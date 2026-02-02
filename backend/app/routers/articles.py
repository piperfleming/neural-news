"""Read news articles for the frontend."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.article import Article

router = APIRouter()


@router.get("")
async def list_articles(db: AsyncSession = Depends(get_db)):
    """Return all news articles (one per row)."""
    result = await db.execute(select(Article))
    rows = result.scalars().all()
    return [
        {"id": r.id, "title": r.title, "content": r.content}
        for r in rows
    ]
