from typing import List

from app.crud.entity import CRUDEntity
from app.models import Placeable
from app.schemas import PlaceableUpdate


class CRUDPlaceable(CRUDEntity[Placeable, PlaceableUpdate, PlaceableUpdate]):
    @staticmethod
    def get_create_required_fields() -> List[str]:
        return []


placeable = CRUDPlaceable(Placeable)
