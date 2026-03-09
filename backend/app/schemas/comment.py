"""Schemas for article comments."""

from datetime import datetime

from pydantic import BaseModel, Field


class ArticleCommentCreate(BaseModel):
    article_id: int | None = None
    article_url: str | None = None
    comment: str = Field(min_length=1, max_length=1000)


class ArticleCommentResponse(BaseModel):
    id: int
    user_id: int
    user_name: str
    article_id: int | None = None
    article_url: str | None = None
    comment: str
    created_at: datetime
