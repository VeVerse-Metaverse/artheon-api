from __future__ import annotations

import datetime
from typing import Optional

from app.schemas.config import CamelCaseModel
from app.schemas.user import UserRef


class LikableBase(CamelCaseModel):
    pass


class Likable(LikableBase):
    value: Optional[int] = False
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    user_id: Optional[str] = None
    user: Optional[UserRef] = None
    entity_id: Optional[str] = None

    class Config:
        orm_mode = True


class LikeRef(LikableBase):
    value: Optional[int] = False
    user: Optional[UserRef] = None

    class Config:
        orm_mode = True


class DislikeRef(LikableBase):
    value: Optional[int] = False

    class Config:
        orm_mode = True


Likable.update_forward_refs()
