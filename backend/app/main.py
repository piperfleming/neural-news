"""FastAPI application entrypoint."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db

from app.routers import articles, auth, buzz, users

# Project root is one level above backend/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB (create tables if needed)."""
    await init_db()
    yield


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
app.include_router(buzz.router, prefix="/api/buzz", tags=["buzz"])


@app.get("/")
async def root():
    """Serve the frontend."""
    return FileResponse(PROJECT_ROOT / "index.html")


@app.get("/account")
async def account_page():
    """Serve the auth / account page."""
    return FileResponse(PROJECT_ROOT / "auth.html")


# Serve only the static/ directory (logo, assets) — not the whole project root
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")
