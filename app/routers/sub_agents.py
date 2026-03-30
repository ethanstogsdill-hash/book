"""Sub-agent CRUD endpoints."""
from fastapi import APIRouter, Request, HTTPException
from app import database as db_mod
from app.auth import require_auth
from app.models import SubAgentCreate, SubAgentUpdate

router = APIRouter(prefix="/api/sub-agents", tags=["sub-agents"])


@router.get("")
async def list_sub_agents(request: Request):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        subs = await db_mod.get_sub_agents(db)
        return {"sub_agents": subs}
    finally:
        await db.close()


@router.get("/{sub_id}")
async def get_sub_agent(request: Request, sub_id: int):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        sub = await db_mod.get_sub_agent(db, sub_id)
        if not sub:
            raise HTTPException(status_code=404, detail="Sub-agent not found")
        return sub
    finally:
        await db.close()


@router.post("")
async def create_sub_agent(request: Request, body: SubAgentCreate):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        sid = await db_mod.create_sub_agent(db, body.model_dump())
        return {"ok": True, "id": sid}
    finally:
        await db.close()


@router.patch("/{sub_id}")
async def update_sub_agent(request: Request, sub_id: int, body: SubAgentUpdate):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        sub = await db_mod.get_sub_agent(db, sub_id)
        if not sub:
            raise HTTPException(status_code=404, detail="Sub-agent not found")
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        await db_mod.update_sub_agent(db, sub_id, updates)
        return {"ok": True}
    finally:
        await db.close()


@router.get("/{sub_id}/players")
async def sub_agent_players(request: Request, sub_id: int):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        players = await db_mod.get_players(db, sub_agent_id=sub_id)
        return {"players": players}
    finally:
        await db.close()
