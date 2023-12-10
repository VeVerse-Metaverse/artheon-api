import uuid
from typing import Union, List

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session, lazyload, Query, joinedload, contains_eager

from app import models, schemas, crud
from app.config import settings
from app.crud.entity import CRUDEntity, EntityParameterError, EntityAccessError, EntityBatch, EntityNotFoundError
from app.helpers import is_valid_uuid
from app.models import Collection
from app.schemas.collection import CollectionCreate, CollectionUpdate


class CRUDCollection(CRUDEntity[Collection, CollectionCreate, CollectionUpdate]):

    def index_with_query(self, db, *, requester, offset=0, limit=10, query=None, fields=None, filters=None, options=None) -> EntityBatch[models.Space]:
        if fields is None:
            fields = ['name', 'description']

        return super(CRUDEntity, self).index_with_query(db, requester=requester, offset=offset, limit=limit, query=query, fields=fields, filters=filters, options=options)

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_collectables(self, db: Session, *, requester: models.User, entity: Union[str, models.Collection], offset: int, limit: int) -> EntityBatch[models.Object]:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not requester.id == entity.id and not entity.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        q: Query = db.query(models.Collectable)

        q = q.filter(models.Collectable.collection_id == entity.id)

        q = q.join(models.Collectable.object).join(models.Object.accessibles, isouter=True)

        # Join objects and their accessibles.
        # q = q.options(contains_eager(models.Collectable.object).contains_eager(models.Object.accessibles))

        q = q.filter(*self.make_can_view_filters(requester_id=requester.id, entity_model=models.Object, accessible_model=models.Accessible))

        total = self.get_total(q, models.Collectable.id)

        # q = q.with_entities(models.Object)

        q = q.order_by(models.Object.created_at)

        objects = q.offset(offset).limit(limit).all()

        return EntityBatch[models.Object](objects, offset, limit, total)

    def create_or_update_collectable(self, db: Session, *, requester: models.User, collection: Union[str, models.Collection], patch: schemas.CollectableUpdate):
        if not requester:
            raise EntityParameterError('no requester')

        if not collection:
            raise EntityParameterError('no entity')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        collection = self.prepare_entity(db, entity=collection, options=[lazyload(models.Collection.accessibles)])

        if not collection.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        if not isinstance(patch, dict):
            patch = patch.dict(exclude_unset=True)

        # Create a new collectable.
        if not "id" in patch or not patch["id"]:
            if not patch["object_id"]:
                raise EntityAccessError('no object id')

            collectable: models.Collectable = models.Collectable()

            if collectable.id is None:
                collectable.id = uuid.uuid4().hex

            collectable.collection_id = collection.id
            collectable.object_id = patch["object_id"]

        # Find an existing collectable to patch.
        else:
            if not is_valid_uuid(patch["id"]):
                raise EntityParameterError("invalid uuid")

            collectable = self.prepare_base(db, entity=patch["id"], model=models.Collectable)

            if collectable is None:
                raise EntityNotFoundError(f"no collectable with id {patch['id']}")
            else:
                collectable["object_id"] = patch["object_id"]

        db.add(collectable)
        db.commit()
        db.refresh(collectable)

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.add_collectable)

        return collectable

    def delete_collectable(self, db: Session, *, requester: models.User, collection: Union[str, models.Space], collectable_id: Union[str, models.Collectable]):
        if not requester:
            raise EntityParameterError('no requester')

        if not collection:
            raise EntityParameterError('no space')

        if not collectable_id:
            raise EntityParameterError('no collectable')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        collection = self.prepare_entity(db, entity=collection, model=models.Space, options=[joinedload(models.Space.accessibles)])
        collectable = self.prepare_base(db, entity=collectable_id, model=models.Collectable)

        # Allow to be deleted by users who are able to delete the placeable or the whole space.
        if not collection.deletable_by(requester):
            raise EntityAccessError('requester has no delete access to the entity')

        db.delete(collectable)
        db.commit()

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.remove_collectable)

    @staticmethod
    def get_create_required_fields() -> List[str]:
        return [models.Collection.name.name]


collection = CRUDCollection(Collection)
