from __future__ import annotations

import datetime
from typing import Optional

from app.schemas.config import CamelCaseModel
from app.schemas.user import UserRef


class AccessibleBase(CamelCaseModel):
    pass


class Accessible(AccessibleBase):
    is_owner: Optional[bool] = False
    can_view: Optional[bool] = False
    can_edit: Optional[bool] = False
    can_delete: Optional[bool] = False
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    entity_id: Optional[str] = None
    user_id: Optional[str] = None
    user: Optional[UserRef] = None

    class Config:
        orm_mode = True


class AccessibleRef(CamelCaseModel):
    is_owner: Optional[bool] = False
    can_view: Optional[bool] = False
    can_edit: Optional[bool] = False
    can_delete: Optional[bool] = False
    user_id: Optional[str] = None
    user: Optional[UserRef] = None

    class Config:
        orm_mode = True


class AccessibleUpdate(AccessibleBase):
    user_id: Optional[str] = None
    can_view: Optional[bool] = False
    can_edit: Optional[bool] = False
    can_delete: Optional[bool] = False


Accessible.update_forward_refs()
