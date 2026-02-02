"""News article model with display, filtering, and AI metadata."""
from datetime import datetime

from sqlalchemy import Column, Integer, Text, String, DateTime, Float
from sqlalchemy.dialects.postgresql import ARRAY

from app.models.base import Base


class Article(Base):
    __tablename__ = "articles"

    # Core fields
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)

    # Display metadata
    author = Column(String(255), nullable=True)
    source = Column(String(255), nullable=True)
    source_url = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Filtering/search metadata
    tags = Column(ARRAY(String), default=list, nullable=False)
    category = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)

    # AI-generated metadata
    summary = Column(Text, nullable=True)
    sentiment = Column(String(20), nullable=True)  # e.g., "positive", "negative", "neutral"
    sentiment_score = Column(Float, nullable=True)  # -1.0 to 1.0
    keywords = Column(ARRAY(String), default=list, nullable=False)
    bias_rating = Column(String(50), nullable=True)  # e.g., "left", "center", "right"
