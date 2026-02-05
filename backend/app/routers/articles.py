"""CRUD endpoints for news articles."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.article import Article
from app.schemas.article import ArticleCreate, ArticleUpdate, ArticleResponse

router = APIRouter()


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
