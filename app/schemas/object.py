from typing import Optional, List

from app.schemas import UserRef, FileRef, LikeRef
from app.schemas.config import to_camel, CamelCaseModel
from app.schemas.entity import EntityBase, Entity


class ObjectBase(EntityBase):
    pass


# Properties to receive via API upon creation
class ObjectCreate(CamelCaseModel):
    type: Optional[str] = None
    name: Optional[str] = None
    artist: Optional[str] = None
    date: Optional[str] = None
    description: Optional[str] = None
    medium: Optional[str] = None
    width: Optional[float] = None
    height: Optional[float] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    license: Optional[str] = None
    copyright: Optional[str] = None
    credit: Optional[str] = None
    origin: Optional[str] = None
    location: Optional[str] = None
    public: Optional[bool] = True
    dimensions: Optional[str] = None
    scale_multiplier: Optional[float] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


# Properties to receive via API on update
class ObjectUpdate(ObjectBase):
    type: Optional[str] = None
    name: Optional[str] = None
    artist: Optional[str] = None
    date: Optional[str] = None
    description: Optional[str] = None
    medium: Optional[str] = None
    width: Optional[float] = None
    height: Optional[float] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    license: Optional[str] = None
    copyright: Optional[str] = None
    credit: Optional[str] = None
    origin: Optional[str] = None
    location: Optional[str] = None
    dimensions: Optional[str] = None
    scale_multiplier: Optional[float] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


# Additional properties to return via API
class Object(ObjectBase, Entity):
    type: Optional[str] = None
    name: Optional[str] = None
    artist: Optional[str] = None
    date: Optional[str] = None
    description: Optional[str] = None
    medium: Optional[str] = None
    width: Optional[float] = None
    height: Optional[float] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    license: Optional[str] = None
    copyright: Optional[str] = None
    credit: Optional[str] = None
    origin: Optional[str] = None
    location: Optional[str] = None
    public: Optional[bool] = None
    dimensions: Optional[str] = None
    scale_multiplier: Optional[float] = None

    class Config:
        orm_mode = True


class ObjectRef(ObjectBase):
    type: Optional[str] = None
    name: Optional[str] = None
    artist: Optional[str] = None
    date: Optional[str] = None
    description: Optional[str] = None
    medium: Optional[str] = None
    width: Optional[float] = None
    height: Optional[float] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    license: Optional[str] = None
    copyright: Optional[str] = None
    credit: Optional[str] = None
    origin: Optional[str] = None
    location: Optional[str] = None
    owner: Optional[UserRef] = None
    files: Optional[List[FileRef]] = []
    total_likes: Optional[int] = []
    total_dislikes: Optional[int] = []
    dimensions: Optional[str] = None
    scale_multiplier: Optional[float] = None

    class Config:
        orm_mode = True


class ObjectRefNoOwner(ObjectBase):
    type: Optional[str] = None
    name: Optional[str] = None
    artist: Optional[str] = None
    date: Optional[str] = None
    description: Optional[str] = None
    medium: Optional[str] = None
    width: Optional[float] = None
    height: Optional[float] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    license: Optional[str] = None
    copyright: Optional[str] = None
    credit: Optional[str] = None
    origin: Optional[str] = None
    location: Optional[str] = None
    files: Optional[List[FileRef]] = []
    dimensions: Optional[str] = None
    scale_multiplier: Optional[float] = None

    class Config:
        orm_mode = True
