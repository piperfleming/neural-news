"""Automated article feed using DuckDuckGo news search + arXiv research papers."""
import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

import httpx
from ddgs import DDGS
from sqlalchemy import delete, select

from app.constants import VALID_TAGS
from app.database import async_session_maker
from app.models.article import Article
from app.models.daily_briefing import DailyBriefing
from app.services.article_extractor import extract_article
from app.services.llm_service import analyze_article

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DuckDuckGo news search config
# ---------------------------------------------------------------------------
_SEARCH_QUERIES = [f"AI {tag}" for tag in VALID_TAGS]
MAX_ARTICLES_PER_RUN = 10

# ---------------------------------------------------------------------------
# arXiv research-paper config
# ---------------------------------------------------------------------------
ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "stat.ML"]
MAX_PAPERS_PER_RUN = 5
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


async def _fetch_arxiv_papers() -> list[dict]:
    """Return recent AI research papers from arXiv (sorted newest-first)."""
    cat_query = " OR ".join(f"cat:{c}" for c in ARXIV_CATEGORIES)
    params = {
        "search_query": cat_query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": 0,
        "max_results": MAX_PAPERS_PER_RUN * 4,
    }

    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(ARXIV_API_URL, params=params)
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    papers: list[dict] = []

    for entry in root.findall("atom:entry", _ATOM_NS):
        title = (entry.findtext("atom:title", "", _ATOM_NS)
                 .strip().replace("\n", " "))
        abstract = entry.findtext("atom:summary", "", _ATOM_NS).strip()
        published = entry.findtext("atom:published", "", _ATOM_NS)[:10]

        url = ""
        for link in entry.findall("atom:link", _ATOM_NS):
            if link.get("type") == "text/html":
                url = link.get("href", "")
                break
        if not url:
            url = entry.findtext("atom:id", "", _ATOM_NS)

        authors = [
            a.findtext("atom:name", "", _ATOM_NS)
            for a in entry.findall("atom:author", _ATOM_NS)
        ]
        author_str = ", ".join(authors[:5])
        if len(authors) > 5:
            author_str += f" et al. ({len(authors)} authors)"

        if title and abstract and url:
            papers.append({
                "title": title,
                "abstract": abstract,
                "url": url,
                "date": published,
                "authors": author_str,
            })

    return papers


async def _ingest_arxiv_papers(session, *, budget: int = MAX_PAPERS_PER_RUN):
    """Fetch arXiv papers and store ones we haven't seen yet.

    Returns (ingested, skipped, failed) counts.
    """
    ingested = skipped = failed = 0
    try:
        papers = await _fetch_arxiv_papers()
    except Exception:
        logger.warning("arXiv API fetch failed", exc_info=True)
        return ingested, skipped, failed

    for paper in papers:
        if ingested >= budget:
            break

        url = paper["url"]
        try:
            dup = await session.execute(
                select(Article.id).where(Article.url == url)
            )
            if dup.scalar_one_or_none() is not None:
                skipped += 1
                continue

            analysis = await analyze_article(paper["title"], paper["abstract"])

            db_article = Article(
                title=paper["title"],
                content=paper["abstract"],
                url=url,
                org="arXiv",
                org_initials="arXiv",
                logo_url="https://www.google.com/s2/favicons?domain=arxiv.org&sz=128",
                summary=analysis.summary,
                date=paper["date"] or date.today().isoformat(),
                author=paper["authors"] or "Unknown",
                tags=analysis.tags,
                sentiment=analysis.sentiment,
                sentiment_score=analysis.sentiment_score,
                keywords=analysis.keywords,
                bias_rating=analysis.bias_rating,
            )
            session.add(db_article)
            await session.commit()
            ingested += 1
            logger.debug("Ingested arXiv paper: %s", paper["title"])

        except Exception:
            await session.rollback()
            failed += 1
            logger.warning("Failed to ingest arXiv paper %s", url, exc_info=True)

    return ingested, skipped, failed


async def refresh_article_feed() -> None:
    """Search DuckDuckGo news + arXiv for AI articles and ingest new ones."""
    # ----- Phase 1: DuckDuckGo news -----
    urls: dict[str, str] = {}
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

    news_ingested = 0
    news_skipped = 0
    news_failed = 0

    if urls:
        async with async_session_maker() as session:
            for url in list(urls)[:MAX_ARTICLES_PER_RUN * 2]:
                if news_ingested >= MAX_ARTICLES_PER_RUN:
                    break

                try:
                    result = await session.execute(
                        select(Article.id).where(Article.url == url)
                    )
                    if result.scalar_one_or_none() is not None:
                        news_skipped += 1
                        continue

                    extracted = await asyncio.to_thread(extract_article, url)
                    analysis = await analyze_article(extracted.title, extracted.text)

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
                    news_ingested += 1
                    logger.debug("Ingested: %s", extracted.title)

                except Exception:
                    await session.rollback()
                    news_failed += 1
                    logger.warning("Failed to ingest %s", url, exc_info=True)
    else:
        logger.info("Feed refresh: no URLs found from DDGS searches")

    # ----- Phase 2: arXiv research papers -----
    async with async_session_maker() as session:
        arxiv_ingested, arxiv_skipped, arxiv_failed = await _ingest_arxiv_papers(session)

    total_ingested = news_ingested + arxiv_ingested

    # ----- Cleanup -----
    cutoff = datetime.utcnow() - timedelta(days=2)
    async with async_session_maker() as session:
        result = await session.execute(
            delete(Article).where(Article.created_at < cutoff)
        )
        deleted = result.rowcount
        if deleted:
            logger.info("Cleaned up %d articles older than 2 days", deleted)

        if total_ingested > 0:
            await session.execute(
                delete(DailyBriefing).where(DailyBriefing.briefing_date == date.today())
            )
            logger.info("Cleared cached briefings — will regenerate with new articles")

        await session.commit()

    logger.info(
        "Feed refresh complete: news=%d (skip=%d, fail=%d), "
        "arxiv=%d (skip=%d, fail=%d)",
        news_ingested, news_skipped, news_failed,
        arxiv_ingested, arxiv_skipped, arxiv_failed,
    )
