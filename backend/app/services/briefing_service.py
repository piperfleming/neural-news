"""Daily AI briefing service — synthesizes articles + social buzz into a morning briefing."""
import asyncio
import json
import logging
from datetime import date, datetime

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.article import Article
from app.models.daily_briefing import DailyBriefing, DEFAULT_DETAIL_LEVEL
from app.models.user import User
from app.models.user_metrics import BriefingFeedback
from app.constants import VALID_TAGS
from app.services.social_buzz_service import search_social_discussions

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.openai_api_key)

DETAIL_INSTRUCTIONS = {
    1: "For each topic, write the topic name as a ### heading, then exactly ONE bullet point (one sentence, max 20 words) with the single most important fact. Use **bold** for key names. Total output must be under 80 words.",
    2: "For each topic, write the topic name as a ### heading, then 1-2 bullet points underneath covering the most essential facts. Use **bold** for key names and numbers.",
    3: "For each topic, write the topic name as a ### heading, then 2-4 bullet points underneath with key facts and brief context. Use **bold** for names and numbers.",
    4: "For each topic, write the topic name as a ### heading, then 4-6 bullet points underneath with context, details, and who is saying what on social media. Use **bold** for emphasis.",
    5: "For each topic, write the topic name as a ### heading, then a full paragraph (5-7 sentences) with analysis and community reactions. Use **bold** for key names and figures. Reference specific social media posts and figures.",
    6: "For each topic, write the topic name as a ### heading, then 1-2 detailed paragraphs with thorough analysis, numbers, and what specific people are saying on social media. Use **bold** for emphasis on key facts.",
    7: "For each topic, write the topic name as a ### heading, then 2-3 paragraphs as a comprehensive deep-dive with full context, data points, analysis, and community sentiment. Reference specific social media voices and platforms. Use **bold** for key facts and names.",
}

_MAX_TOPICS_BY_LEVEL = {1: 2, 2: 3, 3: 4}  # 4+ shows all topics


async def _summarize_buzz_with_sources(social_results: list[dict]) -> list[dict]:
    """Summarize social results into topics, with each topic citing its source indices."""
    if not social_results:
        return []

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


async def _extract_topic_outline(
    article_summaries: str, buzz_text: str, user: User
) -> list[dict]:
    """Extract a structured topic outline from source material (runs once per briefing)."""
    tag_desc = ", ".join(user.preferred_tags) if user.preferred_tags else "general AI topics"
    custom_ctx = f" Additional focus: {user.custom_interests}." if user.custom_interests else ""

    prompt = (
        f"From the following articles and social buzz about AI (reader interests: {tag_desc}.{custom_ctx}), "
        "identify the 3-5 most important and trending topics.\n\n"
        "Return a JSON object:\n"
        '{"topics": [{"headline": "short headline", '
        '"key_facts": ["fact1", "fact2", "fact3"], '
        '"social_voices": ["@elonmusk on X said ...", "Reddit r/MachineLearning reacted ..."]}]}\n\n'
        "Rules:\n"
        "- Order topics by importance/trendiness\n"
        "- Each topic should have 3-6 key facts (specific names, numbers, details)\n"
        "- social_voices: include 1-4 notable reactions from social media — "
        "name the person/account AND the platform (X/Twitter, Reddit, LinkedIn, etc.). "
        "If no social discussion exists for a topic, use an empty array.\n"
        "- Return ONLY valid JSON, no markdown fences\n\n"
        f"ARTICLES:\n{article_summaries}\n\n"
        f"SOCIAL BUZZ:\n{buzz_text}"
    )

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "You extract structured topic outlines from news and social media sources. "
                "Be specific and factual. Preserve social media context — who said what, on which platform."
            )},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    raw = json.loads(response.choices[0].message.content)
    return raw.get("topics", [])


async def _generate_briefing_at_detail_level(
    topic_outline: list[dict],
    source_context: str,
    detail_level: int,
    user: User,
) -> str:
    """Generate briefing prose at a specific detail level, constrained to the topic outline."""
    max_topics = _MAX_TOPICS_BY_LEVEL.get(detail_level, len(topic_outline))
    topic_outline = topic_outline[:max_topics]
    first_name = user.name.split()[0] if user.name else "there"
    tag_desc = ", ".join(user.preferred_tags) if user.preferred_tags else "general AI topics"
    role_context = f" They work as a {user.role}." if user.role else ""
    custom_ctx = f" They specifically asked: \"{user.custom_interests}\"." if user.custom_interests else ""
    level_instruction = DETAIL_INSTRUCTIONS.get(detail_level, DETAIL_INSTRUCTIONS[DEFAULT_DETAIL_LEVEL])

    prompt = (
        f"Morning briefing for {first_name} (interests: {tag_desc}).{role_context}{custom_ctx}\n\n"
        "Write a briefing covering EXACTLY these topics in this order. "
        "Do NOT add, remove, or reorder topics.\n\n"
        f"TOPICS:\n{json.dumps(topic_outline, indent=2)}\n\n"
        f"DETAIL LEVEL ({detail_level}/7): {level_instruction}\n\n"
        "Rules:\n"
        "- Lead with the most important news, not a greeting or preamble\n"
        "- Be specific: name the companies, models, numbers, and details\n"
        "- NO filler like \"as someone interested in X, this matters\" — just report the news\n"
        "- IMPORTANT: Weave in social media reactions from the topic's social_voices — "
        "name the person/account and platform (e.g. \"Elon Musk posted on X that...\", "
        "\"Reddit's r/MachineLearning is buzzing about...\")\n"
        "- Use **bold** markdown for key names, figures, and important facts\n"
        "- Keep it dense with information\n\n"
        f"SOURCE MATERIAL (use for additional context and details):\n{source_context}"
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
    return response.choices[0].message.content


def _build_source_context(article_summaries: str, buzz_text: str) -> str:
    return f"ARTICLES:\n{article_summaries}\n\nSOCIAL BUZZ:\n{buzz_text}"


def _parse_buzz_snapshot(raw: str | None) -> list[dict]:
    if not raw:
        return []
    snapshot = json.loads(raw)
    if isinstance(snapshot, dict):
        return snapshot.get("topics", [])
    return snapshot


async def _fetch_article_urls(article_ids: list[int], db: AsyncSession) -> list[dict]:
    """Fetch article URLs for the given IDs, preserving order."""
    if not article_ids:
        return []
    result = await db.execute(
        select(Article.id, Article.url).where(Article.id.in_(article_ids))
    )
    url_map = {row.id: row.url for row in result.all()}
    return [{"url": url_map[aid]} for aid in article_ids if aid in url_map]


def _briefing_response(
    row: DailyBriefing,
    buzz_topics: list[dict],
    is_cached: bool,
    articles: list[dict] | None = None,
) -> dict:
    return {
        "briefing_text": row.briefing_text,
        "buzz_topics": buzz_topics,
        "article_ids": row.article_ids or [],
        "articles": articles or [],
        "briefing_date": str(row.briefing_date),
        "detail_level": row.detail_level or DEFAULT_DETAIL_LEVEL,
        "is_cached": is_cached,
    }


async def get_or_create_briefing(user: User, db: AsyncSession) -> dict:
    """Return today's briefing for *user*, creating it if it doesn't exist."""

    today = date.today()

    result = await db.execute(
        select(DailyBriefing).where(
            DailyBriefing.user_id == user.id,
            DailyBriefing.briefing_date == today,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        buzz_topics = _parse_buzz_snapshot(existing.buzz_snapshot)
        article_urls = await _fetch_article_urls(existing.article_ids or [], db)
        return _briefing_response(existing, buzz_topics, is_cached=True, articles=article_urls)

    # Extract keywords from custom_interests for supplemental queries
    _stop = {"a","an","the","and","or","but","in","on","at","to","for","of","with","by","i","want","know","about","more","me","my","show","focus","interested","please"}
    interest_keywords = []
    if user.custom_interests:
        interest_keywords = [
            w.lower() for w in user.custom_interests.split()
            if len(w) > 2 and w.lower() not in _stop
        ]

    # Fetch recent articles matching user's preferred tags
    prefs = user.preferred_tags or []
    article_query = select(Article)
    if prefs:
        article_query = article_query.where(Article.tags.overlap(prefs))
    article_query = article_query.order_by(Article.created_at.desc()).limit(15)
    rows = await db.execute(article_query)
    articles = list(rows.scalars().all())

    # Supplement with keyword-matched articles from custom_interests
    if interest_keywords:
        from sqlalchemy import or_
        existing_ids = {a.id for a in articles}
        ilike_conditions = [
            or_(Article.title.ilike(f"%{kw}%"), Article.summary.ilike(f"%{kw}%"))
            for kw in interest_keywords
        ]
        supp_rows = await db.execute(
            select(Article)
            .where(or_(*ilike_conditions))
            .where(Article.id.notin_(existing_ids))
            .order_by(Article.created_at.desc())
            .limit(5)
        )
        articles.extend(supp_rows.scalars().all())

    # Fetch social buzz and summarize with source citations
    # Put interest keywords FIRST so they're not dropped by the [:4] cap in search_social_discussions
    buzz_search_topics = []
    if interest_keywords:
        buzz_search_topics += [f"AI {kw}" for kw in interest_keywords[:2]]
    buzz_search_topics += [f"AI {tag}" for tag in prefs]
    if not buzz_search_topics:
        buzz_search_topics = None
    social_results = await asyncio.to_thread(search_social_discussions, buzz_search_topics)
    buzz_topics = await _summarize_buzz_with_sources(social_results)

    article_summaries = "\n".join(
        f"- {a.title}: {(a.summary or '')[:200]}" for a in articles
    ) or "No recent articles available."

    buzz_text = "\n".join(
        f"- {t['headline']}: {t['summary']}" for t in buzz_topics
    ) or "No social buzz available."

    source_context = _build_source_context(article_summaries, buzz_text)

    # Two-step generation: extract topics, then write prose
    initial_level = user.preferred_detail_level or DEFAULT_DETAIL_LEVEL
    topic_outline = await _extract_topic_outline(article_summaries, buzz_text, user)
    briefing_text = await _generate_briefing_at_detail_level(
        topic_outline, source_context, initial_level, user,
    )

    article_id_list = [a.id for a in articles]
    row = DailyBriefing(
        user_id=user.id,
        briefing_date=today,
        briefing_text=briefing_text,
        buzz_snapshot=json.dumps(buzz_topics),
        article_ids=article_id_list,
        topic_outline=json.dumps(topic_outline),
        detail_level=initial_level,
        source_context=source_context,
    )
    db.add(row)
    await db.flush()

    article_url_list = [{"url": a.url} for a in articles]
    return _briefing_response(row, buzz_topics, is_cached=False, articles=article_url_list)


async def adjust_detail_level(user: User, db: AsyncSession, action: str) -> dict:
    """Adjust the detail level of today's briefing up or down and regenerate prose."""

    today = date.today()

    result = await db.execute(
        select(DailyBriefing).where(
            DailyBriefing.user_id == user.id,
            DailyBriefing.briefing_date == today,
        )
    )
    existing = result.scalar_one_or_none()
    if not existing:
        raise ValueError("No briefing exists for today. Load the briefing first.")

    current_level = existing.detail_level or DEFAULT_DETAIL_LEVEL
    if action == "more_detail":
        new_level = min(current_level + 1, 7)
    else:
        new_level = max(current_level - 1, 1)

    if new_level == current_level:
        buzz_topics = _parse_buzz_snapshot(existing.buzz_snapshot)
        article_urls = await _fetch_article_urls(existing.article_ids or [], db)
        return _briefing_response(existing, buzz_topics, is_cached=True, articles=article_urls)

    # Log the feedback event
    feedback = BriefingFeedback(
        user_id=user.id,
        briefing_id=existing.id,
        action=action,
        detail_level_before=current_level,
        detail_level_after=new_level,
        created_at=datetime.utcnow(),
    )
    db.add(feedback)

    topic_outline = json.loads(existing.topic_outline) if existing.topic_outline else []
    source_context = existing.source_context or ""

    # If the briefing was created before the topic extraction feature,
    # fall back to a simple rewrite
    if not topic_outline or not source_context:
        topic_outline = topic_outline or []
        source_context = source_context or ""
        logger.warning("Briefing %s missing topic_outline or source_context, regenerating outline", existing.id)
        # Best-effort: extract outline from the existing briefing text
        if not topic_outline:
            topic_outline = await _extract_topic_outline(
                existing.briefing_text, source_context, user,
            )
            existing.topic_outline = json.dumps(topic_outline)

    briefing_text = await _generate_briefing_at_detail_level(
        topic_outline, source_context, new_level, user,
    )

    existing.briefing_text = briefing_text
    existing.detail_level = new_level
    user.preferred_detail_level = new_level
    await db.flush()

    buzz_topics = _parse_buzz_snapshot(existing.buzz_snapshot)
    article_urls = await _fetch_article_urls(existing.article_ids or [], db)
    return _briefing_response(existing, buzz_topics, is_cached=False, articles=article_urls)


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
