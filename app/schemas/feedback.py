from __future__ import annotations
import datetime
from typing import Optional

from app.schemas.config import CamelCaseModel


class FeedbackBase(CamelCaseModel):
    id: Optional[str] = None


class Feedback(FeedbackBase):
    created_at: Optional[datetime.datetime] = None
    email: Optional[str] = None
    text: Optional[str] = None

    class Config:
        orm_mode = True


class FeedbackCreate(CamelCaseModel):
    email: Optional[str] = None
    text: str = None

    class Config:
        orm_mode = True


class FeedbackUpdate(FeedbackBase):
    pass
