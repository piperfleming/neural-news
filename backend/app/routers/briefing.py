"""Daily AI briefing endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.briefing import BriefingAdjustDetailIn
from app.services.briefing_service import (
    adjust_detail_level,
    delete_todays_briefing,
    get_or_create_briefing,
)

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


@router.post("/adjust-detail")
async def adjust_briefing_detail(
    body: BriefingAdjustDetailIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Adjust the detail level of today's briefing (more detail or more concise)."""
    try:
        return await adjust_detail_level(user, db, body.action)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Detail adjustment failed: {exc}")
