"""Pydantic schemas for user metrics endpoints."""

from pydantic import BaseModel, Field


class HeartbeatIn(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    page_path: str | None = Field(default=None, max_length=255)
    user_agent: str | None = None


class HeartbeatResponse(BaseModel):
    session_id: str
    active_seconds: int


class SessionEndIn(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)


class ArticleClickIn(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    article_id: int | None = None
    article_url: str | None = None
    page_path: str | None = Field(default=None, max_length=255)
    tags: list[str] = Field(default_factory=list)


class DailyMetric(BaseModel):
    date: str
    sessions: int = 0
    active_seconds: int = 0
    clicks: int = 0


class TopArticle(BaseModel):
    article_id: int | None
    title: str | None
    clicks: int


class MetricsSummary(BaseModel):
    days: int
    total_sessions: int
    total_active_seconds: int
    total_clicks: int
    daily: list[DailyMetric]
    clicks_by_tag: dict[str, int]
    top_articles: list[TopArticle]

