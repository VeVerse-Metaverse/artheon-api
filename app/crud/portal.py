from typing import List

import inject

from app import models, schemas
from app.crud.entity import CRUDEntity, EntityBatch
from app.services.image import Service


class CRUDPortal(CRUDEntity[models.Portal, schemas.PortalCreate, schemas.PortalUpdate]):
    imageService = inject.attr(Service)

    # Filter out mods without files.
    def index(self, db, *, requester, offset=0, limit=10, filters=None, options=None) -> EntityBatch[models.Mod]:
        if isinstance(filters, List):
            filters.append(self.model.files != None)
        else:
            filters = [self.model.files != None]

        return super(CRUDEntity, self).index(db, requester=requester, offset=offset, limit=limit, filters=filters, options=options)

    # Filter out mods without files.
    def index_with_query(self, db, *, requester, offset=0, limit=10, query=None, fields=None, filters=None, options=None) -> EntityBatch[models.Object]:
        if fields is None:
            fields = ['name']

        # if isinstance(filters, List):
        #     filters.append(self.model.files != None)
        # else:
        #     filters = [self.model.files != None]

        return super(CRUDEntity, self).index_with_query(db, requester=requester, offset=offset, limit=limit, query=query, fields=fields, filters=filters, options=options)

    @staticmethod
    def get_create_required_fields() -> List[str]:
        return []


portal = CRUDPortal(models.Portal)
