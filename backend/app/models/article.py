"""News article row for the frontend."""
from sqlalchemy import Column, Integer, Text

from app.models.base import Base


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
