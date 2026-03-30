"""Scraper service — runs scrape_worker.py as a subprocess and processes results."""
import asyncio
import json
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from app.config import settings
from app import database as db_mod

WORKER_SCRIPT = str(Path(__file__).resolve().parent.parent.parent / "scrape_worker.py")

# Track scrape state
scrape_status = {
    "running": False,
    "last_run": None,
    "last_status": None,
    "last_message": None,
}

_executor = ThreadPoolExecutor(max_workers=1)


def _run_scrape_sync():
    """Run the scraper subprocess synchronously (called from thread pool)."""
    print(f"[SCRAPER] Launching: {sys.executable} {WORKER_SCRIPT}", flush=True)

    proc = subprocess.run(
        [
            sys.executable, WORKER_SCRIPT,
            settings.site_url,
            settings.site_username,
            settings.site_password,
            settings.chrome_profile,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )

    print(f"[SCRAPER] Done. returncode={proc.returncode} stdout_len={len(proc.stdout)} stderr_len={len(proc.stderr)}", flush=True)

    if proc.stderr:
        for line in proc.stderr.strip().split("\n"):
            if line.strip():
                print(f"[SCRAPER] {line}", flush=True)

    if proc.returncode != 0:
        raise RuntimeError(f"Scraper exited with code {proc.returncode}: {proc.stderr[-200:]}")

    return json.loads(proc.stdout)


async def run_scrape():
    """Execute the scraper and process results into the database."""
    if scrape_status["running"]:
        return {"error": "Scrape already in progress"}

    scrape_status["running"] = True
    start_time = time.time()
    database = await db_mod.get_db()

    try:
        await db_mod.log_scrape(database, "scrape", "running", "Scrape started")

        # Run subprocess in thread pool to avoid async pipe issues on Windows
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(_executor, _run_scrape_sync)

        if "error" in data:
            duration = time.time() - start_time
            await db_mod.log_scrape(database, "scrape", "error", data["error"], 0, duration)
            scrape_status.update(running=False, last_run=time.time(),
                                 last_status="error", last_message=data["error"])
            return {"error": data["error"]}

        # Process players
        players = data.get("players", [])
        player_count = await db_mod.upsert_players(
            database, players, settings.site_username
        )

        # Process wagers
        wagers = data.get("wagers", [])
        bet_count = await db_mod.upsert_bets(database, wagers)

        duration = time.time() - start_time
        total = player_count + bet_count
        msg = f"Synced {player_count} players, {bet_count} new bets"
        await db_mod.log_scrape(database, "scrape", "success", msg, total, duration)

        scrape_status.update(
            running=False, last_run=time.time(),
            last_status="success", last_message=msg
        )
        return {"ok": True, "players": player_count, "bets": bet_count, "duration": round(duration, 1)}

    except Exception as e:
        tb = traceback.format_exc()
        error_msg = f"{type(e).__name__}: {e}"
        print(f"[SCRAPER] ERROR: {error_msg}\n{tb}", flush=True)
        duration = time.time() - start_time
        await db_mod.log_scrape(database, "scrape", "error", error_msg[:500], 0, duration)
        scrape_status.update(running=False, last_run=time.time(),
                             last_status="error", last_message=error_msg[:500])
        return {"error": error_msg[:500]}
    finally:
        scrape_status["running"] = False
        await database.close()
