from typing import Optional

from app.schemas.config import CamelCaseModel


class Subscription(CamelCaseModel):
    id: Optional[str] = None
    email: Optional[str] = None
    platform: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        orm_mode = True


class SubscriptionResponse(CamelCaseModel):
    id: Optional[str] = None

    class Config:
        orm_mode = True
