from __future__ import annotations

import datetime
from typing import Optional

from app.schemas.config import CamelCaseModel


class FileBase(CamelCaseModel):
    class Config:
        orm_mode = True


class File(FileBase):
    id: Optional[str] = None
    type: Optional[str] = False
    platform: Optional[str] = False
    url: Optional[str] = False
    mime: Optional[str] = False
    size: Optional[int] = 0
    deployment_type: Optional[str] = None
    version: Optional[int] = None
    variation: Optional[int] = 0
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    uploaded_by: Optional[str] = None
    entity_id: Optional[str] = None


class FileRef(FileBase):
    id: Optional[str] = None
    type: Optional[str] = None
    platform: Optional[str] = False
    url: Optional[str] = None
    mime: Optional[str] = None
    size: Optional[int] = 0
    deployment_type: Optional[str] = None
    width: Optional[int] = 0
    height: Optional[int] = 0
    version: Optional[int] = 0
    variation: Optional[int] = 0
    entity_id: Optional[str] = None


class AvatarRef(FileBase):
    id: Optional[str] = None
    url: Optional[str] = False
    mime: Optional[str] = False


File.update_forward_refs()
