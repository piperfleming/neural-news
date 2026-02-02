"""Pydantic schemas for Article validation and serialization."""
from pydantic import BaseModel, ConfigDict


class ArticleBase(BaseModel):
    """Shared fields for article schemas."""
    title: str
    content: str


class ArticleCreate(ArticleBase):
    """Schema for creating a new article."""
    pass


class ArticleUpdate(BaseModel):
    """Schema for updating an article. All fields optional."""
    title: str | None = None
    content: str | None = None


class ArticleResponse(ArticleBase):
    """Schema for article responses (includes id)."""
    id: int

    model_config = ConfigDict(from_attributes=True)
