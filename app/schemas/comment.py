from __future__ import annotations

import datetime
from typing import Optional

from app.schemas.config import CamelCaseModel, to_camel
from app.schemas.user import UserRef


class CommentBase(CamelCaseModel):
    pass


class Comment(CommentBase):
    id: Optional[str] = None
    text: Optional[str] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    user_id: Optional[str] = None
    user: Optional[UserRef] = None
    entity_id: Optional[str] = None

    class Config:
        orm_mode = True


class CommentRef(CommentBase):
    id: Optional[str] = None
    text: Optional[str] = None
    entity_id: Optional[str] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    user: Optional[UserRef] = None

    class Config:
        orm_mode = True


class CommentCreate(CamelCaseModel):
    text: Optional[str] = None


class CommentUpdate(CommentBase):
    text: Optional[str] = None


Comment.update_forward_refs()
