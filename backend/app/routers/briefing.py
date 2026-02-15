"""Daily AI briefing endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.briefing_service import delete_todays_briefing, get_or_create_briefing

router = APIRouter()


@router.get("/today")
async def get_today_briefing(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return today's AI briefing for the authenticated user (creates if needed)."""
    try:
        return await get_or_create_briefing(user, db)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Briefing generation failed: {exc}")


@router.post("/refresh")
async def refresh_briefing(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete today's cached briefing and generate a fresh one."""
    try:
        await delete_todays_briefing(user, db)
        return await get_or_create_briefing(user, db)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Briefing refresh failed: {exc}")
