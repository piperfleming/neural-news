"""Ask Buzz chat service — answers user questions using briefing context + article search."""
import logging
import re
from datetime import date

from openai import AsyncOpenAI
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.article import Article
from app.models.daily_briefing import DailyBriefing
from app.models.user import User

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.openai_api_key)

_STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "are", "from", "have", "want",
    "more", "about", "into", "will", "been", "they", "them", "some", "what",
    "when", "where", "which", "would", "could", "should", "their", "these",
    "there", "than", "then", "also", "just", "only", "very", "well", "but",
    "not", "all", "any", "can", "its", "our", "you", "your", "how", "why",
    "who", "was", "has", "had", "did", "like", "get", "make", "see", "use",
}


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords (≥4 chars, non-stop) from free-form text."""
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    return [w for w in words if w not in _STOP_WORDS]


async def answer_question(
    question: str,
    history: list[dict],
    user: User,
    db: AsyncSession,
) -> dict:
    """Answer a user question as Buzz, using today's briefing + relevant articles as context."""

    # 1. Fetch today's briefing (may not exist yet)
    result = await db.execute(
        select(DailyBriefing).where(
            DailyBriefing.user_id == user.id,
            DailyBriefing.briefing_date == date.today(),
        )
    )
    briefing = result.scalar_one_or_none()
    briefing_text = briefing.briefing_text if briefing else ""

    # 2. Keyword-search articles relevant to the question
    keywords = _extract_keywords(question)
    source_articles: list[Article] = []
    if keywords:
        ilike_conditions = [
            or_(Article.title.ilike(f"%{kw}%"), Article.summary.ilike(f"%{kw}%"))
            for kw in keywords
        ]
        rows = await db.execute(
            select(Article)
            .where(or_(*ilike_conditions))
            .order_by(Article.created_at.desc())
            .limit(5)
        )
        source_articles = list(rows.scalars().all())

    # 3. Build system prompt
    tags_str = ", ".join(user.preferred_tags) if user.preferred_tags else "general AI topics"
    role_str = user.role or "reader"
    briefing_snippet = briefing_text[:1500] if briefing_text else "No briefing available yet for today."

    article_context = ""
    if source_articles:
        article_context = "\n".join(
            f"- [{a.title}]({a.url}): {(a.summary or '')[:200]}"
            for a in source_articles
        )
    else:
        article_context = "No closely matching articles found."

    system_prompt = (
        "You are Buzz, a friendly and knowledgeable AI news assistant for Neural News. "
        "You're warm, approachable, and genuinely enjoy helping people understand AI. "
        "Be conversational but concise — no fluff, just helpful and clear.\n"
        f"User interests: {tags_str}. Role: {role_str}.\n"
        f"Today's briefing:\n{briefing_snippet}\n\n"
        f"Relevant articles:\n{article_context}\n\n"
        "Answer questions directly and in plain language. Reference article titles naturally when relevant. "
        "If you're not sure about something, say so honestly."
    )

    # 4. Build message list: system + history + new question
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question})

    # 5. Call gpt-4o-mini
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.5,
    )
    answer = response.choices[0].message.content

    # 6. Filter sources to those actually relevant to the answer
    answer_keywords = set(_extract_keywords(answer))
    def _relevance_score(article: Article) -> int:
        haystack = ((article.title or "") + " " + (article.summary or "")).lower()
        return sum(1 for kw in answer_keywords if kw in haystack)

    relevant_articles = sorted(source_articles, key=_relevance_score, reverse=True)
    relevant_articles = [a for a in relevant_articles if _relevance_score(a) > 0]

    sources = [
        {"id": a.id, "title": a.title, "url": a.url, "org": a.org}
        for a in relevant_articles
    ]
    return {"answer": answer, "sources": sources}
