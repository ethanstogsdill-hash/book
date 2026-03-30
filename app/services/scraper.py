"""Scraper service — runs scrape_worker.py as a subprocess and processes results."""
import asyncio
import json
import sys
import time
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


async def run_scrape():
    """Execute the scraper and process results into the database."""
    if scrape_status["running"]:
        return {"error": "Scrape already in progress"}

    scrape_status["running"] = True
    start_time = time.time()
    database = await db_mod.get_db()

    try:
        await db_mod.log_scrape(database, "scrape", "running", "Scrape started")

        proc = await asyncio.create_subprocess_exec(
            sys.executable, WORKER_SCRIPT,
            settings.site_url,
            settings.site_username,
            settings.site_password,
            settings.chrome_profile,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

        if stderr:
            for line in stderr.decode().split("\n"):
                if line.strip():
                    print(f"[SCRAPER] {line}", flush=True)

        if proc.returncode != 0:
            error_msg = f"Scraper exited with code {proc.returncode}"
            duration = time.time() - start_time
            await db_mod.log_scrape(database, "scrape", "error", error_msg, 0, duration)
            scrape_status.update(running=False, last_run=time.time(),
                                 last_status="error", last_message=error_msg)
            return {"error": error_msg}

        data = json.loads(stdout.decode())

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

    except asyncio.TimeoutError:
        duration = time.time() - start_time
        await db_mod.log_scrape(database, "scrape", "error", "Scrape timed out after 5 minutes", 0, duration)
        scrape_status.update(running=False, last_run=time.time(),
                             last_status="error", last_message="Timeout after 5 minutes")
        return {"error": "Scrape timed out"}
    except Exception as e:
        duration = time.time() - start_time
        await db_mod.log_scrape(database, "scrape", "error", str(e), 0, duration)
        scrape_status.update(running=False, last_run=time.time(),
                             last_status="error", last_message=str(e))
        return {"error": str(e)}
    finally:
        scrape_status["running"] = False
        await database.close()
