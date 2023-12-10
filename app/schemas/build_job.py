from typing import Optional

from app.schemas import ModRef
from app.schemas.config import CamelCaseModel, to_camel


class BuildJob(CamelCaseModel):
    id: Optional[str] = None
    mod_id: Optional[str] = None
    mod: Optional[ModRef] = None
    worker_id: Optional[str] = None
    status: Optional[str] = None
    configuration: Optional[str] = None
    platform: Optional[str] = None
    version: Optional[int] = None
    server: Optional[bool] = None
    map: Optional[str] = None
    release_name: Optional[str] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True
