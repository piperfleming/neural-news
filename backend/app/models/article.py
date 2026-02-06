"""News article model aligned with frontend expectations."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, Text, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY

from app.models.base import Base


class Article(Base):
    __tablename__ = "articles"

    # Core fields
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    url = Column(Text, nullable=False)
    org = Column(String(255), nullable=False)
    org_initials = Column(String(10), nullable=False)
    logo_url = Column(Text, nullable=True)
    summary = Column(Text, nullable=False)
    date = Column(String(20), nullable=False)
    author = Column(String(255), nullable=False)
    tags = Column(ARRAY(String), default=list, nullable=False)

    # AI-generated metadata (nullable — seeded articles won't have these)
    sentiment = Column(String(50), nullable=True)
    sentiment_score = Column(Float, nullable=True)
    keywords = Column(ARRAY(String), default=list, nullable=True)
    bias_rating = Column(String(50), nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("url", name="uq_article_url"),
    )
