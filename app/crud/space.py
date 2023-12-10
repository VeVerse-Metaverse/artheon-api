import re
import uuid
from typing import Union, List

from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, Query, aliased, joinedload, lazyload
from sqlalchemy.orm.interfaces import MapperOption

from app import models, schemas, crud
from app.config import settings
from app.crud.entity import CRUDEntity, EntityParameterError, EntityAccessError, EntityBatch, EntityNotFoundError
from app.helpers import is_valid_uuid
from app.models import Space
from app.schemas.space import SpaceCreate, SpaceUpdate


class CRUDSpace(CRUDEntity[Space, SpaceCreate, SpaceUpdate]):
    def index_with_query(self, db, *, requester, offset=0, limit=10, query=None, fields=None, filters=None, options=None, type=None) -> EntityBatch[models.Space]:
        if fields is None:
            fields = ['name', 'description', 'map']

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

        # Filter entities invisible by the user if user is not an admin.
        if not requester.is_admin:
            # Join accessibles and apply view filters.
            q = q.join(models.Accessible, models.Accessible.entity_id == models.Entity.id, isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id))

        # Filter by the search query if required.
        if query:
            if not bool(re.match('^[a-zA-Z0-9@.\\-_ #]+$', query)):
                raise EntityParameterError('query contains forbidden characters')
            else:
                f = [getattr(self.model, field).ilike(f"%{query}%") for field in fields]
                q = q.filter(or_(*f))

        if type:
            if not bool(re.match('^[a-zA-Z]+$', type)):
                raise EntityParameterError('type contains forbidden characters')
            else:
                q = q.filter(models.Space.type == type)

        if filters:
            q = q.filter(*filters)

        # Sort by created date.
        q = q.order_by(self.model.created_at)

        # Get total count of entities falling under the query.
        total = self.get_total(q, self.model.id)

        if options and isinstance(options, MapperOption):
            q.options(options)

        entities = q.offset(offset).limit(limit).all()

        for entity in entities:
            q = q.filter(models.Likable.entity_id == entity.id, models.Likable.value > 0)
            total_likes = self.get_total(q, models.Likable.id)

            q = q.filter(models.Likable.entity_id == entity.id, models.Likable.value < 0)
            total_dislikes = self.get_total(q, models.Likable.id)

            entity.total_likes = total_likes
            entity.total_dislikes = total_dislikes

        # Form entity batch and return.
        return EntityBatch[self.model](entities, offset, limit, total)

        # return super(CRUDEntity, self).index_with_query(db, requester=requester, offset=offset, limit=limit, query=query, fields=fields, filters=filters, options=options)

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_placeables(self, db: Session, *, requester: models.User, space: Union[str, models.Space], offset: int, limit: int) -> EntityBatch[models.Placeable]:
        if not requester:
            raise EntityParameterError('no requester')

        if not space:
            raise EntityParameterError('no entity')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        space = self.prepare_entity(db, entity=space, options=[joinedload(self.model.accessibles), joinedload(models.Placeable.placeable_class)])

        if not space.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        q: Query = db.query(models.Placeable)

        q = q.filter(models.Placeable.space_id == space.id)

        # Filter entities invisible by the requester if the requester is not an admin.
        if not requester.is_admin:
            ra = aliased(models.Accessible, name='ra')
            q = q.join(ra, and_(ra.entity_id == models.Placeable.id, ra.user_id == requester.id), isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id, accessible_model=ra))

        q = q.order_by(models.Placeable.created_at)

        total = self.get_total(q, models.Placeable.id)

        q = q.options(joinedload(models.Placeable.entity), joinedload(models.Placeable.properties))

        placeables = q.offset(offset).limit(limit).all()

        return EntityBatch[models.Placeable](placeables, offset, limit, total)

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_portals(self, db: Session, *, requester: models.User, space: Union[str, models.Space], offset: int, limit: int) -> EntityBatch[models.Portal]:
        if not requester:
            raise EntityParameterError('no requester')

        if not space:
            raise EntityParameterError('no entity')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        space = self.prepare_entity(db, entity=space, options=[joinedload(self.model.accessibles)])

        if not space.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        q: Query = db.query(models.Portal)

        q = q.filter(models.Portal.space_id == space.id)

        # Filter entities invisible by the requester if the requester is not an admin.
        if not requester.is_admin:
            ra = aliased(models.Accessible, name='ra')
            q = q.join(ra, and_(ra.entity_id == models.Portal.id, ra.user_id == requester.id), isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id, accessible_model=ra))

        q = q.order_by(models.Portal.created_at)

        total = self.get_total(q, models.Portal.id)

        portals = q.offset(offset).limit(limit).all()

        return EntityBatch[models.Portal](portals, offset, limit, total)

    # noinspection PyMethodMayBeStatic
    def create_or_update_placeable(self, db: Session, *, requester: models.User, space: Union[str, models.Space], placeable_class: Union[str, models.PlaceableClass], patch: schemas.PlaceableUpdate) -> models.Placeable:
        if not requester:
            raise EntityParameterError('no requester')

        if not space:
            raise EntityParameterError('no space')

        if not placeable_class:
            raise EntityParameterError('no class')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        space = self.prepare_entity(db, entity=space, options=[lazyload(models.Space.accessibles)])
        placeable_class = self.prepare_entity(db, model=models.PlaceableClass, entity=placeable_class, join_accessibles=False)

        if not space.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        json = jsonable_encoder(patch, by_alias=False)
        if not isinstance(patch, dict):
            patch = patch.dict(exclude_unset=True)

        # Create a new placeable.
        if not "id" in patch or not patch["id"]:
            placeable = models.Placeable()

            if placeable.id is None:
                placeable.id = uuid.uuid4().hex

            placeable.public = True
            placeable.space_id = space.id
            placeable.placeable_class_id = placeable_class.id

            for field in json:
                if field != "id":
                    if field in patch:
                        setattr(placeable, field, patch[field])

            # Create an accessible trait for the placeable.
            accessible = models.Accessible()
            accessible.entity_id = placeable.id
            accessible.user_id = requester.id
            accessible.is_owner = True
            accessible.can_view = True
            accessible.can_edit = True
            accessible.can_delete = True
            db.add(accessible)

        # Find an existing placeable to patch.
        else:
            if not is_valid_uuid(patch["id"]):
                raise EntityParameterError("invalid uuid")

            placeable = self.prepare_entity(db, entity=patch['id'], model=models.Placeable, options=[joinedload(models.Placeable.accessibles), joinedload(models.Placeable.placeable_class)])

            if placeable is None:
                raise EntityNotFoundError(f"no placeable with id {patch['id']}")
            else:
                updated_properties = 0

                # Enumerate all keys and update divergent keys.
                for field in json:
                    if field != "id":
                        if field in patch and getattr(placeable, field) != json[field]:
                            setattr(placeable, field, patch[field])
                            updated_properties += 1

                # Skip adding to database and return if we didn't actually update anything.
                if updated_properties == 0:
                    return placeable

        db.add(placeable)
        db.commit()
        db.refresh(placeable)

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.place_object)

        return placeable

    # noinspection PyMethodMayBeStatic
    def update_placeable_transform(self, db: Session, *, requester: models.User, id: str, patch: schemas.PlaceableTransformUpdate) -> models.Placeable:
        if not requester:
            raise EntityParameterError('no requester')

        if not id:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        placeable = self.prepare_entity(db, entity=id, model=models.Placeable, options=[lazyload(models.Placeable.accessibles)])

        if placeable is None:
            raise EntityNotFoundError(f"no placeable with id {id}")

        if not placeable.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        json = jsonable_encoder(patch, by_alias=False)
        if not isinstance(patch, dict):
            patch = patch.dict(exclude_unset=True)

        updated_properties = 0

        # Enumerate all keys and update divergent keys.
        for field in json:
            if field != "id":
                if field in patch and getattr(placeable, field) != json[field]:
                    setattr(placeable, field, patch[field])
                    updated_properties += 1

        # Skip adding to database and return if we didn't actually update anything.
        if updated_properties == 0:
            return placeable

        db.add(placeable)
        db.commit()
        db.refresh(placeable)

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.place_object)

        return placeable

    # noinspection PyMethodMayBeStatic
    def update_placeable_entity(self, db: Session, *, requester: models.User, id: str, entity_id: str) -> models.Placeable:
        if not requester:
            raise EntityParameterError('no requester')

        if not id:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        placeable: models.Placeable = self.prepare_entity(db, entity=id, model=models.Placeable, options=[lazyload(models.Placeable.accessibles)])

        if placeable is None:
            raise EntityNotFoundError(f"no placeable with id {id}")

        if not placeable.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        placeable.entity_id = entity_id

        db.add(placeable)
        db.commit()
        db.refresh(placeable)

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.place_object)

        return placeable

    def delete_placeable(self, db: Session, *, requester: models.User, placeable: Union[str, models.Placeable]):
        if not requester:
            raise EntityParameterError('no requester')

        if not placeable:
            raise EntityParameterError('no placeable')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        placeable = self.prepare_entity(db, entity=placeable, model=models.Placeable, options=[joinedload(models.Placeable.accessibles)])
        space = self.prepare_entity(db, entity=placeable.space_id, model=models.Space, options=[joinedload(models.Space.accessibles)])

        # Allow to be deleted by users who are able to delete the placeable or the whole space.
        if not space.deletable_by(requester) or not placeable.deletable_by(requester):
            raise EntityAccessError('requester has no delete access to the entity')

        CRUDEntity.delete_traits(self, db, entity_id=placeable.id)

        db.delete(placeable)
        db.commit()

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.remove_object)

    @staticmethod
    def get_create_required_fields() -> List[str]:
        return [models.Space.name.name,
                models.Space.map.name]

    def delete_traits(self, db: Session, *, entity_id: str):
        db.query(models.Placeable).filter(models.Placeable.entity_id == entity_id).delete()
        return super(CRUDEntity).delete_traits(db, entity_id=entity_id)


space = CRUDSpace(Space)
