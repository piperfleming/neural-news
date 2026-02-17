"""User profile and preferences endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.article import Article
from app.models.saved_article import SavedArticle
from app.models.user import User
from app.schemas.article import ArticleResponse
from app.schemas.user import PreferencesResponse, UserResponse, UserUpdate

router = APIRouter()


@router.put("/me", response_model=UserResponse)
async def update_profile(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    await db.flush()
    await db.refresh(current_user)
    return current_user


@router.get("/me/preferences", response_model=PreferencesResponse)
async def get_preferences(current_user: User = Depends(get_current_user)):
    return PreferencesResponse(preferred_tags=current_user.preferred_tags)


# ---------------------------------------------------------------------------
# Saved articles
# ---------------------------------------------------------------------------

@router.get("/me/saved/ids")
async def get_saved_article_ids(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return IDs of articles saved by the current user (for feed UI state)."""
    result = await db.execute(
        select(SavedArticle.article_id).where(SavedArticle.user_id == current_user.id)
    )
    ids = [row[0] for row in result.all()]
    return {"article_ids": ids}


@router.get("/me/saved")
async def get_saved_articles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all articles saved by the current user."""
    result = await db.execute(
        select(Article)
        .join(SavedArticle, SavedArticle.article_id == Article.id)
        .where(SavedArticle.user_id == current_user.id)
        .order_by(SavedArticle.article_id)
    )
    rows = result.scalars().all()
    articles = [ArticleResponse.model_validate(row).model_dump() for row in rows]
    return {"count": len(articles), "articles": articles}


@router.post("/me/saved/{article_id}", status_code=201)
async def save_article(
    article_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save an article for the current user."""
    article_result = await db.execute(select(Article).where(Article.id == article_id))
    if not article_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Article not found")

    existing = await db.execute(
        select(SavedArticle).where(
            SavedArticle.user_id == current_user.id,
            SavedArticle.article_id == article_id,
        )
    )
    if existing.scalar_one_or_none():
        return {"saved": True, "article_id": article_id}

    saved = SavedArticle(user_id=current_user.id, article_id=article_id)
    db.add(saved)
    await db.flush()
    return {"saved": True, "article_id": article_id}


@router.delete("/me/saved/{article_id}", status_code=204)
async def unsave_article(
    article_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove an article from the current user's saved list."""
    result = await db.execute(
        select(SavedArticle).where(
            SavedArticle.user_id == current_user.id,
            SavedArticle.article_id == article_id,
        )
    )
    saved = result.scalar_one_or_none()
    if saved:
        await db.delete(saved)
