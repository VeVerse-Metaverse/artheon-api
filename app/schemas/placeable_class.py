from typing import Optional, List

from app.schemas import FileRef
from app.schemas.config import CamelCaseModel, to_camel_cls, to_camel


class PlaceableClassBase(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    # mod_id: Optional[str] = None
    # mod: Optional[ModRef] = None
    cls: Optional[str] = None  # class
    files: Optional[List[FileRef]]

    class Config:
        orm_mode = True


class PlaceableClass(PlaceableClassBase):
    class Config:
        alias_generator = to_camel_cls
        allow_population_by_field_name = True
        orm_mode = True


class PlaceableClassCategory(CamelCaseModel):
    name: Optional[str] = None

    class Config:
        alias_generator = to_camel
