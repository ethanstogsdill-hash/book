"""Telegram bot — outbound notifications + inbound command polling."""
import httpx
from app.config import settings
from app import database as db_mod
from app.utils import fmt_money

API_BASE = "https://api.telegram.org/bot{token}"


def _url(method: str) -> str:
    return f"{API_BASE.format(token=settings.telegram_bot_token)}/{method}"


async def send_message(chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    """Send a Telegram message. Returns True on success."""
    if not settings.telegram_bot_token or not chat_id:
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            })
            return resp.status_code == 200
    except Exception as e:
        print(f"[TELEGRAM] Send failed: {e}")
        return False


async def send_to_owner(text: str) -> bool:
    """Send a message to the configured owner chat ID."""
    return await send_message(settings.telegram_chat_id, text)


async def send_test_message() -> bool:
    """Send a test message to verify bot config."""
    return await send_to_owner("Sportsbook Manager bot is working!")


# ─── Alert Functions ──────────────────────────────────────────

async def check_and_send_alerts(db):
    """Check all thresholds and send alerts. Called after each scrape."""
    app_settings = await db_mod.get_all_settings(db)
    if app_settings.get("telegram_alerts_enabled") != "true":
        return

    balance_threshold = float(app_settings.get("balance_alert_threshold", "1000"))
    credit_warning_pct = float(app_settings.get("credit_limit_warning_pct", "80")) / 100
    sub_book_threshold = float(app_settings.get("sub_agent_book_threshold", "5000"))

    # Check player balances
    players = await db_mod.get_players(db)
    for p in players:
        if p["status"] == "inactive":
            continue

        # Balance threshold
        if abs(p["balance"]) > balance_threshold:
            msg = (f"<b>Balance Alert</b>\n"
                   f"Player: {p['name'] or p['account_id']}\n"
                   f"Balance: {fmt_money(p['balance'])}\n"
                   f"Threshold: {fmt_money(balance_threshold)}")
            sent = await send_to_owner(msg)
            await db_mod.log_alert(db, "balance_threshold", f"{p['name'] or p['account_id']}: {fmt_money(p['balance'])}",
                                   p["id"], "player", sent)

        # Credit limit warning
        if p["credit_limit"] > 0 and abs(p["balance"]) > p["credit_limit"] * credit_warning_pct:
            msg = (f"<b>Credit Limit Warning</b>\n"
                   f"Player: {p['name'] or p['account_id']}\n"
                   f"Balance: {fmt_money(p['balance'])}\n"
                   f"Limit: {fmt_money(p['credit_limit'])} ({credit_warning_pct*100:.0f}%)")
            sent = await send_to_owner(msg)
            await db_mod.log_alert(db, "credit_limit", f"{p['name'] or p['account_id']}: near limit",
                                   p["id"], "player", sent)

    # Check sub-agent book sizes
    subs = await db_mod.get_sub_agents(db)
    for s in subs:
        if s["status"] == "inactive":
            continue
        total_book = s.get("total_book", 0)
        if abs(total_book) > sub_book_threshold:
            msg = (f"<b>Sub-Agent Book Alert</b>\n"
                   f"Sub-Agent: {s['name']}\n"
                   f"Book Size: {fmt_money(total_book)}\n"
                   f"Threshold: {fmt_money(sub_book_threshold)}")
            sent = await send_to_owner(msg)
            await db_mod.log_alert(db, "book_threshold", f"{s['name']}: book {fmt_money(total_book)}",
                                   s["id"], "sub_agent", sent)


async def send_settlement_summary(db, week_ending: str):
    """Send the full settlement summary to the owner."""
    settlements = await db_mod.get_settlements(db, week_ending)
    if not settlements:
        return

    lines = [f"<b>Settlement Summary — {week_ending}</b>\n"]

    total_collect = 0
    total_pay = 0

    for s in settlements:
        arrow = "+" if s["direction"] == "collect" else "-"
        lines.append(f"{arrow} {s['counterparty_name']}: {fmt_money(s['amount'])} ({s['direction']})")
        if s["direction"] == "collect":
            total_collect += s["amount"]
        else:
            total_pay += s["amount"]

    lines.append(f"\n<b>Collect:</b> {fmt_money(total_collect)}")
    lines.append(f"<b>Pay:</b> {fmt_money(total_pay)}")
    lines.append(f"<b>Net:</b> {fmt_money(total_collect - total_pay)}")

    await send_to_owner("\n".join(lines))


async def send_settlement_messages(db, settlements: list) -> int:
    """Send individual settlement messages to each sub-agent."""
    sent_count = 0
    for s in settlements:
        if s["counterparty_type"] != "sub_agent" or not s.get("counterparty_id"):
            continue

        sub = await db_mod.get_sub_agent(db, s["counterparty_id"])
        if not sub or not sub.get("telegram_chat_id"):
            continue

        direction_text = "You owe" if s["direction"] == "collect" else "I owe you"
        msg = (f"<b>Weekly Settlement</b>\n"
               f"Week: {s['week_ending']}\n"
               f"{direction_text}: {fmt_money(s['amount'])}\n"
               f"Status: {s['status']}")
        if s.get("notes"):
            msg += f"\nNotes: {s['notes']}"

        if await send_message(sub["telegram_chat_id"], msg):
            sent_count += 1

    return sent_count


async def send_settlement_confirmation(db, settlement: dict):
    """Send confirmation when a settlement is marked as paid."""
    if settlement["counterparty_type"] == "sub_agent" and settlement.get("counterparty_id"):
        sub = await db_mod.get_sub_agent(db, settlement["counterparty_id"])
        if sub and sub.get("telegram_chat_id"):
            msg = (f"<b>Settlement Confirmed</b>\n"
                   f"Week: {settlement['week_ending']}\n"
                   f"Amount: {fmt_money(settlement['amount'])}\n"
                   f"Status: PAID")
            await send_message(sub["telegram_chat_id"], msg)

    # Also notify owner
    await send_to_owner(
        f"Settlement with {settlement['counterparty_name']} marked as PAID "
        f"({fmt_money(settlement['amount'])})"
    )


# ─── Bot Command Polling ──────────────────────────────────────────

_poll_offset = 0


async def poll_commands():
    """Long-poll for incoming bot commands and handle them."""
    global _poll_offset

    if not settings.telegram_bot_token:
        return

    try:
        async with httpx.AsyncClient(timeout=35) as client:
            resp = await client.get(_url("getUpdates"), params={
                "offset": _poll_offset,
                "timeout": 30,
                "allowed_updates": '["message"]',
            })
            if resp.status_code != 200:
                return
            data = resp.json()
            if not data.get("ok"):
                return

            for update in data.get("result", []):
                _poll_offset = update["update_id"] + 1
                await _handle_update(update)

    except Exception as e:
        if "timeout" not in str(e).lower():
            print(f"[TELEGRAM] Poll error: {e}")


async def _handle_update(update: dict):
    """Process a single incoming Telegram update."""
    msg = update.get("message", {})
    chat_id = str(msg.get("chat", {}).get("id", ""))
    text = msg.get("text", "").strip()

    # Security: only respond to the configured owner
    if chat_id != settings.telegram_chat_id:
        return

    if not text.startswith("/"):
        return

    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    db = await db_mod.get_db()
    try:
        if cmd == "/balance":
            await _cmd_balance(db, chat_id, arg)
        elif cmd == "/week":
            await _cmd_week(db, chat_id)
        elif cmd == "/status":
            await _cmd_status(db, chat_id)
        elif cmd in ("/start", "/help"):
            await send_message(chat_id,
                "<b>Sportsbook Manager Bot</b>\n\n"
                "/balance [name] — Check balance\n"
                "/week — This week's summary\n"
                "/status — System status")
        else:
            await send_message(chat_id, "Unknown command. Try /help")
    finally:
        await db.close()


async def _cmd_balance(db, chat_id: str, name: str):
    if not name:
        await send_message(chat_id, "Usage: /balance [player or sub-agent name]")
        return

    # Search players
    players = await db_mod.get_players(db, search=name)
    subs = await db_mod.get_sub_agents(db)
    matching_subs = [s for s in subs if name.lower() in (s["name"] or "").lower()]

    lines = []
    for p in players[:5]:
        lines.append(f"Player <b>{p['name'] or p['account_id']}</b>: {fmt_money(p['balance'])} (W/L: {fmt_money(p['win_loss'])})")
    for s in matching_subs[:3]:
        lines.append(f"Sub <b>{s['name']}</b>: {fmt_money(s['balance'])} ({s.get('player_count', 0)} players)")

    if lines:
        await send_message(chat_id, "\n".join(lines))
    else:
        await send_message(chat_id, f"No results for '{name}'")


async def _cmd_week(db, chat_id: str):
    summary = await db_mod.get_dashboard_summary(db)
    msg = (f"<b>Weekly Summary</b>\n\n"
           f"Players: {summary['total_players']}\n"
           f"Sub-Agents: {summary['total_sub_agents']}\n"
           f"Net Position: {fmt_money(summary['net_position'])}\n"
           f"Outstanding: {fmt_money(summary['total_outstanding'])}\n"
           f"Flagged: {summary['flagged_players']}")
    await send_message(chat_id, msg)


async def _cmd_status(db, chat_id: str):
    last = await db_mod.get_last_scrape(db)
    summary = await db_mod.get_dashboard_summary(db)
    msg = (f"<b>System Status</b>\n\n"
           f"Last Sync: {last['created_at'] if last else 'Never'}\n"
           f"Sync Result: {last['message'] if last else 'N/A'}\n"
           f"Players: {summary['total_players']}\n"
           f"Sub-Agents: {summary['total_sub_agents']}")
    await send_message(chat_id, msg)
