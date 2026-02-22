"""Pydantic schemas for briefing endpoints."""

from typing import Literal

from pydantic import BaseModel


class BriefingAdjustDetailIn(BaseModel):
    action: Literal["more_detail", "more_concise"]
