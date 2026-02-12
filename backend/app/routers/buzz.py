"""Trending social buzz endpoint."""
import asyncio

from fastapi import APIRouter, HTTPException, Query

from app.services.social_buzz_service import generate_buzz_summary, search_social_discussions

router = APIRouter()


@router.get("")
async def get_buzz(
    topics: str | None = Query(None, description="Comma-separated topics to search for"),
):
    """Return trending AI social buzz summarized by LLM.

    Searches social media (Reddit, Twitter, LinkedIn) for recent AI discussions,
    then uses OpenAI to summarize the trending topics.
    """
    topic_list = None
    if topics:
        topic_list = [t.strip() for t in topics.split(",") if t.strip()]

    try:
        social_results = await asyncio.to_thread(search_social_discussions, topic_list)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Social search failed: {exc}")

    if not social_results:
        return {"topics": []}

    try:
        buzz = await generate_buzz_summary(social_results)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM summarization failed: {exc}")

    return buzz
