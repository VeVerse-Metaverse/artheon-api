# Update properties
from typing import Optional

from app.schemas.config import CamelCaseModel


class Tag(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None

    class Config:
        orm_mode = True


class TagRef(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None

    class Config:
        orm_mode = True
