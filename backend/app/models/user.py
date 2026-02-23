"""User account model."""
from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    preferred_tags = Column(ARRAY(String), default=list, nullable=False)
    role = Column(String(100), nullable=True)
    custom_interests = Column(Text, nullable=True)
    preferred_detail_level = Column(Integer, nullable=True)
    theme_config = Column(JSONB, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
