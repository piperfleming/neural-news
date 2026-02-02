"""FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db

from app.routers import articles


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

app.include_router(articles.router, prefix="/articles", tags=["articles"])


@app.get("/")
async def root():
    return {"message": "Team 15 API", "docs": "/docs"}
