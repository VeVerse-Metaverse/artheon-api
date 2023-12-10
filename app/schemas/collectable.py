from typing import Optional

from app.schemas import Object, Collection
from app.schemas.config import CamelCaseModel


class CollectableBase(CamelCaseModel):
    id: Optional[str] = None

    class Config:
        orm_mode = True


# Properties to receive via API upon creation
class CollectableCreate(CollectableBase):
    object_id: Optional[str] = None


# Properties to receive via API on update
class CollectableUpdate(CollectableBase):
    pass


# Additional properties to return via API
class Collectable(CollectableBase):
    collection_id: Optional[str] = None
    object_id: Optional[str] = None
    collection: Optional[Collection] = None
    object: Optional[Object] = None


class CollectableRef(CollectableBase):
    object: Optional[Object] = None
