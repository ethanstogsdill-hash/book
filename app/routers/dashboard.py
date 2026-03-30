"""Dashboard summary endpoint."""
from fastapi import APIRouter, Request, HTTPException
from app import database as db_mod
from app.auth import require_auth

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
async def summary(request: Request):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        data = await db_mod.get_dashboard_summary(db)
        # Also get recent alerts
        alerts = await db_mod.get_alerts(db, limit=5)
        data["recent_alerts"] = alerts
        return data
    finally:
        await db.close()
