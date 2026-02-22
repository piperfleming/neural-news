"""User-added or saved articles — private to each user, never expire."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY

from app.models.base import Base


class UserArticle(Base):
    """Articles added via URL or saved from feed. Stored per-user, persist indefinitely."""
    __tablename__ = "user_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    feed_article_id = Column(Integer, ForeignKey("articles.id", ondelete="SET NULL"), nullable=True)
    source = Column(String(20), nullable=False)  # 'url' | 'feed'

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

    created_at = Column(DateTime, nullable=False, server_default=func.now())
