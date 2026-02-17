"""Automated article feed using DuckDuckGo news search."""
import asyncio
import logging
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

from ddgs import DDGS
from sqlalchemy import delete, select

from app.constants import VALID_TAGS
from app.database import async_session_maker
from app.models.article import Article
from app.models.daily_briefing import DailyBriefing
from app.services.article_extractor import extract_article
from app.services.llm_service import analyze_article

logger = logging.getLogger(__name__)

# Search queries derived from VALID_TAGS
_SEARCH_QUERIES = [f"AI {tag}" for tag in VALID_TAGS]

# Max articles to ingest per run (controls LLM costs)
MAX_ARTICLES_PER_RUN = 10


async def refresh_article_feed() -> None:
    """Search DuckDuckGo news for AI articles and ingest new ones."""
    # 1. Collect unique URLs from DDGS news results
    urls: dict[str, str] = {}  # url -> search title (for logging)
    for query in _SEARCH_QUERIES:
        try:
            results = await asyncio.to_thread(DDGS().news, query, max_results=5)
            for r in results:
                url = r.get("url", "")
                if url and url not in urls:
                    urls[url] = r.get("title", "")
        except Exception:
            logger.warning("DDGS search failed for query %r", query, exc_info=True)

        if len(urls) >= MAX_ARTICLES_PER_RUN * 2:
            break

    if not urls:
        logger.info("Feed refresh: no URLs found from DDGS searches")
        return

    ingested = 0
    skipped = 0
    failed = 0

    async with async_session_maker() as session:
        for url in list(urls)[:MAX_ARTICLES_PER_RUN * 2]:
            if ingested >= MAX_ARTICLES_PER_RUN:
                break

            try:
                # Check for existing article
                result = await session.execute(
                    select(Article.id).where(Article.url == url)
                )
                if result.scalar_one_or_none() is not None:
                    skipped += 1
                    continue

                # Extract article content
                extracted = await asyncio.to_thread(extract_article, url)

                # LLM analysis
                analysis = await analyze_article(extracted.title, extracted.text)

                # Derive org/logo metadata (same pattern as /ingest endpoint)
                domain = urlparse(url).netloc.replace("www.", "")
                org = extracted.source or domain
                org_initials = "".join(
                    word[0].upper() for word in org.split()[:3]
                )

                db_article = Article(
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
                    sentiment=analysis.sentiment,
                    sentiment_score=analysis.sentiment_score,
                    keywords=analysis.keywords,
                    bias_rating=analysis.bias_rating,
                )
                session.add(db_article)
                await session.commit()
                ingested += 1
                logger.debug("Ingested: %s", extracted.title)

            except Exception:
                await session.rollback()
                failed += 1
                logger.warning("Failed to ingest %s", url, exc_info=True)

    # Clean up old articles (older than 2 days)
    cutoff = datetime.utcnow() - timedelta(days=2)
    async with async_session_maker() as session:
        result = await session.execute(
            delete(Article).where(Article.created_at < cutoff)
        )
        deleted = result.rowcount
        if deleted:
            logger.info("Cleaned up %d articles older than 2 days", deleted)

        # Clear today's cached briefings so they regenerate with fresh articles + buzz
        if ingested > 0:
            await session.execute(
                delete(DailyBriefing).where(DailyBriefing.briefing_date == date.today())
            )
            logger.info("Cleared cached briefings — will regenerate with new articles")

        await session.commit()

    logger.info(
        "Feed refresh complete: ingested=%d, skipped=%d (duplicate), failed=%d",
        ingested,
        skipped,
        failed,
    )
