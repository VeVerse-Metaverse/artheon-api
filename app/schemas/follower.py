import datetime
from typing import Optional

from app.schemas import UserRef
from app.schemas.config import CamelCaseModel


class FollowerRef(CamelCaseModel):
    created_at: Optional[datetime.datetime] = None
    user: Optional[UserRef] = None
    target: Optional[UserRef] = None

    class Config:
        orm_mode = True
