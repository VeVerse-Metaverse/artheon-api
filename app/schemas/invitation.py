from pydantic.generics import GenericModel

from app.schemas.config import CamelCaseModel


class InvitationTotal(GenericModel, CamelCaseModel):
    used: int = 0
    unused: int = 0
    total: int = 0

    class Config:
        orm_mode = True
