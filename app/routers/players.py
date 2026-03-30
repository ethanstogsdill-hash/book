"""Player CRUD endpoints."""
from fastapi import APIRouter, Request, HTTPException, Query
from app import database as db_mod
from app.auth import require_auth
from app.models import PlayerCreate, PlayerUpdate

router = APIRouter(prefix="/api/players", tags=["players"])


@router.get("")
async def list_players(
    request: Request,
    search: str = None,
    status: str = None,
    sub_agent_id: int = None,
    sort_by: str = "name",
    sort_dir: str = "asc",
):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        players = await db_mod.get_players(db, search, status, sub_agent_id, sort_by, sort_dir)
        return {"players": players}
    finally:
        await db.close()


@router.get("/{player_id}")
async def get_player(request: Request, player_id: int):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        player = await db_mod.get_player(db, player_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        return player
    finally:
        await db.close()


@router.post("")
async def create_player(request: Request, body: PlayerCreate):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        existing = await db_mod.get_player_by_account_id(db, body.account_id)
        if existing:
            raise HTTPException(status_code=400, detail="Account ID already exists")
        pid = await db_mod.create_player(db, body.model_dump())
        return {"ok": True, "id": pid}
    finally:
        await db.close()


@router.patch("/{player_id}")
async def update_player(request: Request, player_id: int, body: PlayerUpdate):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        player = await db_mod.get_player(db, player_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        await db_mod.update_player(db, player_id, updates)
        return {"ok": True}
    finally:
        await db.close()


@router.get("/{player_id}/history")
async def player_history(request: Request, player_id: int):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        history = await db_mod.get_player_history(db, player_id)
        return {"history": history}
    finally:
        await db.close()
