"""Session-based authentication for the app."""
import uuid
from datetime import datetime, timedelta
from passlib.hash import bcrypt
from fastapi import Request, HTTPException


def hash_password(plain: str) -> str:
    return bcrypt.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.verify(plain, hashed)


async def create_session(db, user_id: int) -> str:
    """Create a new session and return the session token."""
    session_id = str(uuid.uuid4())
    expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
    await db.execute(
        "INSERT INTO sessions (id, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (session_id, user_id, datetime.utcnow().isoformat(), expires),
    )
    await db.commit()
    return session_id


async def get_current_user(request: Request, db):
    """Validate session cookie and return user dict or None."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None
    row = await db.execute(
        "SELECT s.user_id, s.expires_at, u.username FROM sessions s "
        "JOIN users u ON u.id = s.user_id WHERE s.id = ?",
        (session_id,),
    )
    row = await row.fetchone()
    if not row:
        return None
    if datetime.fromisoformat(row[1]) < datetime.utcnow():
        await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await db.commit()
        return None
    return {"id": row[0], "username": row[2]}


async def require_auth(request: Request, db):
    """Raise 401 if not authenticated."""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
