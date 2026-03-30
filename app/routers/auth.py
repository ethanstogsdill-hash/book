"""Authentication endpoints."""
from fastapi import APIRouter, Request, Response, HTTPException
from app import database as db_mod
from app.auth import verify_password, create_session, get_current_user, hash_password
from app.models import LoginRequest, ChangePassword

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(req: LoginRequest, response: Response):
    db = await db_mod.get_db()
    try:
        user = await db_mod.get_user_by_username(db, req.username)
        if not user or not verify_password(req.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        session_id = await create_session(db, user["id"])
        response.set_cookie(
            key="session_id", value=session_id,
            httponly=True, samesite="lax", max_age=30 * 24 * 3600
        )
        return {"ok": True, "username": user["username"]}
    finally:
        await db.close()


@router.post("/logout")
async def logout(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    if session_id:
        db = await db_mod.get_db()
        try:
            await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            await db.commit()
        finally:
            await db.close()
    response.delete_cookie("session_id")
    return {"ok": True}


@router.get("/me")
async def me(request: Request):
    db = await db_mod.get_db()
    try:
        user = await get_current_user(request, db)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return {"username": user["username"]}
    finally:
        await db.close()


@router.post("/change-password")
async def change_password(request: Request, body: ChangePassword):
    db = await db_mod.get_db()
    try:
        user = await get_current_user(request, db)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        full_user = await db_mod.get_user_by_username(db, user["username"])
        if not verify_password(body.current_password, full_user["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        new_hash = hash_password(body.new_password)
        await db_mod.update_user_password(db, user["id"], new_hash)
        return {"ok": True}
    finally:
        await db.close()
