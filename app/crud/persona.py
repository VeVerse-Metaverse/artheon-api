from typing import List

from app import models
from app.crud.entity import CRUDEntity
from app.models import Persona
from app.schemas import PersonaUpdate


class CRUDPersona(CRUDEntity[Persona, PersonaUpdate, PersonaUpdate]):
    @staticmethod
    def get_create_required_fields() -> List[str]:
        return [models.Persona.name.name,
                models.Persona.configuration.name]



persona = CRUDPersona(Persona)
