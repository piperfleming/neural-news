"""CRUD endpoints for news articles."""
import asyncio
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

from ddgs import DDGS

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.article import Article
from app.models.user_metrics import ArticleClick, ArticleLike
from app.schemas.article import (
    ArticleCreate,
    ArticleIngestRequest,
    ArticleUpdate,
    ArticleResponse,
)
from app.services.article_extractor import extract_article
from app.services.llm_service import analyze_article

router = APIRouter()

_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "be", "it", "its",
    "i", "me", "my", "we", "you", "he", "she", "they", "that", "this",
    "how", "what", "when", "where", "who", "which", "more", "about",
}


def _interest_score(article: dict, keywords: list[str]) -> int:
    haystack = " ".join([
        article.get("title") or "",
        article.get("summary") or "",
        " ".join(article.get("tags") or []),
    ]).lower()
    return sum(1 for kw in keywords if kw in haystack)


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
    sort_by_tags: str | None = Query(
        None,
        description="Comma-separated user preferred tags used for relevance sorting",
    ),
    sort_by: str = Query(
        "attention",
        description='Sort order: "attention"/"trending" (trending first) or "recent"',
    ),
    custom_interests: str | None = Query(
        None,
        description="Free-form user interest text for secondary relevance re-ranking",
    ),
):
    """Return all news articles, optionally filtered and sorted.

    Uses OR logic: articles matching ANY of the requested tags are returned.
    *sort_by* controls the base ordering ("attention"/"trending" or "recent").
    When *sort_by_tags* is also provided, articles are further ranked by the
    number of matching preferred tags (descending), with ties preserving the
    base ordering.
    """
    clicks_subquery = (
        select(
            ArticleClick.article_id.label("article_id"),
            func.count(ArticleClick.id).label("click_count"),
        )
        .group_by(ArticleClick.article_id)
        .subquery()
    )
    likes_subquery = (
        select(
            ArticleLike.article_id.label("article_id"),
            func.count(ArticleLike.id).label("like_count"),
        )
        .group_by(ArticleLike.article_id)
        .subquery()
    )
    trending_cutoff = datetime.utcnow() - timedelta(days=1)
    recent_clicks_subquery = (
        select(
            ArticleClick.article_id.label("article_id"),
            func.count(ArticleClick.id).label("recent_click_count"),
        )
        .where(ArticleClick.clicked_at >= trending_cutoff)
        .group_by(ArticleClick.article_id)
        .subquery()
    )
    recent_likes_subquery = (
        select(
            ArticleLike.article_id.label("article_id"),
            func.count(ArticleLike.id).label("recent_like_count"),
        )
        .where(ArticleLike.liked_at >= trending_cutoff)
        .group_by(ArticleLike.article_id)
        .subquery()
    )

    query = (
        select(
            Article,
            func.coalesce(clicks_subquery.c.click_count, 0).label("click_count"),
            func.coalesce(recent_clicks_subquery.c.recent_click_count, 0).label("recent_click_count"),
            func.coalesce(likes_subquery.c.like_count, 0).label("like_count"),
            func.coalesce(recent_likes_subquery.c.recent_like_count, 0).label("recent_like_count"),
        )
        .outerjoin(clicks_subquery, Article.id == clicks_subquery.c.article_id)
        .outerjoin(recent_clicks_subquery, Article.id == recent_clicks_subquery.c.article_id)
        .outerjoin(likes_subquery, Article.id == likes_subquery.c.article_id)
        .outerjoin(recent_likes_subquery, Article.id == recent_likes_subquery.c.article_id)
    )

    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        query = query.where(Article.tags.overlap(tag_list))

    sort_key = sort_by.lower().strip()
    if sort_key == "recent":
        query = query.order_by(Article.created_at.desc())
    else:
        query = query.order_by(
            desc(func.coalesce(recent_likes_subquery.c.recent_like_count, 0)),
            desc(func.coalesce(recent_clicks_subquery.c.recent_click_count, 0)),
            desc(func.coalesce(likes_subquery.c.like_count, 0)),
            desc(func.coalesce(clicks_subquery.c.click_count, 0)),
            Article.created_at.desc(),
        )

    result = await db.execute(query)
    rows = result.all()

    ranked_by_recent_clicks = sorted(
        (
            (
                row[0].id,
                (int(row[4] or 0) * 2) + int(row[2] or 0),
            )
            for row in rows
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    trending_ids = {article_id for article_id, clicks in ranked_by_recent_clicks[:5] if clicks > 0}

    articles = []
    for article, _, _, like_count, _ in rows:
        payload = ArticleResponse.model_validate(article).model_dump()
        payload["is_trending"] = article.id in trending_ids
        payload["like_count"] = int(like_count or 0)
        articles.append(payload)

    if sort_by_tags:
        pref_set = {t.strip() for t in sort_by_tags.split(",") if t.strip()}
        if pref_set:
            articles.sort(
                key=lambda a: -len(pref_set.intersection(a.get("tags", [])))
            )

    if custom_interests:
        keywords = [
            w.lower() for w in custom_interests.split()
            if len(w) > 2 and w.lower() not in _STOP_WORDS
        ]
        if keywords:
            # Supplemental query: fetch articles matching keywords in title/summary
            # that weren't already returned by the tag filter
            existing_ids = {a["id"] for a in articles}
            ilike_conditions = [
                or_(
                    Article.title.ilike(f"%{kw}%"),
                    Article.summary.ilike(f"%{kw}%"),
                )
                for kw in keywords
            ]
            supp_query = (
                select(Article)
                .where(or_(*ilike_conditions))
                .where(Article.id.notin_(existing_ids))
                .order_by(Article.created_at.desc())
                .limit(20)
            )
            supp_rows = (await db.execute(supp_query)).scalars().all()
            supp_articles = []
            for article in supp_rows:
                payload = ArticleResponse.model_validate(article).model_dump()
                payload["is_trending"] = article.id in trending_ids
                payload["like_count"] = 0
                supp_articles.append(payload)

            # Merge, filter to only relevant articles, sort by score descending
            all_articles = articles + supp_articles
            scored = [(a, _interest_score(a, keywords)) for a in all_articles]
            relevant = [a for a, score in scored if score > 0]
            relevant.sort(key=lambda a: -_interest_score(a, keywords))
            # Fall back to full pool if nothing matches (avoids empty feed)
            final = relevant if len(relevant) >= 3 else all_articles
            return {"count": len(final), "articles": final}

    return {"count": len(articles), "articles": articles}


def _ddgs_news_search(query: str, max_results: int) -> list[dict]:
    """Run a DuckDuckGo news search synchronously (called via thread)."""
    try:
        return list(DDGS().news(query, max_results=max_results))
    except Exception:
        return []


@router.get("/live")
async def live_articles(
    interests: str | None = Query(None, description="Free-form interest text"),
    tags: str | None = Query(None, description="Comma-separated preferred tags"),
):
    """Fetch fresh news articles from the web matching the user's interests."""
    _stop = {
        "i", "i'm", "want", "to", "know", "about", "more", "me", "my",
        "show", "focus", "focused", "interested", "in", "please", "the",
        "a", "an", "and", "or", "on", "for", "of", "with", "only", "just",
        "mostly", "some", "get", "see", "read", "find", "keep", "stay",
        "up", "news", "latest", "stuff",
    }

    # Build search queries from interests and tags
    queries: list[str] = []
    if interests:
        keywords = [
            w for w in interests.split()
            if len(w) > 2 and w.lower() not in _stop
        ]
        if keywords:
            queries.append("AI " + " ".join(keywords[:6]))

    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        for tag in tag_list[:2]:
            queries.append(f"AI {tag} news")

    if not queries:
        queries = ["artificial intelligence news"]

    # Run searches in parallel (capped at 2 queries, 6 results each)
    search_tasks = [
        asyncio.to_thread(_ddgs_news_search, q, 6)
        for q in queries[:2]
    ]
    results_nested = await asyncio.gather(*search_tasks, return_exceptions=True)

    # Flatten, deduplicate by URL
    seen_urls: set[str] = set()
    articles = []
    for batch in results_nested:
        if isinstance(batch, Exception) or not batch:
            continue
        for r in batch:
            url = r.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            domain = urlparse(url).netloc.replace("www.", "")
            org = r.get("source") or domain
            org_initials = "".join(w[0].upper() for w in org.split()[:3])
            articles.append({
                "id": abs(hash(url)) % (10 ** 8),
                "title": r.get("title", ""),
                "content": r.get("body", ""),
                "url": url,
                "org": org,
                "org_initials": org_initials,
                "logo_url": f"https://www.google.com/s2/favicons?domain={domain}&sz=128",
                "summary": r.get("body", ""),
                "date": (r.get("date") or "")[:10],
                "author": org,
                "tags": [],
                "is_trending": False,
                "like_count": 0,
                "is_live": True,
            })

    return {"count": len(articles), "articles": articles[:10]}


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
