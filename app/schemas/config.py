import stringcase
from pydantic import BaseModel


def to_camel(string):
    return stringcase.camelcase(string)


def to_camel_cls(string):
    if string == 'cls':
        return 'class'
    return stringcase.camelcase(string)


# Use this model as the base for entity base models instead of entity base to eliminate circular imports
class CamelCaseModel(BaseModel):
    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
