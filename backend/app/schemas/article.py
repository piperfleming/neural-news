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
    """Core article fields."""
    title: str
    content: str


class ArticleCreate(ArticleBase, ArticleDisplayMeta, ArticleFilterMeta):
    """Schema for creating a new article. AI fields are generated later."""
    pass


class ArticleUpdate(BaseModel):
    """Schema for updating an article. All fields optional."""
    # Core
    title: str | None = None
    content: str | None = None
    # Display
    author: str | None = None
    source: str | None = None
    source_url: str | None = None
    image_url: str | None = None
    published_at: datetime | None = None
    # Filtering
    tags: list[str] | None = None
    category: str | None = None
    region: str | None = None
    # AI
    summary: str | None = None
    sentiment: str | None = None
    sentiment_score: float | None = None
    keywords: list[str] | None = None
    bias_rating: str | None = None


class ArticleResponse(ArticleBase, ArticleDisplayMeta, ArticleFilterMeta, ArticleAIMeta):
    """Full article response with all metadata."""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
