from typing import List, Optional, Dict, Any

import inject
from sqlalchemy import or_, and_, distinct
from sqlalchemy.orm import Session, lazyload, Query, noload
from sqlalchemy.orm.interfaces import MapperOption

from app import crud, models
from app.crud.entity import CRUDEntity, EntityParameterError, EntityAccessError, EntityBatch, EntityNotFoundError
from app.schemas.object import ObjectUpdate, ObjectCreate
from app.services.image import Service


class CRUDObject(CRUDEntity[models.Object, ObjectCreate, ObjectUpdate]):
    imageService = inject.attr(Service)

    def index(self, db, *, requester, offset=0, limit=10, filters=None, options=None) -> EntityBatch[models.Object]:
        if isinstance(filters, List):
            filters.append(self.model.files != None)
        else:
            filters = [self.model.files != None]

        return super(CRUDEntity, self).index(db, requester=requester, offset=offset, limit=limit, filters=filters, options=options)

    def index_with_query(self, db, *, requester, offset=0, limit=10, query=None, fields=None, filters=None, options=None) -> EntityBatch[models.Object]:
        if fields is None:
            fields = ['name', 'description', 'artist', 'type', 'medium', 'origin', 'location']

        if isinstance(filters, List):
            filters.append(self.model.files != None)
        else:
            filters = [self.model.files != None]

        return super(CRUDEntity, self).index_with_query(db, requester=requester, offset=offset, limit=limit, query=query, fields=fields, filters=filters, options=options)

    def index_search(self, db: Session, *, requester: models.User, name: Optional[str] = None, description: Optional[str] = None,
                     artist: Optional[str] = None, type: Optional[str] = None, medium: Optional[str] = None, museum: Optional[str] = None,
                     year_min: Optional[int] = None, year_max: Optional[int] = None,
                     width_min: Optional[int] = None, width_max: Optional[int] = None,
                     height_min: Optional[int] = None, height_max: Optional[int] = None,
                     views_min: Optional[int] = None, views_max: Optional[int] = None,
                     offset: int = 0, limit: int = 10, options: Optional[MapperOption] = None) -> EntityBatch[models.Object]:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        # Polymorphic relation will join entity and user.
        q: Query = db.query(self.model)

        # Filter entities invisible by the user if user is not an admin.
        if not requester.is_admin:
            # Join accessibles and apply view filters.
            q = q.join(models.Accessible, models.Accessible.entity_id == models.Entity.id, isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id))

        if self._check_filter_str_parameter(name):
            q = q.filter(self.model.name.ilike(f"%{name}%"))
        if self._check_filter_str_parameter(description):
            q = q.filter(self.model.description.ilike(f"%{description}%"))
        if self._check_filter_str_parameter(artist):
            q = q.filter(self.model.artist.ilike(f"%{artist}%"))
        if self._check_filter_str_parameter(type):
            q = q.filter(self.model.type.ilike(f"%{type}%"))
        if self._check_filter_str_parameter(medium):
            q = q.filter(self.model.medium.ilike(f"%{medium}%"))
        if self._check_filter_str_parameter(museum):
            q = q.filter(self.model.museum.ilike(f"%{museum}%"))

        if year_min is not None:
            q = q.filter(self.model.year >= year_min)
        if year_max is not None:
            q = q.filter(self.model.year <= year_max)

        if views_min is not None:
            q = q.filter(self.model.views >= views_min)
        if views_max is not None:
            q = q.filter(self.model.views <= views_max)

        if width_min is not None:
            q = q.filter(self.model.width >= width_min)
        if width_max is not None:
            q = q.filter(self.model.width <= width_max)

        if height_min is not None:
            q = q.filter(self.model.height >= height_min)
        if height_max is not None:
            q = q.filter(self.model.height <= height_max)

        q = q.filter(self.model.files != None)

        # Sort by created date.
        q = q.order_by(self.model.created_at)

        # Get total count of entities falling under the query.
        total = self.get_total(q, self.model.id)

        if options and isinstance(options, MapperOption):
            q.options(options)

        entities = q.offset(offset).limit(limit).all()

        # Form entity batch and return.
        return EntityBatch[self.model](entities, offset, limit, total)

    # noinspection PyShadowingBuiltins,PyShadowingNames
    def index_similar(self, db: Session, *, requester: models.User, id: str, offset: int = 0, limit: int = 10, options: Optional[MapperOption] = None) -> EntityBatch[models.Object]:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        object = crud.object.get(db, requester=requester, id=id, options=options)

        if not object:
            raise EntityNotFoundError('entity does not exist')

        if not object.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        # Polymorphic relation will join entity and user.
        q: Query = db.query(self.model)

        # Filter entities invisible by the user if user is not an admin.
        if not requester.is_admin:
            # Join accessibles and apply view filters.
            q = q.join(models.Accessible, models.Accessible.entity_id == models.Entity.id, isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id))

        filters = []

        if object.name:
            filters.append(self.model.name.ilike(f"%{object.name}%"))
        if object.description:
            filters.append(self.model.description.ilike(f"%{object.description}%"))
        if object.artist:
            filters.append(self.model.artist.ilike(f"%{object.artist}%"))
        if object.type:
            filters.append(self.model.type.ilike(f"%{object.type}%"))
        if object.medium:
            filters.append(self.model.medium.ilike(f"%{object.medium}%"))

        q = q.filter(or_(*filters))

        q = q.filter(self.model.files != None)

        q = q.order_by(self.model.created_at)

        total = self.get_total(q, self.model.id)

        if options and isinstance(options, MapperOption):
            q.options(options)

        entities = q.offset(offset).limit(limit).all()

        return EntityBatch[self.model](entities, offset, limit, total)

    def index_types(self, db, *, query: str = None, requester: models.User, offset=0, limit=10) -> EntityBatch[Any]:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not query or len(query) < 3:
            raise EntityParameterError('query is too short')

        if not self._check_filter_str_parameter(query):
            raise EntityParameterError('invalid query')

        offset, limit = self.prepare_offset_limit(offset, limit)

        q: Query = db.query(self.model).filter(self.model.type.ilike(f"{query}%")).options(noload(self.model.files))

        total = self.get_total(q, self.model.type)

        stmt = q.statement.with_only_columns([distinct(self.model.type)]).order_by(self.model.type).limit(limit).offset(offset)

        result = q.session.execute(stmt).fetchall()

        return EntityBatch([r for r, in result], offset, limit, total)

    def index_museums(self, db, *, query: str = None, requester: models.User, offset=0, limit=10) -> EntityBatch[Any]:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not query or len(query) < 3:
            raise EntityParameterError('query is too short')

        if not self._check_filter_str_parameter(query):
            raise EntityParameterError('invalid query')

        offset, limit = self.prepare_offset_limit(offset, limit)

        q: Query = db.query(self.model).filter(self.model.museum.ilike(f"{query}%")).options(noload(self.model.files))

        total = self.get_total(q, self.model.museum)

        stmt = q.statement.with_only_columns([distinct(self.model.museum)]).order_by(self.model.type).limit(limit).offset(offset)

        result = q.session.execute(stmt).fetchall()

        return EntityBatch([r for r, in result], offset, limit, total)

    def index_artists(self, db, *, query: str = None, requester: models.User, offset=0, limit=10) -> EntityBatch[Any]:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not query or len(query) < 3:
            raise EntityParameterError('query is too short')

        if not self._check_filter_str_parameter(query):
            raise EntityParameterError('invalid query')

        offset, limit = self.prepare_offset_limit(offset, limit)

        q: Query = db.query(self.model).filter(self.model.artist.ilike(f"{query}%")).options(noload(self.model.files))

        total = self.get_total(q, self.model.artist)

        stmt = q.statement.with_only_columns([distinct(self.model.artist)]).order_by(self.model.artist).limit(limit).offset(offset)

        result = q.session.execute(stmt).fetchall()

        return EntityBatch([r for r, in result], offset, limit, total)

    def index_media(self, db, *, query: str = None, requester: models.User, offset=0, limit=10) -> EntityBatch[Any]:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not query or len(query) < 3:
            raise EntityParameterError('query is too short')

        if not self._check_filter_str_parameter(query):
            raise EntityParameterError('invalid query')

        offset, limit = self.prepare_offset_limit(offset, limit)

        q: Query = db.query(self.model).filter(self.model.medium.ilike(f"{query}%")).options(noload(self.model.files))

        total = self.get_total(q, self.model.medium)

        stmt = q.statement.with_only_columns([distinct(self.model.medium)]).order_by(self.model.medium).limit(limit).offset(offset)

        result = q.session.execute(stmt).fetchall()

        return EntityBatch([r for r, in result], offset, limit, total)

    @staticmethod
    def get_create_required_fields() -> List[str]:
        return [models.Object.name.name,
                models.Object.width.name,
                models.Object.height.name,
                models.Object.artist.name]

object = CRUDObject(models.Object)
