from typing import Optional

from app.schemas.config import CamelCaseModel, to_camel


class ModLink(CamelCaseModel):
    link_type: Optional[str] = None
    url: Optional[str] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True
