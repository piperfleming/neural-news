"""Daily AI briefing service — synthesizes articles + social buzz into a morning briefing."""
import asyncio
import json
import logging
from datetime import date

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.article import Article
from app.models.daily_briefing import DailyBriefing
from app.models.user import User
from app.constants import VALID_TAGS
from app.services.social_buzz_service import search_social_discussions

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.openai_api_key)


async def _summarize_buzz_with_sources(social_results: list[dict]) -> list[dict]:
    """Summarize social results into topics, with each topic citing its source indices."""
    if not social_results:
        return []

    # Number each source so the LLM can cite them
    numbered = social_results[:20]
    snippets = "\n\n".join(
        f"[{i}] [{r['source']}] {r['title']}\n{r['body'][:300]}"
        for i, r in enumerate(numbered)
    )

    prompt = (
        "Given these numbered social media posts about AI, group them into 3-5 trending topics.\n\n"
        "Return a JSON object:\n"
        '{"topics": [{"headline": "...", "summary": "2-3 sentences", '
        '"sentiment": "excited|concerned|divided|curious|skeptical", '
        '"source_indices": [0, 3], "tags": ["tag1"]}]}\n\n'
        "Rules:\n"
        "- source_indices MUST be the [N] numbers of the posts that each topic draws from\n"
        "- Tags must be from: " + json.dumps(VALID_TAGS) + "\n"
        "- Return ONLY valid JSON, no markdown fences\n\n"
        f"Posts:\n{snippets}"
    )

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You summarize social media discussions into trending topics with source citations."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )

    raw = json.loads(response.choices[0].message.content)
    topics = raw.get("topics", [])

    # Map source_indices back to actual links
    for topic in topics:
        topic["tags"] = [t for t in topic.get("tags", []) if t in VALID_TAGS]
        indices = topic.pop("source_indices", [])
        topic["source_links"] = []
        for idx in indices:
            if isinstance(idx, int) and 0 <= idx < len(numbered):
                r = numbered[idx]
                if r.get("href"):
                    topic["source_links"].append({
                        "title": r["title"],
                        "href": r["href"],
                        "source": r["source"],
                    })

    return topics


async def get_or_create_briefing(user: User, db: AsyncSession) -> dict:
    """Return today's briefing for *user*, creating it if it doesn't exist."""

    today = date.today()

    # 1. Check cache
    result = await db.execute(
        select(DailyBriefing).where(
            DailyBriefing.user_id == user.id,
            DailyBriefing.briefing_date == today,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        snapshot = json.loads(existing.buzz_snapshot) if existing.buzz_snapshot else []
        # Handle old format (dict with separate source_links) and new format (list with embedded links)
        if isinstance(snapshot, dict):
            buzz_topics = snapshot.get("topics", [])
        else:
            buzz_topics = snapshot
        return {
            "briefing_text": existing.briefing_text,
            "buzz_topics": buzz_topics,
            "article_ids": existing.article_ids or [],
            "briefing_date": str(existing.briefing_date),
            "is_cached": True,
        }

    # 2. Fetch recent articles matching user's preferred tags
    prefs = user.preferred_tags or []
    article_query = select(Article)
    if prefs:
        article_query = article_query.where(Article.tags.overlap(prefs))
    article_query = article_query.order_by(Article.created_at.desc()).limit(15)
    rows = await db.execute(article_query)
    articles = rows.scalars().all()

    # 3. Fetch social buzz (synchronous library → thread) and summarize with source citations
    buzz_search_topics = [f"AI {tag}" for tag in prefs] if prefs else None
    social_results = await asyncio.to_thread(search_social_discussions, buzz_search_topics)
    buzz_topics = await _summarize_buzz_with_sources(social_results)

    # 4. Build OpenAI prompt
    article_summaries = "\n".join(
        f"- {a.title}: {(a.summary or '')[:200]}" for a in articles
    ) or "No recent articles available."

    buzz_text = "\n".join(
        f"- {t['headline']}: {t['summary']}" for t in buzz_topics
    ) or "No social buzz available."

    tag_desc = ", ".join(prefs) if prefs else "general AI topics"
    role_context = f" They work as a {user.role}." if user.role else ""
    first_name = user.name.split()[0] if user.name else "there"

    prompt = (
        f"Morning briefing for {first_name} (interests: {tag_desc}).{role_context}\n\n"
        f"Write 3-5 paragraphs. Rules:\n"
        f"- Lead with the most important news, not a greeting or preamble\n"
        f"- Be specific: name the companies, models, numbers, and details\n"
        f"- NO filler like \"as someone interested in X, this matters\" — just report the news\n"
        f"- Mention what the online community thinks where relevant (reactions, debates)\n"
        f"- Keep it dense with information, like a smart friend catching you up over coffee\n\n"
        f"ARTICLES:\n{article_summaries}\n\n"
        f"SOCIAL BUZZ:\n{buzz_text}"
    )

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "You write information-dense AI news briefings. No fluff, no generic commentary, "
                "no motivational filler. Just the news, the details, and what people are saying. "
                "Write like a sharp newsletter — every sentence should contain real information."
            )},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    briefing_text = response.choices[0].message.content

    # 5. Persist
    article_id_list = [a.id for a in articles]
    row = DailyBriefing(
        user_id=user.id,
        briefing_date=today,
        briefing_text=briefing_text,
        buzz_snapshot=json.dumps(buzz_topics),
        article_ids=article_id_list,
    )
    db.add(row)
    await db.flush()

    return {
        "briefing_text": briefing_text,
        "buzz_topics": buzz_topics,
        "article_ids": article_id_list,
        "briefing_date": str(today),
        "is_cached": False,
    }


async def delete_todays_briefing(user: User, db: AsyncSession) -> None:
    """Delete today's cached briefing so it can be regenerated."""
    result = await db.execute(
        select(DailyBriefing).where(
            DailyBriefing.user_id == user.id,
            DailyBriefing.briefing_date == date.today(),
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.flush()
