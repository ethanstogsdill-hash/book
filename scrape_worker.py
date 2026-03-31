"""Standalone scrape script — launches native Chrome via CDP to bypass Cloudflare.

Usage: python scrape_worker.py <site_url> <username> <password> [chrome_profile_dir]

Outputs JSON to stdout:
{
    "players": [{"account_id": "...", "agent_name": "...", "win_loss": 0, "balance": 0, "action": 0, "raw_data": {}}],
    "wagers": [{"ticket_id": "...", "player_id": "...", "placed_at": "...", "sport": "...", ...}]
}
"""
import hashlib
import json
import re
import sys
import os
import time
import subprocess
from playwright.sync_api import sync_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9222


def parse_number(text: str) -> float:
    """Parse a money/number string like '$1,234.56' or '(500.00)' into a float."""
    if not text:
        return 0.0
    text = text.strip()
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    text = text.replace("$", "").replace(",", "").strip()
    if not text or text == "-":
        return 0.0
    try:
        val = float(text)
        return -val if negative else val
    except ValueError:
        return 0.0


def normalize_result(text: str) -> str:
    """Normalize bet result text to standard values."""
    t = text.strip().lower()
    if t in ("win", "won", "w"):
        return "win"
    if t in ("loss", "lost", "lose", "l"):
        return "loss"
    if t in ("push", "tie", "draw"):
        return "push"
    if t in ("cancel", "cancelled", "void", "no action"):
        return "cancel"
    return "pending"


def kill_chrome():
    """Kill Chrome processes on Windows."""
    try:
        os.system('taskkill /F /IM chrome.exe /T >nul 2>&1')
    except Exception:
        pass


def main():
    site_url = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    profile_dir = sys.argv[4] if len(sys.argv) > 4 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "chrome_profile"
    )
    mode = sys.argv[5] if len(sys.argv) > 5 else "full"  # "full" or "livebets"

    os.makedirs(profile_dir, exist_ok=True)

    # Launch Chrome with CDP
    profile_abs = os.path.abspath(profile_dir)
    chrome_args = [
        CHROME_PATH,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={profile_abs}",
        "--no-first-run",
        "--no-default-browser-check",
        site_url,
    ]
    # Launch Chrome fully detached so it doesn't block the parent process pipes
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    DETACHED_PROCESS = 0x00000008
    chrome_proc = subprocess.Popen(
        chrome_args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS,
    )

    # Wait for Chrome CDP to be ready
    import urllib.request
    for attempt in range(15):
        time.sleep(1)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=2)
            break
        except Exception:
            continue
    else:
        print(json.dumps({"error": "Chrome failed to start with CDP"}), file=sys.stderr)
        sys.exit(1)

    result = {"players": [], "wagers": []}

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()

            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                page.wait_for_load_state("load", timeout=30000)
            page.wait_for_timeout(3000)

            # Wait for Cloudflare challenge to resolve
            for attempt in range(20):
                title = page.title().lower()
                url = page.url.lower()
                print(f"DEBUG: attempt={attempt} title='{page.title()}' url='{page.url}'", file=sys.stderr)
                if "moment" in title or "checking" in title or "challenge" in url or "cloudflare" in title:
                    print("DEBUG: Cloudflare challenge detected, waiting...", file=sys.stderr)
                    time.sleep(5)
                    continue
                break
            else:
                print(json.dumps({"error": "Cloudflare challenge not resolved after 100s"}), file=sys.stderr)
                sys.exit(1)

            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            page.wait_for_timeout(2000)

            # Login if needed
            if "login" in page.url.lower():
                try:
                    page.locator("#ctl00_ContentSectionMisc_txtUser").wait_for(state="visible", timeout=30000)
                except Exception:
                    print(f"DEBUG: Login form not found. URL={page.url}", file=sys.stderr)
                    print(json.dumps({"error": f"Login form not found: {page.url}"}), file=sys.stderr)
                    sys.exit(1)

                page.fill("#ctl00_ContentSectionMisc_txtUser", username)
                page.wait_for_timeout(500)
                page.fill("#ctl00_ContentSectionMisc_txtPassword", password)
                page.wait_for_timeout(500)
                page.click("a.btn-login")
                try:
                    page.wait_for_load_state("load", timeout=30000)
                except Exception:
                    pass
                page.wait_for_timeout(5000)

                if "login" in page.url.lower():
                    print(json.dumps({"error": "Login failed — still on login page"}), file=sys.stderr)
                    sys.exit(1)

                print("DEBUG: Login successful", file=sys.stderr)

            # Use the actual base URL from the browser (may differ from configured due to redirects)
            from urllib.parse import urlparse
            parsed = urlparse(page.url)
            actual_base = f"{parsed.scheme}://{parsed.netloc}"
            print(f"DEBUG: Post-login URL: {page.url}, using base: {actual_base}", file=sys.stderr)

            if mode == "livebets":
                # ─── Scrape Live Bets Only ─────────────────────────────
                result["live_bets"] = scrape_live_bets(page, actual_base)
            else:
                # ─── Scrape Dashboard ──────────────────────────────────
                result["players"] = scrape_dashboard(page, actual_base)

                # ─── Scrape Weekly Balance ─────────────────────────────
                enrich_with_balance(page, actual_base, result["players"])

                # ─── Scrape Wagers ─────────────────────────────────────
                result["wagers"] = scrape_wagers(page, actual_base)

            browser.close()

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)
    finally:
        kill_chrome()

    print(json.dumps(result))


def scrape_dashboard(page, site_url: str) -> list:
    """Scrape the Dashboard page for player win/loss data with agent (sub-agent) info."""
    players = []
    try:
        # Check if we're already on a dashboard/content page
        current = page.url.lower()
        if "login" in current or "dashboard" not in current:
            # Try navigating to dashboard
            dashboard_url = site_url.rstrip("/") + "/Forms/Dashboard.aspx"
            print(f"DEBUG: Navigating to {dashboard_url}", file=sys.stderr)
            page.goto(dashboard_url, wait_until="load", timeout=30000)
            page.wait_for_timeout(5000)

            # If redirected back to login, try clicking Dashboard link in nav menu
            if "login" in page.url.lower():
                print("DEBUG: Redirected to login, trying nav menu", file=sys.stderr)
                page.go_back()
                page.wait_for_timeout(2000)
                try:
                    page.click("text=Dashboard", timeout=5000)
                    page.wait_for_timeout(3000)
                except Exception:
                    # Try other nav links
                    try:
                        page.click("a[href*='Dashboard']", timeout=5000)
                        page.wait_for_timeout(3000)
                    except Exception:
                        pass
        else:
            page.wait_for_timeout(3000)

        print(f"DEBUG: Now on: {page.url}", file=sys.stderr)

        # Debug: dump page info
        print(f"DEBUG: Dashboard URL: {page.url}", file=sys.stderr)
        print(f"DEBUG: Dashboard title: {page.title()}", file=sys.stderr)

        # Try to find ALL tables on the page
        all_tables = page.locator("table").all()
        print(f"DEBUG: Total <table> elements on page: {len(all_tables)}", file=sys.stderr)
        for i, t in enumerate(all_tables[:10]):
            cls = t.get_attribute("class") or ""
            tid = t.get_attribute("id") or ""
            rows = t.locator("tr").count()
            print(f"DEBUG: Table {i}: class='{cls}' id='{tid}' rows={rows}", file=sys.stderr)

        # Find tables with broader selectors
        tables = page.locator("table").all()
        # Filter to tables with at least 2 rows (header + data)
        tables = [t for t in tables if t.locator("tr").count() >= 2]
        print(f"DEBUG: Tables with 2+ rows: {len(tables)}", file=sys.stderr)

        seen_ids = set()
        for table in tables:
            rows = table.locator("tr").all()
            if len(rows) < 2:
                continue

            # Parse header to find column indices
            header_cells = rows[0].locator("th, td").all()
            headers = [h.inner_text().strip().lower() for h in header_cells]
            print(f"DEBUG: Table headers: {headers}", file=sys.stderr)

            # Find key columns by fuzzy matching
            agent_col = next((i for i, h in enumerate(headers) if "agent" in h), None)
            player_col = next((i for i, h in enumerate(headers) if "player" in h or "account" in h or "id" in h), None)
            wl_col = next((i for i, h in enumerate(headers) if "win" in h or "loss" in h or "w/l" in h or "net" in h), None)

            if player_col is None:
                continue

            for row in rows[1:]:
                cells = row.locator("td").all()
                if len(cells) <= max(filter(None, [agent_col, player_col, wl_col]), default=0):
                    continue

                agent_name = cells[agent_col].inner_text().strip() if agent_col is not None else ""
                player_id = cells[player_col].inner_text().strip() if player_col is not None else ""
                win_loss = parse_number(cells[wl_col].inner_text()) if wl_col is not None else 0

                if not player_id or player_id in seen_ids:
                    continue
                seen_ids.add(player_id)

                players.append({
                    "account_id": player_id,
                    "agent_name": agent_name,
                    "win_loss": win_loss,
                    "balance": 0,
                    "action": 0,
                    "raw_data": {"agent": agent_name, "source": "dashboard"},
                })

    except Exception as e:
        print(f"DEBUG: Dashboard scrape error: {e}", file=sys.stderr)

    print(f"DEBUG: Scraped {len(players)} players from dashboard", file=sys.stderr)
    return players


def enrich_with_balance(page, site_url: str, players: list):
    """Navigate to Weekly Balance page and enrich player records with balance/action."""
    try:
        balance_url = site_url.rstrip("/") + "/Forms/BettorBalance.aspx"
        print(f"DEBUG: Navigating to balance page: {balance_url}", file=sys.stderr)
        page.goto(balance_url, wait_until="load", timeout=30000)
        page.wait_for_timeout(5000)
        print(f"DEBUG: Balance page URL: {page.url}, title: {page.title()}", file=sys.stderr)

        # Use broad table selector
        all_tables = page.locator("table").all()
        tables = [t for t in all_tables if t.locator("tr").count() >= 2]
        print(f"DEBUG: Balance page tables: {len(all_tables)} total, {len(tables)} with 2+ rows", file=sys.stderr)

        # Debug first table headers
        for i, t in enumerate(tables[:5]):
            hdrs = [c.inner_text().strip().lower() for c in t.locator("tr").first.locator("th, td").all()]
            print(f"DEBUG: Balance table {i} headers: {hdrs}", file=sys.stderr)

        player_map = {p["account_id"]: p for p in players}

        for table in tables:
            rows = table.locator("tr").all()
            if len(rows) < 2:
                continue

            header_cells = rows[0].locator("th, td").all()
            headers = [h.inner_text().strip().lower() for h in header_cells]

            # The balance table may use "agent" as first column containing player IDs
            player_col = next((i for i, h in enumerate(headers) if "player" in h or "account" in h or "bettor" in h), None)
            agent_col = next((i for i, h in enumerate(headers) if "agent" in h), None)
            # If no explicit player column, the "agent" column likely holds the player/account name
            if player_col is None and agent_col is not None:
                player_col = agent_col
                agent_col = None

            balance_col = next((i for i, h in enumerate(headers) if "new bal" in h or "balance" in h), None)
            prev_bal_col = next((i for i, h in enumerate(headers) if "prev bal" in h or "prev" in h), None)
            action_col = next((i for i, h in enumerate(headers) if "action" in h or "handle" in h or "volume" in h or "at risk" in h), None)
            wl_col = next((i for i, h in enumerate(headers) if h == "this week" or "win" in h or "loss" in h or "w/l" in h), None)
            settle_col = next((i for i, h in enumerate(headers) if "settle" in h), None)

            if player_col is None:
                continue

            print(f"DEBUG: Balance columns: player={player_col} balance={balance_col} wl={wl_col} action={action_col} settle={settle_col}", file=sys.stderr)

            for row in rows[1:]:
                cells = row.locator("td").all()
                if len(cells) < 3:
                    continue

                raw_pid = cells[player_col].inner_text().strip() if player_col < len(cells) else ""
                if not raw_pid or "total" in raw_pid.lower() or "grand" in raw_pid.lower():
                    continue

                # Balance page shows "ACCOUNT_ID / DISPLAY_NAME" — extract the account ID
                pid = raw_pid.split("/")[0].strip() if "/" in raw_pid else raw_pid
                display_name = raw_pid.split("/")[1].strip() if "/" in raw_pid else ""

                balance = parse_number(cells[balance_col].inner_text()) if balance_col is not None and balance_col < len(cells) else 0
                action = parse_number(cells[action_col].inner_text()) if action_col is not None and action_col < len(cells) else 0
                wl = parse_number(cells[wl_col].inner_text()) if wl_col is not None and wl_col < len(cells) else None
                settle = parse_number(cells[settle_col].inner_text()) if settle_col is not None and settle_col < len(cells) else 0

                print(f"DEBUG: Balance row: pid={pid} name={display_name} balance={balance} wl={wl} action={action}", file=sys.stderr)

                if pid in player_map:
                    player_map[pid]["balance"] = balance
                    player_map[pid]["action"] = action
                    if display_name and not player_map[pid].get("name"):
                        player_map[pid]["name"] = display_name
                    if wl is not None:
                        player_map[pid]["win_loss"] = wl
                else:
                    # New player found on balance page but not dashboard
                    players.append({
                        "account_id": pid,
                        "name": display_name,
                        "agent_name": "",
                        "win_loss": wl if wl is not None else 0,
                        "balance": balance,
                        "action": action,
                        "raw_data": {"source": "balance"},
                    })
                    player_map[pid] = players[-1]

    except Exception as e:
        print(f"DEBUG: Balance scrape error: {e}", file=sys.stderr)

    print(f"DEBUG: Balance enrichment done, total players: {len(players)}", file=sys.stderr)


def scrape_wagers(page, site_url: str) -> list:
    """Scrape the Wagers/Bets page for individual bet records."""
    wagers = []
    try:
        # Navigate to wagers — try common report paths
        wager_urls = [
            site_url.rstrip("/") + "/Forms/OpenWagers.aspx",
            site_url.rstrip("/") + "/Forms/Wagers.aspx",
        ]

        navigated = False
        for url in wager_urls:
            try:
                page.goto(url, wait_until="load", timeout=15000)
                page.wait_for_timeout(2000)
                if "login" not in page.url.lower():
                    navigated = True
                    break
            except Exception:
                continue

        if not navigated:
            # Try clicking through the Reports menu
            try:
                page.click("text=Reports", timeout=5000)
                page.wait_for_timeout(1000)
                page.click("text=Wagers", timeout=5000)
                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)
                navigated = True
            except Exception:
                pass

        if not navigated:
            print("DEBUG: Could not navigate to wagers page", file=sys.stderr)
            return wagers

        tables = page.locator("table.table, table[class*='grid'], table[id*='grid']").all()

        for table in tables:
            rows = table.locator("tr").all()
            if len(rows) < 2:
                continue

            header_cells = rows[0].locator("th, td").all()
            headers = [h.inner_text().strip().lower() for h in header_cells]

            ticket_col = next((i for i, h in enumerate(headers) if "ticket" in h or "#" in h), None)
            player_col = next((i for i, h in enumerate(headers) if "player" in h or "account" in h), None)
            date_col = next((i for i, h in enumerate(headers) if "date" in h or "time" in h), None)
            sport_col = next((i for i, h in enumerate(headers) if "sport" in h), None)
            desc_col = next((i for i, h in enumerate(headers) if "desc" in h or "selection" in h or "team" in h), None)
            type_col = next((i for i, h in enumerate(headers) if "type" in h), None)
            risk_col = next((i for i, h in enumerate(headers) if "risk" in h or "stake" in h or "wager" in h), None)
            win_col = next((i for i, h in enumerate(headers) if "win" in h and "loss" not in h), None)
            result_col = next((i for i, h in enumerate(headers) if "result" in h or "status" in h or "outcome" in h), None)

            if player_col is None:
                continue

            for row in rows[1:]:
                cells = row.locator("td").all()
                if len(cells) < 3:
                    continue

                def cell_text(col_idx):
                    if col_idx is not None and col_idx < len(cells):
                        return cells[col_idx].inner_text().strip()
                    return ""

                ticket_id = cell_text(ticket_col) or hashlib.md5(
                    f"{cell_text(player_col)}{cell_text(date_col)}{cell_text(desc_col)}".encode()
                ).hexdigest()[:12]

                wagers.append({
                    "ticket_id": ticket_id,
                    "player_id": cell_text(player_col),
                    "placed_at": cell_text(date_col),
                    "sport": cell_text(sport_col),
                    "description": cell_text(desc_col),
                    "bet_type": cell_text(type_col),
                    "risk": parse_number(cell_text(risk_col)),
                    "win_amount": parse_number(cell_text(win_col)),
                    "result": normalize_result(cell_text(result_col)),
                    "raw_data": {},
                })

    except Exception as e:
        print(f"DEBUG: Wagers scrape error: {e}", file=sys.stderr)

    print(f"DEBUG: Scraped {len(wagers)} wagers", file=sys.stderr)
    return wagers


def scrape_live_bets(page, site_url: str) -> list:
    """Scrape the Wagers Ticker (Live) page for open/active bets.

    Page structure (allagentreports.com):
    - Table 0: Color legend (1 row, skip)
    - Table 1: Headers row with TH cells: Date, Agent|Player/Password, Ticket, Source, Type, Description, Risk, Win
    - Table 2: Data rows with TD cells, but has 2 extra columns at start (checkbox, Delete button)
      So data columns are offset by +2: col2=Date, col3=Agent|Player, col4=Ticket, col5=Source, col6=Type, col7=Description, col8=Risk, col9=Win
    """
    live_bets = []
    try:
        live_url = site_url.rstrip("/") + "/Forms/BettorWagersLive.aspx"
        print(f"DEBUG: Navigating to live bets: {live_url}", file=sys.stderr)
        page.goto(live_url, wait_until="load", timeout=30000)
        page.wait_for_timeout(5000)
        print(f"DEBUG: Live bets page: {page.url}, title: {page.title()}", file=sys.stderr)

        if "login" in page.url.lower():
            print("DEBUG: Redirected to login, live bets page not accessible", file=sys.stderr)
            return live_bets

        # Find the data table (the one with the most rows)
        all_tables = page.locator("table").all()
        data_table = None
        max_rows = 0
        for t in all_tables:
            rc = t.locator("tr").count()
            if rc > max_rows:
                max_rows = rc
                data_table = t

        if not data_table or max_rows < 1:
            print("DEBUG: No data table found on live bets page", file=sys.stderr)
            return live_bets

        print(f"DEBUG: Using data table with {max_rows} rows", file=sys.stderr)

        rows = data_table.locator("tr").all()
        seen_ids = set()

        for row in rows:
            cells = row.locator("td").all()
            # Data rows have 10 columns: checkbox, Delete, Date, Agent|Player, Ticket, Source, Type, Description, Risk, Win
            if len(cells) < 8:
                continue

            # Columns with +2 offset for the checkbox and Delete columns
            date_text = cells[2].inner_text().strip() if len(cells) > 2 else ""
            agent_player_text = cells[3].inner_text().strip() if len(cells) > 3 else ""
            ticket_id = cells[4].inner_text().strip() if len(cells) > 4 else ""
            # source = cells[5]  # "Internet" etc
            bet_type = cells[6].inner_text().strip() if len(cells) > 6 else ""
            description = cells[7].inner_text().strip() if len(cells) > 7 else ""
            risk_text = cells[8].inner_text().strip() if len(cells) > 8 else "0"
            win_text = cells[9].inner_text().strip() if len(cells) > 9 else "0"

            if not ticket_id or not agent_player_text or "delete" in ticket_id.lower():
                continue
            if ticket_id in seen_ids:
                continue
            seen_ids.add(ticket_id)

            # Parse "AGENT_NAME\nPLAYER_ACCOUNT / DISPLAY_NAME" or "AGENT_NAME | PLAYER_ACCOUNT / DISPLAY_NAME"
            sub_agent_name = ""
            player_account = ""
            player_name = ""
            # The cell contains agent on first line, player on second line (separated by \n)
            ap = agent_player_text.replace("|", "\n")
            lines = [l.strip() for l in ap.split("\n") if l.strip()]
            if len(lines) >= 2:
                sub_agent_name = lines[0]
                player_part = lines[1]
                if "/" in player_part:
                    player_account = player_part.split("/")[0].strip()
                    player_name = player_part.split("/")[1].strip()
                else:
                    player_account = player_part
                    player_name = player_part
            elif len(lines) == 1:
                player_account = lines[0]

            amount = parse_number(risk_text)
            payout = parse_number(win_text)

            # Extract odds from description if present (e.g., "-150", "+135")
            odds = ""
            odds_match = re.search(r'[+-]\d{3,}', description)
            if odds_match:
                odds = odds_match.group()

            # Extract sport from description (e.g., "[MLB]", "[NBA]")
            sport = ""
            sport_match = re.search(r'\[(\w+)\]', description)
            if sport_match:
                sport = sport_match.group(1)

            # Clean up description — collapse newlines
            description = description.replace("\n", " | ").strip()

            bet = {
                "bet_id": ticket_id,
                "player_name": player_name,
                "player_account": player_account,
                "sub_agent_name": sub_agent_name,
                "description": description,
                "amount": amount,
                "odds": odds,
                "potential_payout": payout if payout else amount,
                "time_placed": date_text,
                "status": "open",
                "sport": sport,
                "bet_type": bet_type,
                "raw_data": {},
            }
            live_bets.append(bet)
            print(f"DEBUG: Live bet: {player_account} {description[:40]} risk=${amount} win=${payout}", file=sys.stderr)

    except Exception as e:
        print(f"DEBUG: Live bets scrape error: {e}", file=sys.stderr)

    print(f"DEBUG: Scraped {len(live_bets)} live bets", file=sys.stderr)
    return live_bets


if __name__ == "__main__":
    main()
