import datetime
from typing import Optional, List

from pydantic.main import BaseModel

from app.schemas import UserRef, FileRef, SpaceRef
from app.schemas.config import CamelCaseModel, to_camel
from app.schemas.entity import Entity, EntityRef


class StripeWebHookData(BaseModel):
    data: dict
    type: str


# Create properties
class EventCreate(CamelCaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    public: Optional[bool] = True
    starts_at: Optional[datetime.datetime] = None
    ends_at: Optional[datetime.datetime] = None
    type: Optional[str] = None
    space_id: Optional[str] = None

    class Config:
        orm_mode = True


# Update properties
class EventUpdate(CamelCaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    public: Optional[bool] = True
    starts_at: Optional[datetime.datetime] = None
    ends_at: Optional[datetime.datetime] = None
    space_id: Optional[str] = None

    class Config:
        orm_mode = True


# Api properties
class Event(Entity):
    entity_type = 'event'
    name: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    public: Optional[bool] = True
    starts_at: Optional[datetime.datetime] = None
    ends_at: Optional[datetime.datetime] = None
    price: Optional[float] = None
    active: Optional[bool] = None
    type: Optional[str] = None
    files: Optional[List[FileRef]] = []
    space_id: Optional[str] = None
    space: Optional[SpaceRef] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


class EventRef(EntityRef):
    name: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    public: Optional[bool] = True
    active: Optional[bool] = None
    starts_at: Optional[datetime.datetime] = None
    ends_at: Optional[datetime.datetime] = None
    type: Optional[str] = None
    owner: Optional[UserRef] = None
    files: Optional[List[FileRef]] = []
    space_id: Optional[str] = None
    space: Optional[SpaceRef] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True
