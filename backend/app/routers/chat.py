"""Ask Buzz chat endpoint."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.chat_service import answer_question

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    history: list[dict] = []


@router.post("/ask")
async def ask_buzz(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Answer a user question as Buzz, using briefing context + article search."""
    try:
        return await answer_question(payload.question, payload.history, user, db)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Buzz could not answer: {exc}")
