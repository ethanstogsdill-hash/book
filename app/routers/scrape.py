"""Scrape trigger and status endpoints."""
import asyncio
from fastapi import APIRouter, Request
from app import database as db_mod
from app.auth import require_auth
from app.services.scraper import run_scrape, scrape_status

router = APIRouter(prefix="/api/scrape", tags=["scrape"])


@router.post("/trigger")
async def trigger_scrape(request: Request):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
    finally:
        await db.close()

    if scrape_status["running"]:
        return {"error": "Scrape already in progress"}

    # Run in background so the API returns immediately
    asyncio.create_task(run_scrape())
    return {"ok": True, "message": "Scrape started"}


@router.get("/status")
async def get_scrape_status(request: Request):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        last = await db_mod.get_last_scrape(db)
        return {
            "running": scrape_status["running"],
            "last_run": scrape_status.get("last_run"),
            "last_status": scrape_status.get("last_status"),
            "last_message": scrape_status.get("last_message"),
            "last_success": last,
        }
    finally:
        await db.close()
