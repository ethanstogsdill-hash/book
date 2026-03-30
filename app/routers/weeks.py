"""Weekly results endpoints."""
from fastapi import APIRouter, Request
from app import database as db_mod
from app.auth import require_auth

router = APIRouter(prefix="/api/weeks", tags=["weeks"])


@router.get("")
async def available_weeks(request: Request):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        weeks = await db_mod.get_available_weeks(db)
        return {"weeks": weeks}
    finally:
        await db.close()


@router.get("/{week_ending}")
async def weekly_results(request: Request, week_ending: str):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        results = await db_mod.get_weekly_results(db, week_ending)

        # Group by sub-agent for hierarchical display
        groups = {}
        direct_players = []

        for r in results:
            if r.get("sub_agent_name"):
                group_name = r["sub_agent_name"]
                if group_name not in groups:
                    groups[group_name] = {"name": group_name, "players": [], "total_net": 0}
                groups[group_name]["players"].append(r)
                groups[group_name]["total_net"] += r.get("net", 0)
            else:
                direct_players.append(r)

        return {
            "week_ending": week_ending,
            "sub_agent_groups": list(groups.values()),
            "direct_players": direct_players,
            "all_results": results,
        }
    finally:
        await db.close()


@router.get("/{week_ending}/summary")
async def weekly_summary(request: Request, week_ending: str):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        results = await db_mod.get_weekly_results(db, week_ending)
        total_won_lost = sum(r.get("won_lost", 0) for r in results)
        total_vig = sum(r.get("vig", 0) for r in results)
        total_net = sum(r.get("net", 0) for r in results)
        return {
            "week_ending": week_ending,
            "total_won_lost": total_won_lost,
            "total_vig": total_vig,
            "total_net": total_net,
            "player_count": len(results),
        }
    finally:
        await db.close()
