"""LLM service for article analysis via OpenAI."""
import json
import logging

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import settings
from app.constants import VALID_TAGS

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.openai_api_key)

SYSTEM_PROMPT = (
    "You are an AI news analyst. Analyze the given article and return a JSON object "
    "with exactly these fields:\n\n"
    "{\n"
    '  "summary": "2-3 sentence summary of the article for a professional audience",\n'
    '  "tags": ["tag1", "tag2"],\n'
    '  "sentiment": "positive" | "negative" | "neutral" | "mixed",\n'
    '  "sentiment_score": 0.0 to 1.0 (0=very negative, 0.5=neutral, 1=very positive),\n'
    '  "keywords": ["keyword1", "keyword2", ...] (5-8 key terms/phrases),\n'
    '  "bias_rating": "left" | "center-left" | "center" | "center-right" | "right" | "neutral"\n'
    "}\n\n"
    'For "tags", select ONLY from this list: '
    + json.dumps(VALID_TAGS)
    + "\n"
    "Select 1-3 tags that best match the article's topic.\n\n"
    "Return ONLY valid JSON, no markdown fences or extra text."
)

# Maximum characters of article text to send to the LLM
MAX_ARTICLE_CHARS = 8000


class ArticleAnalysis(BaseModel):
    """Structured response from LLM analysis."""

    summary: str
    tags: list[str]
    sentiment: str
    sentiment_score: float
    keywords: list[str]
    bias_rating: str


async def analyze_article(title: str, text: str) -> ArticleAnalysis:
    """Send article to OpenAI and get structured analysis back.

    Uses a single API call with JSON mode for all AI fields
    (summary, tags, sentiment, sentiment_score, keywords, bias_rating).

    Args:
        title: The article title.
        text: The article body text.

    Returns:
        ArticleAnalysis with all AI-generated fields.

    Raises:
        Exception: If the OpenAI API call fails or returns invalid JSON.
    """
    user_message = f"Article title: {title}\n\nArticle text:\n{text[:MAX_ARTICLE_CHARS]}"

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    raw = json.loads(response.choices[0].message.content)

    # Validate tags — only allow known tags
    raw["tags"] = [t for t in raw.get("tags", []) if t in VALID_TAGS]

    # Clamp sentiment_score to [0, 1]
    score = raw.get("sentiment_score", 0.5)
    raw["sentiment_score"] = max(0.0, min(1.0, float(score)))

    logger.info("LLM analysis complete: tags=%s, sentiment=%s", raw["tags"], raw.get("sentiment"))

    return ArticleAnalysis(**raw)
