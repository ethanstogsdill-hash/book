"""Bets listing endpoints."""
from fastapi import APIRouter, Request
from app import database as db_mod
from app.auth import require_auth

router = APIRouter(prefix="/api/bets", tags=["bets"])


@router.get("")
async def list_bets(
    request: Request,
    player_id: str = None,
    sport: str = None,
    result: str = None,
    limit: int = 100,
    offset: int = 0,
):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        bets = await db_mod.get_bets(db, player_id, sport, result, limit, offset)
        return {"bets": bets}
    finally:
        await db.close()


@router.get("/stats")
async def bet_stats(request: Request):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        stats = await db_mod.get_bet_stats(db)
        return stats
    finally:
        await db.close()


@router.get("/sports")
async def bet_sports(request: Request):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        sports = await db_mod.get_bet_sports(db)
        return {"sports": sports}
    finally:
        await db.close()
