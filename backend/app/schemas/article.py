"""Pydantic schemas for Article validation and serialization."""
from pydantic import BaseModel, ConfigDict


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


class ArticleCreate(ArticleBase):
    """Schema for creating a new article."""
    pass


class ArticleUpdate(BaseModel):
    """Schema for updating an article. All fields optional."""
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


class ArticleResponse(ArticleBase):
    """Schema for article responses (includes id)."""
    id: int

    model_config = ConfigDict(from_attributes=True)
