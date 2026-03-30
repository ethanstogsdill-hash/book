"""FastAPI application with lifespan, auth middleware, and static file serving."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.database import init_db
from app.routers import auth, dashboard, players, sub_agents, bets, weeks, settlements, scrape, settings_router, activity

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    print("[STARTUP] Database initialized")

    # Start background scheduler
    try:
        from app.services.scheduler import start_scheduler
        await start_scheduler()
        print("[STARTUP] Scheduler started")
    except Exception as e:
        print(f"[STARTUP] Scheduler failed to start: {e}")

    yield

    # Shutdown
    try:
        from app.services.scheduler import stop_scheduler
        await stop_scheduler()
    except Exception:
        pass


app = FastAPI(title="Sportsbook Manager", lifespan=lifespan)

# Register routers
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(players.router)
app.include_router(sub_agents.router)
app.include_router(bets.router)
app.include_router(weeks.router)
app.include_router(settlements.router)
app.include_router(scrape.router)
app.include_router(settings_router.router)
app.include_router(activity.router)


@app.get("/api/telegram/test")
async def telegram_test(request: Request):
    from app.auth import require_auth
    from app import database as db_mod
    from app.services.telegram import send_test_message
    db = await db_mod.get_db()
    try:
        await require_auth(request, db)
    finally:
        await db.close()
    ok = await send_test_message()
    if ok:
        return {"ok": True}
    return {"error": "Failed to send. Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env"}


# Static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def login_page():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/dashboard")
async def dashboard_page():
    return FileResponse(str(STATIC_DIR / "dashboard.html"))


@app.exception_handler(401)
async def auth_exception_handler(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    return FileResponse(str(STATIC_DIR / "index.html"))
