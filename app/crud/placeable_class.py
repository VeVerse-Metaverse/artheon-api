import re

from sqlalchemy import or_
from sqlalchemy.orm import Query
from sqlalchemy.orm.interfaces import MapperOption

from app import models
from app.crud.entity import CRUDEntity, EntityParameterError, EntityAccessError, EntityBatch
from app.models import PlaceableClass


class CRUDPlaceableClass(CRUDEntity[PlaceableClass, PlaceableClass, PlaceableClass]):
    def index_with_query(self, db, *, requester, offset=0, limit=10, query=None, fields=None, filters=None, options=None, category=None) -> EntityBatch[models.PlaceableClass]:
        if fields is None:
            fields = ['name', 'description']

        if not fields:
            raise EntityParameterError('no fields')

        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        # Polymorphic relation will join entity and user.
        q: Query = db.query(self.model)

        # Filter by the search query if required.
        if query:
            if not bool(re.match('^[a-zA-Z0-9@.\\-_ #]+$', query)):
                raise EntityParameterError('query contains forbidden characters')
            else:
                f = [getattr(self.model, field).ilike(f"%{query}%") for field in fields]
                q = q.filter(or_(*f))

        if category:
            if not bool(re.match('^[a-zA-Z]+$', category)):
                raise EntityParameterError('category contains forbidden characters')
            else:
                q = q.filter(models.PlaceableClass.category == category)

        if filters:
            q = q.filter(*filters)

        # Sort by name
        q = q.order_by(self.model.category)

        # Get total count of entities falling under the query.
        total = self.get_total(q, self.model.id)

        if options and isinstance(options, MapperOption):
            q.options(options)

        entities = q.offset(offset).limit(limit).all()

        # Form entity batch and return.
        return EntityBatch[self.model](entities, offset, limit, total)

    def index_categories_with_query(self, db, *, requester, offset=0, limit=10, query=None, filters=None, options=None) -> EntityBatch[str]:
        fields = ['category']

        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        # Polymorphic relation will join entity and user.
        q: Query = db.query(self.model.category).distinct()

        # Filter by the search query if required.
        if query:
            if not bool(re.match('^[a-zA-Z0-9@.\\-_ #]+$', query)):
                raise EntityParameterError('query contains forbidden characters')
            else:
                f = [getattr(self.model, field).ilike(f"%{query}%") for field in fields]
                q = q.filter(or_(*f))

        if filters:
            q = q.filter(*filters)

        # Sort by name
        q = q.order_by(self.model.category)

        # Get total count of entities falling under the query.
        total = self.get_total(q, self.model.category)

        if options and isinstance(options, MapperOption):
            q.options(options)

        result_entities = q.offset(offset).limit(limit).all()

        entities = []
        for e in result_entities:
            entities.append(e[0])

        # Form entity batch and return.
        return EntityBatch[self.model](entities, offset, limit, total)


placeable_class = CRUDPlaceableClass(PlaceableClass)
