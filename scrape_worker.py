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
        subprocess.run(
            ["taskkill", "/F", "/IM", "chrome.exe", "/T"],
            capture_output=True, timeout=10
        )
    except Exception:
        pass


def main():
    site_url = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    profile_dir = sys.argv[4] if len(sys.argv) > 4 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "chrome_profile"
    )

    os.makedirs(profile_dir, exist_ok=True)

    # Launch Chrome with CDP
    profile_abs = os.path.abspath(profile_dir)
    cmd = (
        f'start "" "{CHROME_PATH}" '
        f'--remote-debugging-port={CDP_PORT} '
        f'--user-data-dir="{profile_abs}" '
        f'--no-first-run --no-default-browser-check "{site_url}"'
    )
    os.system(cmd)

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

            page.wait_for_load_state("networkidle", timeout=60000)
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

            page.wait_for_load_state("networkidle", timeout=30000)
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
                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                if "login" in page.url.lower():
                    print(json.dumps({"error": "Login failed — still on login page"}), file=sys.stderr)
                    sys.exit(1)

                print("DEBUG: Login successful", file=sys.stderr)

            # ─── Scrape Dashboard ───────────────────────────────────
            result["players"] = scrape_dashboard(page, site_url)

            # ─── Scrape Weekly Balance ──────────────────────────────
            enrich_with_balance(page, site_url, result["players"])

            # ─── Scrape Wagers ──────────────────────────────────────
            result["wagers"] = scrape_wagers(page, site_url)

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
        dashboard_url = site_url.rstrip("/") + "/Forms/Dashboard.aspx"
        page.goto(dashboard_url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)

        # Find tables — typically "Top Losers" and "Top Winners"
        tables = page.locator("table.table, table[class*='grid'], table[id*='grid']").all()
        print(f"DEBUG: Found {len(tables)} tables on dashboard", file=sys.stderr)

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
        page.goto(balance_url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)

        tables = page.locator("table.table, table[class*='grid'], table[id*='grid']").all()

        player_map = {p["account_id"]: p for p in players}

        for table in tables:
            rows = table.locator("tr").all()
            if len(rows) < 2:
                continue

            header_cells = rows[0].locator("th, td").all()
            headers = [h.inner_text().strip().lower() for h in header_cells]

            player_col = next((i for i, h in enumerate(headers) if "player" in h or "account" in h or "bettor" in h), None)
            balance_col = next((i for i, h in enumerate(headers) if "balance" in h), None)
            action_col = next((i for i, h in enumerate(headers) if "action" in h or "handle" in h or "volume" in h), None)
            wl_col = next((i for i, h in enumerate(headers) if "win" in h or "loss" in h or "w/l" in h or "net" in h), None)
            agent_col = next((i for i, h in enumerate(headers) if "agent" in h), None)

            if player_col is None:
                continue

            for row in rows[1:]:
                cells = row.locator("td").all()
                if len(cells) <= (player_col or 0):
                    continue

                pid = cells[player_col].inner_text().strip()
                balance = parse_number(cells[balance_col].inner_text()) if balance_col is not None and len(cells) > balance_col else 0
                action = parse_number(cells[action_col].inner_text()) if action_col is not None and len(cells) > action_col else 0
                wl = parse_number(cells[wl_col].inner_text()) if wl_col is not None and len(cells) > wl_col else None
                agent_name = cells[agent_col].inner_text().strip() if agent_col is not None and len(cells) > agent_col else ""

                if pid in player_map:
                    player_map[pid]["balance"] = balance
                    player_map[pid]["action"] = action
                    if wl is not None:
                        player_map[pid]["win_loss"] = wl
                else:
                    # New player found on balance page but not dashboard
                    players.append({
                        "account_id": pid,
                        "agent_name": agent_name,
                        "win_loss": wl if wl is not None else 0,
                        "balance": balance,
                        "action": action,
                        "raw_data": {"agent": agent_name, "source": "balance"},
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
                page.goto(url, wait_until="networkidle", timeout=15000)
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


if __name__ == "__main__":
    main()
