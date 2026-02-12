"""Social buzz service: search for trending AI discussions and summarize with LLM."""
import json
import logging

from ddgs import DDGS
from openai import AsyncOpenAI

from app.config import settings
from app.constants import VALID_TAGS

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.openai_api_key)

# Sites to target for social discussions
SOCIAL_SITES = ["reddit.com", "twitter.com", "x.com", "linkedin.com"]

BUZZ_SYSTEM_PROMPT = (
    "You are an AI news analyst summarizing what people are saying on social media "
    "about AI topics. Given a collection of social media post titles and snippets, "
    "produce a JSON object with this exact structure:\n\n"
    "{\n"
    '  "topics": [\n'
    "    {\n"
    '      "headline": "Short catchy headline (max 10 words)",\n'
    '      "summary": "2-3 sentence summary of what people are discussing",\n'
    '      "sentiment": "excited" | "concerned" | "divided" | "curious" | "skeptical",\n'
    '      "sources": ["reddit", "twitter", "linkedin"],\n'
    '      "tags": ["tag1", "tag2"]\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Rules:\n"
    "- Return 3-5 trending topics\n"
    "- Tags must be from: " + json.dumps(VALID_TAGS) + "\n"
    "- Sources should reflect where the discussion was found\n"
    "- Keep headlines punchy and summaries informative\n"
    "- Return ONLY valid JSON, no markdown fences or extra text."
)


def _search_social(query: str, max_results: int = 8) -> list[dict]:
    """Search DuckDuckGo for recent social media discussions."""
    results = []
    try:
        ddgs = DDGS()
        for site in SOCIAL_SITES:
            site_query = f"{query} site:{site}"
            hits = ddgs.text(site_query, max_results=max_results // len(SOCIAL_SITES))
            if hits:
                for r in hits:
                    results.append({
                        "title": r.get("title", ""),
                        "body": r.get("body", ""),
                        "href": r.get("href", ""),
                        "source": site.replace(".com", ""),
                    })
    except Exception as e:
        logger.warning("Social search failed for %r: %s", query, e)
    return results


def search_social_discussions(topics: list[str] | None = None) -> list[dict]:
    """Search for social discussions across AI topics."""
    if not topics:
        topics = ["artificial intelligence", "AI models", "AI policy", "AI safety"]

    all_results = []
    for topic in topics[:4]:
        results = _search_social(topic)
        all_results.extend(results)

    return all_results


async def generate_buzz_summary(social_results: list[dict]) -> dict:
    """Use OpenAI to summarize social media discussions into trending topics."""
    if not social_results:
        return {"topics": []}

    snippets = "\n\n".join(
        f"[{r['source']}] {r['title']}\n{r['body'][:300]}"
        for r in social_results[:20]
    )

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": BUZZ_SYSTEM_PROMPT},
            {"role": "user", "content": f"Social media posts about AI:\n\n{snippets}"},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )

    raw = json.loads(response.choices[0].message.content)

    # Validate tags
    for topic in raw.get("topics", []):
        topic["tags"] = [t for t in topic.get("tags", []) if t in VALID_TAGS]

    logger.info("Buzz summary: %d topics generated", len(raw.get("topics", [])))
    return raw
