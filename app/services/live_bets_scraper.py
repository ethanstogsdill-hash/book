"""Live bets scraper service — runs scrape_worker.py in livebets mode."""
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

live_bets_status = {
    "running": False,
    "last_run": None,
    "last_status": None,
    "last_message": None,
}

_executor = ThreadPoolExecutor(max_workers=1)


def _run_live_bets_sync():
    """Run the scraper in livebets mode synchronously."""
    print(f"[LIVE_BETS] Launching scraper in livebets mode", flush=True)

    proc = subprocess.run(
        [
            sys.executable, WORKER_SCRIPT,
            settings.site_url,
            settings.site_username,
            settings.site_password,
            settings.chrome_profile,
            "livebets",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )

    print(f"[LIVE_BETS] Done. returncode={proc.returncode} stdout_len={len(proc.stdout)}", flush=True)

    if proc.stderr:
        for line in proc.stderr.strip().split("\n"):
            if line.strip():
                print(f"[LIVE_BETS] {line}", flush=True)

    if proc.returncode != 0:
        raise RuntimeError(f"Live bets scraper exited with code {proc.returncode}: {proc.stderr[-200:]}")

    return json.loads(proc.stdout)


async def run_live_bets_scrape():
    """Execute the live bets scraper and store results."""
    import asyncio

    if live_bets_status["running"]:
        return {"error": "Live bets scrape already in progress"}

    live_bets_status["running"] = True
    start_time = time.time()
    database = await db_mod.get_db()

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(_executor, _run_live_bets_sync)

        if "error" in data:
            live_bets_status.update(running=False, last_run=time.time(),
                                    last_status="error", last_message=data["error"])
            return {"error": data["error"]}

        bets = data.get("live_bets", [])
        count = await db_mod.upsert_live_bets(database, bets)

        duration = time.time() - start_time
        msg = f"Synced {count} live bets in {duration:.1f}s"
        await db_mod.log_scrape(database, "livebets", "success", msg, count, duration)

        live_bets_status.update(
            running=False, last_run=time.time(),
            last_status="success", last_message=msg
        )
        return {"ok": True, "count": count, "duration": round(duration, 1)}

    except Exception as e:
        tb = traceback.format_exc()
        error_msg = f"{type(e).__name__}: {e}"
        print(f"[LIVE_BETS] ERROR: {error_msg}\n{tb}", flush=True)
        live_bets_status.update(running=False, last_run=time.time(),
                                last_status="error", last_message=error_msg[:500])
        return {"error": error_msg[:500]}
    finally:
        live_bets_status["running"] = False
        await database.close()
