"""CRUD endpoints for news articles."""
import asyncio
from datetime import date
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.article import Article
from app.schemas.article import (
    ArticleCreate,
    ArticleIngestRequest,
    ArticleUpdate,
    ArticleResponse,
)
from app.services.article_extractor import extract_article
from app.services.llm_service import analyze_article

router = APIRouter()


# ---------------------------------------------------------------------------
# Ingest (must be above /{article_id} so FastAPI doesn't match "ingest" as id)
# ---------------------------------------------------------------------------

@router.post("/ingest", response_model=ArticleResponse, status_code=201)
async def ingest_article(
    payload: ArticleIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest an article from a URL.

    1. Check for duplicates (by URL).
    2. Fetch & extract article content with trafilatura.
    3. Analyse with OpenAI (summary, tags, sentiment, keywords, bias).
    4. Save to database and return the new article.
    """

    # 1. Duplicate detection
    existing = await db.execute(
        select(Article).where(Article.url == payload.url)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Article with this URL already exists",
        )

    # 2. Extract article content (synchronous lib → run in thread)
    try:
        extracted = await asyncio.to_thread(extract_article, payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # 3. LLM analysis (single call → structured JSON)
    try:
        analysis = await analyze_article(extracted.title, extracted.text)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"LLM analysis failed: {exc}",
        )

    # 4. Derive org info from metadata or URL domain
    domain = urlparse(payload.url).netloc.replace("www.", "")
    org = extracted.source or domain
    org_initials = "".join(word[0].upper() for word in org.split()[:3])

    # 5. Build and persist Article
    db_article = Article(
        title=extracted.title,
        content=extracted.text,
        url=payload.url,
        org=org,
        org_initials=org_initials,
        logo_url=f"https://www.google.com/s2/favicons?domain={domain}&sz=128",
        summary=analysis.summary,
        date=extracted.date or date.today().isoformat(),
        author=extracted.author or "Unknown",
        tags=analysis.tags,
        # AI metadata
        sentiment=analysis.sentiment,
        sentiment_score=analysis.sentiment_score,
        keywords=analysis.keywords,
        bias_rating=analysis.bias_rating,
    )
    db.add(db_article)
    await db.flush()
    await db.refresh(db_article)
    return db_article


# ---------------------------------------------------------------------------
# Standard CRUD
# ---------------------------------------------------------------------------

@router.get("")
async def list_articles(
    db: AsyncSession = Depends(get_db),
    tags: str | None = Query(None, description="Comma-separated tags to filter by"),
):
    """Return all news articles, optionally filtered by tags.

    Uses OR logic: articles matching ANY of the requested tags are returned.
    Response format: {"count": N, "articles": [...]}
    """
    query = select(Article)

    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        # overlap = OR logic: return articles that have ANY of the requested tags
        query = query.where(Article.tags.overlap(tag_list))

    result = await db.execute(query)
    rows = result.scalars().all()
    articles = [ArticleResponse.model_validate(row).model_dump() for row in rows]
    return {"count": len(articles), "articles": articles}


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    """Return a single article by ID."""
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.post("", response_model=ArticleResponse, status_code=201)
async def create_article(article: ArticleCreate, db: AsyncSession = Depends(get_db)):
    """Create a new article."""
    db_article = Article(**article.model_dump())
    db.add(db_article)
    await db.flush()
    await db.refresh(db_article)
    return db_article


@router.put("/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: int, article: ArticleUpdate, db: AsyncSession = Depends(get_db)
):
    """Update an existing article."""
    result = await db.execute(select(Article).where(Article.id == article_id))
    db_article = result.scalar_one_or_none()
    if not db_article:
        raise HTTPException(status_code=404, detail="Article not found")

    update_data = article.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_article, field, value)

    await db.flush()
    await db.refresh(db_article)
    return db_article


@router.delete("/{article_id}", status_code=204)
async def delete_article(article_id: int, db: AsyncSession = Depends(get_db)):
    """Delete an article."""
    result = await db.execute(select(Article).where(Article.id == article_id))
    db_article = result.scalar_one_or_none()
    if not db_article:
        raise HTTPException(status_code=404, detail="Article not found")

    await db.delete(db_article)
