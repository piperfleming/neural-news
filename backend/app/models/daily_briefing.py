"""Daily AI briefing model — one cached briefing per user per day."""
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY

from app.models.base import Base

DEFAULT_DETAIL_LEVEL = 2


class DailyBriefing(Base):
    __tablename__ = "daily_briefings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    briefing_date = Column(Date, nullable=False)
    briefing_text = Column(Text, nullable=False)
    buzz_snapshot = Column(Text, nullable=True)
    article_ids = Column(ARRAY(Integer), default=list)
    topic_outline = Column(Text, nullable=True)
    detail_level = Column(Integer, nullable=False, default=DEFAULT_DETAIL_LEVEL)
    source_context = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "briefing_date", name="uq_user_briefing_date"),
    )
