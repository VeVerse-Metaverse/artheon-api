from typing import Optional, List

from app.schemas import UserRef, FileRef
from app.schemas.config import to_camel, CamelCaseModel


class Template(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    views: Optional[int] = None
    version: Optional[str] = None
    community: Optional[bool] = True
    public: Optional[bool] = True
    owner: Optional[UserRef] = None
    files: Optional[List[FileRef]] = None
    tags: Optional[List[str]] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


class TemplateCreate(CamelCaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    community: Optional[bool] = True
    public: Optional[bool] = True

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


class TemplateUpdate(CamelCaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


class TemplateRef(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    owner: Optional[UserRef] = None
    likes: Optional[int] = None
    dislikes: Optional[int] = None
    files: Optional[List[FileRef]] = None
    tags: Optional[List[str]] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True
