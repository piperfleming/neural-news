"""Per-article user comments."""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, Text, func

from app.models.base import Base


class ArticleComment(Base):
    __tablename__ = "article_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=True, index=True)
    article_url = Column(Text, nullable=True, index=True)
    comment = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "(article_id IS NOT NULL) OR (article_url IS NOT NULL)",
            name="ck_article_comments_target_present",
        ),
    )
