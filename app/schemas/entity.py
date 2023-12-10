import datetime
from typing import Optional, List, Generic, TypeVar

from pydantic import BaseModel
from pydantic.generics import GenericModel

from app.schemas.accessible import AccessibleRef
from app.schemas.comment import CommentRef
from app.schemas.config import CamelCaseModel
from app.schemas.property import PropertyRef
from app.schemas.file import FileRef
from app.schemas.likable import LikeRef


class EntityBase(CamelCaseModel):
    id: Optional[str] = None
    public: Optional[bool] = False


class Entity(EntityBase):
    entity_type: Optional[str] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    views: Optional[int] = 0

    likables: Optional[List[LikeRef]] = []
    comments: Optional[List[CommentRef]] = []
    accessibles: Optional[List[AccessibleRef]] = []
    files: Optional[List[FileRef]] = []
    properties: Optional[List[PropertyRef]] = []

    class Config:
        orm_mode = True


class EntityCreate(EntityBase):
    pass


class EntityUpdate(EntityBase):
    pass


# Represents user reference without private user data
class EntityRef(CamelCaseModel):
    id: Optional[str] = None
    entity_type: str = 'entity'
    views: Optional[int] = None
    public: Optional[bool] = False

    class Config:
        orm_mode = True


RefSchemaType = TypeVar("RefSchemaType", bound=BaseModel)


class EntityBatch(GenericModel, CamelCaseModel, Generic[RefSchemaType]):
    entities: List[RefSchemaType] = []
    offset: int = 0
    limit: int = 0
    total: int = 0

    class Config:
        orm_mode = True


class EntityBatchLiked(GenericModel, CamelCaseModel, Generic[RefSchemaType]):
    entities: List[RefSchemaType] = []
    offset: int = 0
    limit: int = 0
    total: int = 0
    liked: bool = False

    class Config:
        orm_mode = True


class EntityTotal(GenericModel, CamelCaseModel):
    total: int = 0

    class Config:
        orm_mode = True


class EntityTotalDisliked(GenericModel, CamelCaseModel):
    total: int = 0
    disliked: bool = False

    class Config:
        orm_mode = True
