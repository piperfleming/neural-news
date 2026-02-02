"""CRUD endpoints for news articles."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.article import Article
from app.schemas.article import ArticleCreate, ArticleUpdate, ArticleResponse

router = APIRouter()


@router.get("", response_model=list[ArticleResponse])
async def list_articles(
    db: AsyncSession = Depends(get_db),
    category: str | None = Query(None, description="Filter by category"),
    tag: str | None = Query(None, description="Filter by tag"),
    region: str | None = Query(None, description="Filter by region"),
    sentiment: str | None = Query(None, description="Filter by sentiment"),
):
    """Return all news articles, optionally filtered."""
    query = select(Article)

    if category:
        query = query.where(Article.category == category)
    if tag:
        query = query.where(Article.tags.contains([tag]))
    if region:
        query = query.where(Article.region == region)
    if sentiment:
        query = query.where(Article.sentiment == sentiment)

    result = await db.execute(query)
    return result.scalars().all()


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
