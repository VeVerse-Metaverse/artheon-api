from typing import Optional, List

from app.schemas import FileRef, UserRef
from app.schemas.config import to_camel, CamelCaseModel
from app.schemas.mod import SpaceModRef


class PortalDestination(CamelCaseModel):
    id: Optional[str] = None
    space: Optional[SpaceModRef] = None
    name: Optional[str] = None
    files: Optional[List[FileRef]] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


class PortalDestinationFileSimple(CamelCaseModel):
    id: Optional[str] = None
    type: Optional[str] = None
    platform: Optional[str] = False
    url: Optional[str] = None
    mime: Optional[str] = None
    deployment_type: Optional[str] = None
    version: Optional[int] = 0
    entity_id: Optional[str] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True

class PortalDestinationModSimple(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    version: Optional[str] = None
    release_name: Optional[str] = None
    map: Optional[str] = None
    files: Optional[List[PortalDestinationFileSimple]] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


class PortalDestinationSpaceSimple(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    map: Optional[str] = None
    mod: Optional[PortalDestinationModSimple] = None
    files: Optional[List[PortalDestinationFileSimple]] = None

    class Config:
        orm_mode = True


class PortalDestinationSimple(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    space: Optional[PortalDestinationSpaceSimple] = None
    files: Optional[List[PortalDestinationFileSimple]] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


class PortalSimple(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    destination: Optional[PortalDestinationSimple]

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


class Portal(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    destination: Optional[PortalDestination]
    owner: Optional[UserRef]

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


class PortalRef(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    space: Optional[SpaceModRef] = None
    destination: Optional[PortalDestination]
    owner: Optional[UserRef]

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


class PortalCreate(CamelCaseModel):
    public: Optional[bool] = True
    name: Optional[str] = None
    destination_id: Optional[str] = None
    space_id: Optional[str] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


class PortalUpdate(CamelCaseModel):
    public: Optional[bool] = True
    name: Optional[str] = None
    destination_id: Optional[str] = None
    space_id: Optional[str] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True
