import datetime
from typing import Optional, Any, List

from app.schemas import UserRef, Accessible, FileRef
from app.schemas.config import CamelCaseModel
from app.schemas.entity import Entity, EntityRef


class CollectionBase(CamelCaseModel):
    name: str
    # summary: Optional[str] = None
    description: Optional[str] = None

    # tags: Optional[str] = None
    # map: Optional[str] = None

    class Config:
        orm_mode = True


# Create properties
class CollectionCreate(CollectionBase):
    public: Optional[bool] = True
    pass


# Update properties
class CollectionUpdate(CollectionBase):
    pass


# Api properties
class Collection(CollectionBase, Entity):
    entity_type = 'collection'
    object_count: int = None


class CollectionRef(CamelCaseModel):
    id: str
    created_at: datetime.datetime
    name: str
    description: Optional[str] = None
    owner: Optional[UserRef] = None
    files: Optional[List[FileRef]] = []

    class Config:
        orm_mode = True


class CollectionRefNoOwner(CamelCaseModel):
    id: str
    created_at: datetime.datetime
    name: str
    description: Optional[str] = None

    class Config:
        orm_mode = True
