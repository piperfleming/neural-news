"""Pydantic schemas for user metrics endpoints."""

from datetime import datetime

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


class TagMetric(BaseModel):
    tag: str
    clicks: int


class AdminMetricsSummary(BaseModel):
    days: int
    total_users: int
    new_users: int
    active_users_24h: int
    total_sessions: int
    total_active_seconds: int
    total_clicks: int
    top_tags: list[TagMetric]
    top_articles: list[TopArticle]


class AdminUserListItem(BaseModel):
    user_id: int
    name: str
    email: str
    role: str | None
    created_at: datetime
    last_seen_at: datetime | None
    total_sessions: int
    total_active_seconds: int
    total_clicks: int


class AdminUsersResponse(BaseModel):
    days: int
    users: list[AdminUserListItem]


class SessionMetric(BaseModel):
    session_id: str
    started_at: datetime
    last_seen_at: datetime
    ended_at: datetime | None
    active_seconds: int


class AdminUserDetail(BaseModel):
    days: int
    user_id: int
    name: str
    email: str
    role: str | None
    created_at: datetime
    last_seen_at: datetime | None
    total_sessions: int
    total_active_seconds: int
    total_clicks: int
    daily: list[DailyMetric]
    clicks_by_tag: dict[str, int]
    top_articles: list[TopArticle]
    recent_sessions: list[SessionMetric]

