"""Background scheduler — auto-scrape, payday, telegram polling."""
import asyncio
from datetime import datetime
from app.config import settings
from app import database as db_mod

_tasks = []
_running = False


async def start_scheduler():
    """Start all background loops."""
    global _running
    _running = True

    _tasks.append(asyncio.create_task(_scrape_loop()))
    # Live bets auto-refresh disabled — use manual Refresh button instead
    # _tasks.append(asyncio.create_task(_live_bets_loop()))
    _tasks.append(asyncio.create_task(_payday_loop()))
    _tasks.append(asyncio.create_task(_telegram_poll_loop()))

    print("[SCHEDULER] All background tasks started")


async def stop_scheduler():
    """Cancel all background tasks."""
    global _running
    _running = False
    for t in _tasks:
        t.cancel()
    _tasks.clear()


async def _scrape_loop():
    """Periodically run the scraper."""
    await asyncio.sleep(300)  # Wait 5 minutes before first auto-scrape

    while _running:
        try:
            db = await db_mod.get_db()
            try:
                interval_str = await db_mod.get_setting(db, "auto_scrape_interval_min", "60")
                interval = int(interval_str) * 60  # Convert to seconds
            finally:
                await db.close()

            from app.services.scraper import run_scrape, scrape_status
            if not scrape_status["running"]:
                print(f"[SCHEDULER] Auto-scrape starting")
                result = await run_scrape()
                print(f"[SCHEDULER] Auto-scrape result: {result}")

                # After scrape, check alerts
                if result.get("ok"):
                    db = await db_mod.get_db()
                    try:
                        from app.services.telegram import check_and_send_alerts
                        await check_and_send_alerts(db)
                    finally:
                        await db.close()

            await asyncio.sleep(interval)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[SCHEDULER] Scrape loop error: {e}")
            await asyncio.sleep(300)  # Wait 5 min on error


async def _live_bets_loop():
    """Auto-refresh live bets every 5 minutes."""
    await asyncio.sleep(120)  # Wait 2 minutes before first refresh

    while _running:
        try:
            from app.services.live_bets_scraper import run_live_bets_scrape, live_bets_status
            if not live_bets_status["running"]:
                print("[SCHEDULER] Auto-refreshing live bets", flush=True)
                result = await run_live_bets_scrape()
                print(f"[SCHEDULER] Live bets result: {result}", flush=True)

            await asyncio.sleep(300)  # 5 minutes

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[SCHEDULER] Live bets loop error: {e}")
            await asyncio.sleep(300)


async def _payday_loop():
    """Check if it's Monday at the configured hour, and run payday if so."""
    while _running:
        try:
            now = datetime.now()
            if now.weekday() == 0:  # Monday
                db = await db_mod.get_db()
                try:
                    payday_hour = int(await db_mod.get_setting(db, "payday_hour", "9"))
                    if now.hour == payday_hour:
                        # Check if we already ran today
                        last_log = await db_mod.get_scrape_logs(db, 1)
                        already_ran = False
                        if last_log:
                            last = last_log[0]
                            if (last["run_type"] == "payday" and
                                    last["created_at"] and
                                    last["created_at"][:10] == now.strftime("%Y-%m-%d")):
                                already_ran = True

                        if not already_ran:
                            print("[SCHEDULER] Running Monday payday")

                            # First, trigger a scrape to get latest data
                            from app.services.scraper import run_scrape
                            await run_scrape()

                            # Then generate settlements
                            from app.services.payday import run_payday
                            from app.utils import current_week_ending
                            week = current_week_ending()
                            result = await run_payday(db, week)
                            print(f"[SCHEDULER] Payday result: {result}")

                            # Send settlement summary via Telegram
                            from app.services.telegram import send_settlement_summary
                            await send_settlement_summary(db, week)
                finally:
                    await db.close()

            # Check every 30 minutes
            await asyncio.sleep(1800)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[SCHEDULER] Payday loop error: {e}")
            await asyncio.sleep(1800)


async def _telegram_poll_loop():
    """Poll Telegram for incoming bot commands."""
    if not settings.telegram_bot_token:
        print("[SCHEDULER] Telegram bot token not configured, skipping poll loop")
        return

    await asyncio.sleep(5)  # Short startup delay

    while _running:
        try:
            from app.services.telegram import poll_commands
            await poll_commands()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[SCHEDULER] Telegram poll error: {e}")
            await asyncio.sleep(10)
