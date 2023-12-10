from typing import Optional, List

from app.schemas import UserRef, ModRef
from app.schemas.config import CamelCaseModel, to_camel
from app.schemas.entity import Entity, EntityBase
from app.schemas.placeable import PlaceableRef


class SpaceBase(EntityBase):
    name: Optional[str] = None
    description: Optional[str] = None
    map: Optional[str] = None
    mod_id: Optional[str] = None
    mod: Optional[ModRef] = None
    type: Optional[str] = None
    game_mode: Optional[str] = None

    class Config:
        orm_mode = True


# Create properties
class SpaceCreate(CamelCaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    map: Optional[str] = None
    public: Optional[bool] = True
    mod_id: Optional[str] = None
    type: Optional[str] = None
    game_mode: Optional[str] = None

    class Config:
        orm_mode = True


# Update properties
class SpaceUpdate(CamelCaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    map: Optional[str] = None
    mod_id: Optional[str] = None
    type: Optional[str] = None
    game_mode: Optional[str] = None

    class Config:
        orm_mode = True


# Api properties
class Space(SpaceBase, Entity):
    entity_type = 'space'
    placeables: Optional[List[PlaceableRef]] = []

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


class SpaceRef(SpaceBase):
    owner: Optional[UserRef] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


class SpaceRefNoOwner(SpaceBase):
    pass
