"""Models for user engagement metrics (sessions + article clicks)."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY

from app.models.base import Base


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Client-generated (per-tab) ID to correlate events without cookies
    session_id = Column(String(64), nullable=False, unique=True, index=True)

    started_at = Column(DateTime, nullable=False, server_default=func.now())
    last_seen_at = Column(DateTime, nullable=False, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)

    # Best-effort approximation based on heartbeat deltas
    active_seconds = Column(Integer, nullable=False, default=0)

    user_agent = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ArticleClick(Base):
    __tablename__ = "article_clicks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    article_id = Column(Integer, ForeignKey("articles.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(String(64), nullable=False, index=True)

    article_url = Column(Text, nullable=True)
    page_path = Column(String(255), nullable=True)
    tags = Column(ARRAY(String), default=list, nullable=False)

    clicked_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)

