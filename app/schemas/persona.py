from typing import Optional, List

from app.schemas.config import CamelCaseModel
from app.schemas.user import FileRef


class PersonaUpdate(CamelCaseModel):
    name: Optional[str] = None
    configuration: Optional[str] = None
    type: Optional[str] = None

    class Config:
        orm_mode = True

class PersonaRef(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    configuration: Optional[str] = None
    files: Optional[List[FileRef]] = []

    class Config:
        orm_mode = True
