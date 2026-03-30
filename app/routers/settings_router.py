"""Settings endpoints."""
from fastapi import APIRouter, Request
from app import database as db_mod
from app.auth import require_auth
from app.models import SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings(request: Request):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        s = await db_mod.get_all_settings(db)
        return {"settings": s}
    finally:
        await db.close()


@router.patch("")
async def update_settings(request: Request, body: SettingsUpdate):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        await db_mod.update_settings(db, body.settings)
        return {"ok": True}
    finally:
        await db.close()
