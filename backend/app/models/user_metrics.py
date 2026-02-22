"""Models for user engagement metrics (sessions, clicks, likes)."""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
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


class ArticleLike(Base):
    __tablename__ = "article_likes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    article_id = Column(Integer, ForeignKey("articles.id", ondelete="SET NULL"), nullable=True, index=True)
    article_url = Column(Text, nullable=True)
    tags = Column(ARRAY(String), default=list, nullable=False)
    liked_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)

    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_article_likes_user_article"),
    )


class BriefingFeedback(Base):
    __tablename__ = "briefing_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    briefing_id = Column(Integer, ForeignKey("daily_briefings.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(20), nullable=False)
    detail_level_before = Column(Integer, nullable=False)
    detail_level_after = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)

