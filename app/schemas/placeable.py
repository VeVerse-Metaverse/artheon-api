from __future__ import annotations

import datetime
from typing import Optional, List

from app.schemas import PropertyRef, EntityRef
from app.schemas.config import CamelCaseModel, to_camel_cls


class FileRef(CamelCaseModel):
    id: Optional[str] = None
    type: Optional[str] = None
    url: Optional[str] = None
    mime: Optional[str] = None
    size: Optional[int] = 0
    width: Optional[int] = 0
    height: Optional[int] = 0
    version: Optional[int] = 0
    entity_id: Optional[str] = None

    class Config:
        orm_mode = True


class PlaceableBase(CamelCaseModel):
    pass

class PlaceableClassRef(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    # mod_id: Optional[str] = None
    # mod: Optional[ModRef] = None
    cls: Optional[str] = None  # class
    files: Optional[List[FileRef]]

    class Config:
        alias_generator = to_camel_cls
        allow_population_by_field_name = True
        orm_mode = True


class Placeable(PlaceableBase):
    id: str = None
    slot_id: Optional[str] = None
    p_x: Optional[float] = None
    p_y: Optional[float] = None
    p_z: Optional[float] = None
    r_x: Optional[float] = None
    r_y: Optional[float] = None
    r_z: Optional[float] = None
    s_x: Optional[float] = None
    s_y: Optional[float] = None
    s_z: Optional[float] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    entity_id: Optional[str] = None
    space_id: Optional[str] = None
    type: Optional[str] = None
    files: Optional[List[FileRef]] = None
    placeable_class_id: Optional[str] = None
    placeable_class: Optional[PlaceableClassRef] = None

    class Config:
        orm_mode = True


class PlaceableRef(PlaceableBase):
    id: str = None
    slot_id: Optional[str] = None
    p_x: Optional[float] = None
    p_y: Optional[float] = None
    p_z: Optional[float] = None
    r_x: Optional[float] = None
    r_y: Optional[float] = None
    r_z: Optional[float] = None
    s_x: Optional[float] = None
    s_y: Optional[float] = None
    s_z: Optional[float] = None
    type: Optional[str] = None
    space_id: Optional[str] = None
    placeable_class_id: Optional[str] = None
    entity_id: Optional[str] = None
    entity: Optional[EntityRef] = None
    placeable_class: Optional[PlaceableClassRef] = None
    files: Optional[List[FileRef]] = None
    properties: Optional[List[PropertyRef]] = None

    class Config:
        orm_mode = True


class PlaceableCreate(PlaceableBase):
    pass


class PlaceableUpdate(PlaceableBase):
    id: Optional[str] = None
    p_x: float = 0
    p_y: float = 0
    p_z: float = 0
    r_x: float = 0
    r_y: float = 0
    r_z: float = 0
    s_x: float = 1
    s_y: float = 1
    s_z: float = 1
    slot_id: Optional[str] = None
    type: Optional[str] = None
    entity_id: Optional[str] = None
    placeable_class_id: Optional[str] = None


class PlaceableTransformUpdate(PlaceableBase):
    id: Optional[str] = None
    p_x: float = 0
    p_y: float = 0
    p_z: float = 0
    r_x: float = 0
    r_y: float = 0
    r_z: float = 0
    s_x: float = 1
    s_y: float = 1
    s_z: float = 1


Placeable.update_forward_refs()
