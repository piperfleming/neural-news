"""Saved article association — links users to articles they've saved."""
from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base


class SavedArticle(Base):
    __tablename__ = "saved_articles"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)

    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_user_article"),
    )
