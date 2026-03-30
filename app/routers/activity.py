"""Activity log endpoints — scrape history and alerts."""
from fastapi import APIRouter, Request
from app import database as db_mod
from app.auth import require_auth

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("")
async def get_activity(request: Request, limit: int = 30):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        logs = await db_mod.get_scrape_logs(db, limit)
        alerts = await db_mod.get_alerts(db, limit)
        return {"logs": logs, "alerts": alerts}
    finally:
        await db.close()


@router.get("/alerts")
async def get_alerts(request: Request, limit: int = 20):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        alerts = await db_mod.get_alerts(db, limit)
        return {"alerts": alerts}
    finally:
        await db.close()
