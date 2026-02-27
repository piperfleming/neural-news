"""FastAPI application entrypoint."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.services.feed_service import refresh_article_feed

from app.routers import articles, auth, briefing, buzz, chat, metrics, users

logger = logging.getLogger(__name__)

# Frontend directory — set by Docker (FRONTEND_DIR=/frontend) or auto-detected
# for local development (../frontend relative to the backend/ folder).
_BACKEND_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = Path(
    os.environ.get("FRONTEND_DIR", str(_BACKEND_DIR.parent / "frontend"))
)


async def _periodic_feed():
    """Run the article feed on a schedule (every 6 hours)."""
    await asyncio.sleep(10)  # brief delay after startup
    while True:
        try:
            await refresh_article_feed()
        except Exception:
            logger.exception("Feed refresh failed")
        await asyncio.sleep(12 * 3600)  # every 12 hours


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, launch periodic feed task."""
    await init_db()
    task = asyncio.create_task(_periodic_feed())
    yield
    task.cancel()


app = FastAPI(
    title="Team 15 API",
    description="Backend for Neural News (FastAPI + Postgres)",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"] if not settings.debug else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(articles.router, prefix="/api/articles", tags=["articles"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(briefing.router, prefix="/api/briefing", tags=["briefing"])
app.include_router(buzz.router, prefix="/api/buzz", tags=["buzz"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])


@app.get("/")
async def root():
    """Serve the frontend."""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/account")
async def account_page():
    """Serve the auth / account page."""
    return FileResponse(FRONTEND_DIR / "auth.html")


@app.get("/saved")
async def saved_page():
    """Serve the saved articles page."""
    return FileResponse(FRONTEND_DIR / "saved.html")


@app.get("/admin")
async def admin_page():
    """Serve the admin dashboard page."""
    return FileResponse(FRONTEND_DIR / "admin.html")


# Serve the static/ directory inside frontend/ (logo, assets)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")
