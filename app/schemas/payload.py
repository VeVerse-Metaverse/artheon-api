from typing import Generic, Optional, TypeVar

from pydantic.generics import GenericModel

DataT = TypeVar('DataT')


# Generic response wrapper
class Payload(GenericModel, Generic[DataT]):
    data: Optional[DataT]

    class Config:
        orm_mode = True


class Ok(GenericModel):
    ok: bool

    class Config:
        orm_mode = True


class Views(GenericModel):
    views: int

    class Config:
        orm_mode = True


class Id(GenericModel):
    id: str

    class Config:
        orm_mode = True
