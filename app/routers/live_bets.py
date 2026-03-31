"""Live bets API endpoints."""
import asyncio
from fastapi import APIRouter, Request
from app import database as db_mod
from app.auth import require_auth
from app.services.live_bets_scraper import run_live_bets_scrape, live_bets_status

router = APIRouter(prefix="/api/live-bets", tags=["live-bets"])


@router.get("")
async def get_live_bets(request: Request, sort_by: str = "sub_agent_name", sort_dir: str = "desc"):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        bets = await db_mod.get_live_bets(db, sort_by, sort_dir)

        # Group by sub-agent for the frontend
        groups = {}
        direct_bets = []
        player_credit_limits = {}

        # Get credit limits for color coding
        players = await db_mod.get_players(db)
        for p in players:
            player_credit_limits[p["account_id"]] = p.get("credit_limit", 0)

        from app.config import settings
        for b in bets:
            b["credit_limit"] = player_credit_limits.get(b["player_account"], 0)
            sa = b.get("sub_agent_name", "")
            if sa and sa.upper() != settings.site_username.upper():
                if sa not in groups:
                    groups[sa] = {"name": sa, "bets": [], "total_amount": 0, "total_payout": 0}
                groups[sa]["bets"].append(b)
                groups[sa]["total_amount"] += b.get("amount", 0)
                groups[sa]["total_payout"] += b.get("potential_payout", 0)
            else:
                direct_bets.append(b)

        # Sort groups by total amount at risk (descending)
        sorted_groups = sorted(groups.values(), key=lambda g: g["total_amount"], reverse=True)

        return {
            "groups": sorted_groups,
            "direct_bets": direct_bets,
            "all_bets": bets,
        }
    finally:
        await db.close()


@router.get("/summary")
async def live_bets_summary(request: Request):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        summary = await db_mod.get_live_bets_summary(db)
        summary["running"] = live_bets_status["running"]
        return summary
    finally:
        await db.close()


@router.post("/refresh")
async def refresh_live_bets(request: Request):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
    finally:
        await db.close()

    if live_bets_status["running"]:
        return {"error": "Already refreshing"}

    asyncio.create_task(run_live_bets_scrape())
    return {"ok": True, "message": "Live bets refresh started"}


@router.get("/status")
async def get_status(request: Request):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
    finally:
        await db.close()
    return live_bets_status
