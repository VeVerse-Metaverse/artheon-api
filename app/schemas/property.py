from __future__ import annotations

from typing import Optional

from app.schemas.config import CamelCaseModel


class PropertyBase(CamelCaseModel):
    class Config:
        orm_mode = True


class Property(PropertyBase):
    type: Optional[str] = None
    name: Optional[str] = None
    value: Optional[str] = None
    entity_id: Optional[str] = None


class PropertyCreate(PropertyBase):
    type: Optional[str] = None
    name: Optional[str] = None
    value: Optional[str] = None


class PropertyRef(CamelCaseModel):
    type: Optional[str] = None
    name: Optional[str] = None
    value: Optional[str] = None

    class Config:
        orm_mode = True


Property.update_forward_refs()
