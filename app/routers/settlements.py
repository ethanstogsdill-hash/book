"""Settlement endpoints and payday trigger."""
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from app import database as db_mod
from app.auth import require_auth
from app.models import SettlementUpdate

router = APIRouter(prefix="/api/settlements", tags=["settlements"])


@router.get("")
async def list_settlements(request: Request, week_ending: str = None, status: str = None):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        settlements = await db_mod.get_settlements(db, week_ending, status)
        return {"settlements": settlements}
    finally:
        await db.close()


@router.get("/weeks")
async def settlement_weeks(request: Request):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        weeks = await db_mod.get_settlement_weeks(db)
        return {"weeks": weeks}
    finally:
        await db.close()


@router.get("/{settlement_id}")
async def get_settlement(request: Request, settlement_id: int):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        s = await db_mod.get_settlement(db, settlement_id)
        if not s:
            raise HTTPException(status_code=404, detail="Settlement not found")
        return s
    finally:
        await db.close()


@router.patch("/{settlement_id}")
async def update_settlement(request: Request, settlement_id: int, body: SettlementUpdate):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        s = await db_mod.get_settlement(db, settlement_id)
        if not s:
            raise HTTPException(status_code=404, detail="Settlement not found")
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if updates.get("status") == "paid":
            updates["settled_at"] = datetime.utcnow().isoformat()
        await db_mod.update_settlement(db, settlement_id, updates)

        # If marked as paid, send Telegram confirmation
        if updates.get("status") == "paid":
            updated = await db_mod.get_settlement(db, settlement_id)
            if updated and updated["counterparty_type"] == "sub_agent":
                try:
                    from app.services.telegram import send_settlement_confirmation
                    await send_settlement_confirmation(db, updated)
                except Exception as e:
                    print(f"[SETTLEMENT] Telegram notification failed: {e}")

        return {"ok": True}
    finally:
        await db.close()


@router.post("/generate/{week_ending}")
async def generate_settlements(request: Request, week_ending: str):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        from app.services.payday import run_payday
        result = await run_payday(db, week_ending)
        return result
    finally:
        await db.close()


@router.get("/{week_ending}/pdf")
async def download_pdf(request: Request, week_ending: str):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        from app.services.pdf_report import generate_settlement_pdf
        settlements = await db_mod.get_settlements(db, week_ending)
        if not settlements:
            raise HTTPException(status_code=404, detail="No settlements for this week")
        pdf_bytes = generate_settlement_pdf(week_ending, settlements)
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=settlement_{week_ending}.pdf"},
        )
    finally:
        await db.close()


@router.post("/{week_ending}/notify")
async def notify_sub_agents(request: Request, week_ending: str):
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
        settlements = await db_mod.get_settlements(db, week_ending)
        sub_settlements = [s for s in settlements if s["counterparty_type"] == "sub_agent"]
        from app.services.telegram import send_settlement_messages
        sent = await send_settlement_messages(db, sub_settlements)
        return {"ok": True, "sent": sent}
    finally:
        await db.close()
