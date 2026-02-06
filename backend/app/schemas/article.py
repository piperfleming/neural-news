"""Pydantic schemas for Article validation and serialization."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


# --- Display metadata ---

class ArticleDisplayMeta(BaseModel):
    """Fields for article display."""
    author: str | None = None
    source: str | None = None
    source_url: str | None = None
    image_url: str | None = None
    published_at: datetime | None = None


# --- Filtering/search metadata ---

class ArticleFilterMeta(BaseModel):
    """Fields for filtering and search."""
    tags: list[str] = []
    category: str | None = None
    region: str | None = None


# --- AI-generated metadata ---

class ArticleAIMeta(BaseModel):
    """AI-generated analysis fields."""
    summary: str | None = None
    sentiment: str | None = None
    sentiment_score: float | None = None
    keywords: list[str] = []
    bias_rating: str | None = None


# --- Main schemas ---

class ArticleBase(BaseModel):
    """Fields the frontend needs to render an article card."""
    title: str
    content: str
    url: str
    org: str
    org_initials: str
    logo_url: str | None = None
    summary: str
    date: str
    author: str
    tags: list[str] = []


class ArticleCreate(ArticleBase, ArticleDisplayMeta, ArticleFilterMeta):
    """Schema for creating a new article. AI fields are generated later."""
    pass


class ArticleUpdate(BaseModel):
    """Schema for updating an article. All fields optional."""
    # Core
    title: str | None = None
    content: str | None = None
    url: str | None = None
    org: str | None = None
    org_initials: str | None = None
    logo_url: str | None = None
    summary: str | None = None
    date: str | None = None
    author: str | None = None
    tags: list[str] | None = None


class ArticleIngestRequest(BaseModel):
    """Schema for the URL ingest endpoint."""
    url: str


class ArticleResponse(ArticleBase):
    """Article response matching the current DB model."""
    id: int
    created_at: datetime
    updated_at: datetime

    # AI-generated (nullable — older articles won't have these)
    sentiment: str | None = None
    sentiment_score: float | None = None
    keywords: list[str] = []
    bias_rating: str | None = None

    model_config = ConfigDict(from_attributes=True)
