"""User profile and preferences endpoints."""
import asyncio
from datetime import date
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, is_admin_user
from app.models.article import Article
from app.models.saved_article import SavedArticle
from app.models.user import User
from app.models.user_article import UserArticle
from app.schemas.article import ArticleIngestRequest, ArticleResponse
from app.schemas.user import PreferencesResponse, UserResponse, UserUpdate
from app.services.article_extractor import extract_article
from app.services.llm_service import analyze_article

router = APIRouter()


def _user_article_to_dict(ua: UserArticle) -> dict:
    """Convert UserArticle to article-like dict for frontend."""
    return {
        "id": ua.id,
        "title": ua.title,
        "content": ua.content,
        "url": ua.url,
        "org": ua.org,
        "org_initials": ua.org_initials,
        "logo_url": ua.logo_url,
        "summary": ua.summary,
        "date": ua.date,
        "author": ua.author,
        "tags": ua.tags or [],
        "created_at": ua.created_at,
    }


@router.put("/me", response_model=UserResponse)
async def update_profile(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    update_data = payload.model_dump(exclude_unset=True)
    if "role" in update_data and not is_admin_user(current_user):
        update_data.pop("role")
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
    """Return all articles saved by the current user (from user_articles, never expire)."""
    # Migrate legacy saved_articles: copy to user_articles if not already there
    legacy = await db.execute(
        select(Article, SavedArticle.article_id)
        .join(SavedArticle, SavedArticle.article_id == Article.id)
        .where(SavedArticle.user_id == current_user.id)
    )
    for article, feed_id in legacy.all():
        existing = await db.execute(
            select(UserArticle).where(
                UserArticle.user_id == current_user.id,
                UserArticle.feed_article_id == feed_id,
            )
        )
        if not existing.scalar_one_or_none():
            ua = UserArticle(
                user_id=current_user.id,
                feed_article_id=feed_id,
                source="feed",
                title=article.title,
                content=article.content,
                url=article.url,
                org=article.org,
                org_initials=article.org_initials,
                logo_url=article.logo_url,
                summary=article.summary,
                date=article.date,
                author=article.author,
                tags=article.tags or [],
            )
            db.add(ua)

    await db.flush()

    result = await db.execute(
        select(UserArticle)
        .where(UserArticle.user_id == current_user.id)
        .order_by(UserArticle.created_at.desc())
    )
    rows = result.scalars().all()
    articles = [_user_article_to_dict(row) for row in rows]
    return {"count": len(articles), "articles": articles}


@router.post("/me/saved/ingest", status_code=201)
async def ingest_to_saved(
    payload: ArticleIngestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add an article from URL to the user's saved list. Private, does not appear on main feed."""
    url = payload.url.strip()

    existing = await db.execute(
        select(UserArticle).where(
            UserArticle.user_id == current_user.id,
            UserArticle.url == url,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="You have already saved this article.")

    try:
        extracted = await asyncio.to_thread(extract_article, url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    try:
        analysis = await analyze_article(extracted.title, extracted.text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {exc}")

    domain = urlparse(url).netloc.replace("www.", "")
    org = extracted.source or domain
    org_initials = "".join(word[0].upper() for word in org.split()[:3])

    ua = UserArticle(
        user_id=current_user.id,
        feed_article_id=None,
        source="url",
        title=extracted.title,
        content=extracted.text,
        url=url,
        org=org,
        org_initials=org_initials,
        logo_url=f"https://www.google.com/s2/favicons?domain={domain}&sz=128",
        summary=analysis.summary,
        date=extracted.date or date.today().isoformat(),
        author=extracted.author or "Unknown",
        tags=analysis.tags,
    )
    db.add(ua)
    await db.flush()
    await db.refresh(ua)

    return _user_article_to_dict(ua)


@router.post("/me/saved/{article_id}", status_code=201)
async def save_article(
    article_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save an article from the feed. Copies to user_articles so it never expires."""
    article = (await db.execute(select(Article).where(Article.id == article_id))).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    existing_ua = await db.execute(
        select(UserArticle).where(
            UserArticle.user_id == current_user.id,
            UserArticle.feed_article_id == article_id,
        )
    )
    if existing_ua.scalar_one_or_none():
        return {"saved": True, "article_id": article_id}

    ua = UserArticle(
        user_id=current_user.id,
        feed_article_id=article_id,
        source="feed",
        title=article.title,
        content=article.content,
        url=article.url,
        org=article.org,
        org_initials=article.org_initials,
        logo_url=article.logo_url,
        summary=article.summary,
        date=article.date,
        author=article.author,
        tags=article.tags or [],
    )
    db.add(ua)

    saved = SavedArticle(user_id=current_user.id, article_id=article_id)
    db.add(saved)

    await db.flush()
    return {"saved": True, "article_id": article_id}


@router.delete("/me/saved/{user_article_id}", status_code=204)
async def unsave_article(
    user_article_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove an article from the current user's saved list (by user_article id)."""
    ua = (
        await db.execute(
            select(UserArticle).where(
                UserArticle.id == user_article_id,
                UserArticle.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not ua:
        raise HTTPException(status_code=404, detail="Saved article not found")

    if ua.feed_article_id:
        saved = (
            await db.execute(
                select(SavedArticle).where(
                    SavedArticle.user_id == current_user.id,
                    SavedArticle.article_id == ua.feed_article_id,
                )
            )
        ).scalar_one_or_none()
        if saved:
            await db.delete(saved)

    await db.delete(ua)
