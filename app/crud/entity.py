import io
import logging
import os
import re
import tempfile
import uuid
from typing import Generic, Type, TypeVar, Any, Optional, List, Dict, Union
from urllib.parse import unquote

import inject
import requests
from PIL import Image
from fastapi import UploadFile
from fastapi.encoders import jsonable_encoder
from pdf2image import convert_from_bytes
from pydantic.main import BaseModel
from sqlalchemy import or_, and_, func, distinct, desc
from sqlalchemy.orm import Session, Query, aliased, lazyload, noload, joinedload
from sqlalchemy.orm.interfaces import MapperOption

from app import models, schemas, crud
from app.config import settings
from app.schemas.accessible import AccessibleUpdate
from app.services import s3, image, upload

ModelType = TypeVar("ModelType", bound=models.Entity)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

logger = logging.getLogger(__name__)


class EntityError(Exception):
    pass


class EntityAccessError(EntityError):
    pass


class EntityParameterError(EntityError):
    pass


class EntityNotFoundError(EntityError):
    pass


# Wrapped list of entities including offset and limit of request and total amount of entities satisfying the request.
class EntityBatch(Generic[ModelType]):
    def __init__(self, entities, offset, limit, total):
        self.entities = entities
        self.offset = offset
        self.limit = limit
        self.total = total

    entities: List[ModelType] = []
    offset: int = 0
    limit: int = 0
    total: int = 0


class EntityTotal(Generic[ModelType]):
    def __init__(self, total):
        self.total = total

    total: int = 0


# noinspection PyComparisonWithNone
class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def _get(self, db: Session, *, id: str):
        if not self.is_valid_uuid(id):
            raise EntityParameterError('invalid id')

        # Polymorphic relation will join entity and user.
        q: Query = db.query(self.model)

        # Exclude private fields.
        q = q.filter(self.model.id == id)

        return q.first()

    @staticmethod
    def get_total(q, column):
        count_q = q.statement.with_only_columns([func.count(distinct(column))]).order_by(None)
        total = q.session.execute(count_q).scalar()
        return total

    # region Accessible helpers

    @staticmethod
    def make_owner_filters(requester_id: str):
        """Helper method to create accessible trait view filters."""
        return [
            models.Accessible.user_id == requester_id,
            models.Accessible.is_owner == True
        ]

    @staticmethod
    def make_can_view_filters(requester_id: str, *, entity_model=models.Entity, accessible_model=models.Accessible):
        """Helper method to create accessible trait view filters for indexing methods. Note that accessible must be joined."""
        return [
            or_(entity_model.public == True,  # Allow public entities
                and_(accessible_model.user_id == requester_id,
                     # Allow objects marked as viewable or owned by the user.
                     or_(accessible_model.can_view == True,
                         accessible_model.is_owner == True)
                     )
                )
        ]

    # endregion
    # noinspection PyMethodMayBeStatic
    def _check_filter_str_parameter(self, query: str):
        if query:
            if not bool(re.match('^[a-zA-Z0-9@.\\-_ ]+$', query)):
                raise EntityParameterError('string contains invalid characters')
            else:
                return True
        return False

    @staticmethod
    def get_public_fields() -> List[str]:
        raise NotImplementedError()

    @staticmethod
    def is_valid_uuid(id, version=4):
        try:
            uuid.UUID(str(id).lower(), version=version)
        except ValueError:
            return False
        return True

    @staticmethod
    def prepare_offset_limit(offset: int = 0, limit: int = 10) -> (int, int):
        if not offset or offset < 0:
            offset = 0

        if not limit or limit <= 0:
            limit = 10

        if limit > 20:
            limit = 20

        return offset, limit

    # noinspection PyShadowingNames
    def prepare_base(self, db, *, entity: Union[str, models.Entity], model=None, options: Optional[Union[MapperOption, List[MapperOption]]] = None) -> models.Entity:
        if not model:
            model = self.model
        if isinstance(entity, str):
            # Check the entity id.
            if not CRUDBase.is_valid_uuid(entity):
                raise EntityParameterError('invalid id')
            # Try to get the entity from the database.
            q = db.query(model)
            q = q.filter(model.id == entity)
            if options:
                if isinstance(options, MapperOption):
                    q = q.options(options)
                elif isinstance(options, List):
                    q = q.options(*options)
            e = q.first()
            if not e:
                raise EntityNotFoundError(f"no entity with id {entity}")
            return e
        elif not isinstance(entity, model):
            raise EntityParameterError('no entity')
        return entity

    # noinspection PyShadowingNames
    def prepare_entity(self, db, *, entity: Union[str, models.Entity], model=None, options: Optional[Union[MapperOption, List[MapperOption]]] = None, join_accessibles: bool = True) -> models.Entity:
        if not model:
            model = self.model
        if isinstance(entity, str):
            # Check the entity id.
            if not CRUDBase.is_valid_uuid(entity):
                raise EntityParameterError('invalid id')
            # Try to get the entity from the database.
            q = db.query(model)
            if join_accessibles:
                q = q.join(models.Accessible, isouter=True)
            q = q.filter(model.id == entity)
            if options:
                if isinstance(options, MapperOption):
                    q = q.options(options)
                elif isinstance(options, List):
                    q = q.options(*options)
            e = q.first()
            if not e:
                raise EntityNotFoundError(f"no entity with id {entity}")
            return e
        elif not isinstance(entity, model):
            raise EntityParameterError('no entity')
        return entity

    @staticmethod
    def prepare_user(db, *, user: Union[str, models.User], options: Optional[Union[MapperOption, List[MapperOption]]] = None, join_accessibles: bool = True) -> models.User:
        if isinstance(user, str):
            # Check user id.
            if not CRUDBase.is_valid_uuid(user):
                raise EntityParameterError('invalid id')
            # Try to get the user from the database.
            q = db.query(models.User)
            if join_accessibles:
                q = q.join(models.Accessible, isouter=True)
            q = q.filter(models.User.id == user)
            if options:
                if isinstance(options, MapperOption):
                    q = q.options(options)
                elif isinstance(options, List):
                    q = q.options(*options)
            u = q.first()
            if not u:
                raise EntityNotFoundError('no user')
            return u
        elif not isinstance(user, models.User):
            raise EntityParameterError('no user')
        return user

    def index(self, db: Session, *, requester: models.User, offset: int = 0, limit: int = 10, filters: List[Any] = None, options: Optional[MapperOption] = None) -> EntityBatch:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        # Query entity model with accessible traits.
        q: Query = db.query(self.model)

        # Filter entities invisible by the user if user is not an admin.
        if not requester.is_admin:
            # Join accessibles and apply view filters.
            q = q.join(models.Accessible, models.Accessible.entity_id == models.Entity.id, isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id))

        if filters:
            q = q.filter(*filters)

        # Calculate total.
        total = self.get_total(q, self.model.id)

        if options is not None:
            q = q.options(options)

        # Execute query and get all entities within offset and limit.
        entities = q.offset(offset).limit(limit).all()

        # Return entity batch.
        return EntityBatch(entities, offset, limit, total)

    def index_with_query(self, db: Session, *, requester: models.User, offset: int = 0, limit: int = 10, query: Optional[str] = None, fields: Optional[List[str]] = None,
                         filters: Optional[List[Any]] = None, options: Optional[MapperOption] = None) -> EntityBatch[models.Entity]:
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

    def index_with_query_sorted(self, db: Session, *, requester: models.User, offset: int = 0, limit: int = 10, query: Optional[str] = None, sort: int = -1, fields: Optional[List[str]] = None,
                                filters: Optional[List[Any]] = None, options: Optional[MapperOption] = None) -> EntityBatch[models.Entity]:
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

        if filters:
            q = q.filter(*filters)

        # Sort by created date.
        if (sort > 0):
            q = q.order_by(self.model.created_at)
        elif (sort < 0):
            q = q.order_by(desc(self.model.created_at))

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

    def index_by_foreign_key_value(self, db: Session, *, requester: models.User, key: Optional[str] = None, value: Optional[str] = None, offset: int = 0, limit: int = 10,
                                   filters: List[Any] = None, options: Optional[MapperOption] = None) -> EntityBatch[models.Entity]:
        if not key:
            raise EntityParameterError('no key')

        if not value:
            raise EntityParameterError('no key')

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

        q.filter(getattr(self.model, key) == value)

        if filters:
            q = q.filter(*filters)

        # Sort by created date.
        q = q.order_by(models.Entity.created_at)

        # Get total count of entities falling under the query.
        total = self.get_total(q, self.model.id)

        if options and isinstance(options, MapperOption):
            q.options(options)

        entities = q.offset(offset).limit(limit).all()

        # Form entity batch and return.
        return EntityBatch[self.model](entities, offset, limit, total)

    # noinspection PyShadowingNames
    def get(self, db: Session, *, requester: models.User, id: str, options: Optional[MapperOption] = None) -> Optional[ModelType]:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not options:
            options = joinedload(self.model.accessibles)

        entity = self.prepare_entity(db, entity=id, model=self.model, options=[options, joinedload(self.model.accessibles)])

        if not entity.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        return entity

    # noinspection PyShadowingNames
    def create(self, db: Session, *, requester: models.User = None, entity: CreateSchemaType) -> ModelType:
        raise NotImplementedError('use create_for_requester instead')

    # noinspection PyShadowingNames
    def update(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity], patch: Union[UpdateSchemaType, Dict[str, Any]]):
        raise NotImplementedError('use derived class instead')

    # noinspection PyShadowingNames
    def delete(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity]):
        if not requester:
            raise EntityParameterError("no requester")

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        # Ensure that entity is deletable by the requester.
        if not entity.deletable_by(requester):
            raise EntityAccessError('requester has no delete access to the entity')

        db.delete(entity)
        db.commit()


# noinspection PyMethodMayBeStatic
class CRUDEntity(CRUDBase[ModelType, CreateSchemaType, UpdateSchemaType]):
    imageService = inject.attr(image.Service)
    uploadService = inject.attr(upload.Service)
    s3Service = inject.attr(s3.S3Service)

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_properties(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity], offset: int, limit: int) -> EntityBatch[models.Property]:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        entity = self.prepare_entity(db, entity=entity, model=models.Entity)

        if not entity.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        q: Query = db.query(models.Property)

        q = q.filter(models.Property.entity_id == entity.id)

        q = q.order_by(models.Property.name)

        total = q.count()

        properties = q.offset(offset).limit(limit).all()

        return EntityBatch[models.Property](properties, offset, limit, total)

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_comments(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity], offset: int, limit: int) -> EntityBatch[models.Comment]:
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

        if not entity.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        q: Query = db.query(models.Comment)

        q = q.filter(models.Comment.entity_id == entity.id)

        # Filter entities invisible by the requester if the requester is not an admin.
        if not requester.is_admin:
            ra = aliased(models.Accessible, name='ra')
            q = q.join(ra, and_(ra.entity_id == models.Comment.id, ra.user_id == requester.id), isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id, accessible_model=ra))

        q = q.order_by(models.Comment.created_at)

        total = self.get_total(q, models.Comment.id)

        # Add the user who posted the comment.
        q = q.options(lazyload(models.Comment.user))

        comments = q.offset(offset).limit(limit).all()

        # Filter away users the requester can't view.
        comments = [self._omit_trait_user(comment, requester) for comment in comments]

        return EntityBatch[models.Comment](comments, offset, limit, total)

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_likes(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity], offset: int, limit: int) -> EntityBatch[models.Likable]:
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

        q: Query = db.query(models.Likable)

        q = q.filter(models.Likable.entity_id == entity.id, models.Likable.value > 0)

        total = self.get_total(q, models.Likable.id)

        q = q.order_by(models.Likable.created_at)

        q = q.options(lazyload(models.Likable.user))

        likes = q.offset(offset).limit(limit).all()

        # Filter away users the requester can't view.
        likes = [self._omit_trait_user(like, requester) for like in likes]

        return EntityBatch[models.Likable](likes, offset, limit, total)

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def get_likes(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity]) -> EntityTotal:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not requester.id == entity.id and not entity.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        q: Query = db.query(models.Likable)

        q = q.filter(models.Likable.entity_id == entity.id, models.Likable.value > 0)

        total = self.get_total(q, models.Likable.id)

        return EntityTotal(total)

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def get_liked_by_requester(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity]) -> bool:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not requester.id == entity.id and not entity.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        q: Query = db.query(models.Likable)

        q = q.filter(models.Likable.entity_id == entity.id, models.Likable.user_id == requester.id, models.Likable.value > 0)

        total = q.count()

        return total > 0

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def get_dislikes(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity]) -> EntityTotal:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not requester.id == entity.id and not entity.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        q: Query = db.query(models.Likable)

        q = q.filter(models.Likable.entity_id == entity.id, models.Likable.value < 0)

        total = self.get_total(q, models.Likable.id)

        return EntityTotal(total)

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def get_disliked_by_requester(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity]) -> bool:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not requester.id == entity.id and not entity.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        q: Query = db.query(models.Likable)

        q = q.filter(models.Likable.entity_id == entity.id, models.Likable.user_id == requester.id, models.Likable.value < 0)

        total = q.count()

        return total > 0

    async def delete_batch(self, db: Session, *, requester: models.User, ids: List[str]) -> int:
        r"""Admin only method to delete batch of entities by id list including all related traits and stored files."""
        if not requester:
            raise EntityParameterError("no requester")

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not requester.is_admin:
            raise EntityAccessError('access denied')

        if not requester.is_super_admin():
            raise EntityAccessError('access denied')

        q: Query = db.query(self.model).options(noload(self.model.files)).filter(self.model.id.in_(ids))

        # Delete stored files.
        for id in ids:
            await self.delete_stored_files(db, entity=id, requester=requester)

        total = q.delete(synchronize_session=False)

        db.commit()

        return total

    # noinspection PyShadowingNames
    def create(self, db: Session, *, requester: models.User = None, entity: CreateSchemaType) -> ModelType:
        raise EntityAccessError('use create_for_requester instead')

    # noinspection PyShadowingNames
    def update(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity], patch: Union[UpdateSchemaType, Dict[str, Any]], unique_fields=None):
        if unique_fields is None:
            unique_fields = []

        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, model=self.model, options=joinedload(self.model.accessibles))

        # Ensure that the entity is editable by the requester.
        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        # Create a JSON-compatible dict.
        json = jsonable_encoder(patch, by_alias=False)
        if not isinstance(patch, dict):
            patch = patch.dict(exclude_unset=True)

        # Check if entity has a name and the name is available.
        for field in unique_fields:
            if field in json:
                if hasattr(entity, field) and getattr(entity, field) != json[field]:
                    if self.check_exists_by_field(db, name=field, value=json[field]):
                        raise EntityParameterError(f"{field} not unique")

        updated_properties: int = 0

        # Patch the entity with values of the existing fields.
        for field in json:
            # Do not change id.
            if field != "id":
                if field in patch and getattr(entity, field) != patch[field]:
                    setattr(entity, field, patch[field])
                    updated_properties += 1

        # Store the entity in the database if it should be updated.
        if updated_properties > 0:
            db.add(entity)
            db.commit()
            db.refresh(entity)

            crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.update)

        return entity

    # noinspection PyShadowingNames
    def create_or_update_accessible(self, db: Session, *, requester: models.User, entity: Union[str, ModelType], patch: AccessibleUpdate) -> bool:
        r"""Updates accessible trait for the entity and the requester."""
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if entity.entity_type == 'user':
            raise EntityAccessError('access denied')

        if not entity.owned_by(user=requester):
            raise EntityAccessError('requester has no owner access to the entity')

        accessible: Optional[models.Accessible] = db.query(models.Accessible).filter(
            models.Accessible.user_id == patch.user_id,
            models.Accessible.entity_id == entity.id
        ).first()

        if accessible is not None:
            # Nothing to update.
            if accessible.can_view == patch.can_view and accessible.can_edit == patch.can_edit and accessible.can_delete == patch.can_delete:
                return accessible

            accessible.can_view = patch.can_view
            accessible.can_edit = patch.can_edit
            accessible.can_delete = patch.can_delete
        else:
            # Create a new accessible between the entity and the user we share access with
            accessible = models.Accessible()
            accessible.entity_id = entity.id
            accessible.user_id = patch.user_id
            accessible.is_owner = False  # Owner flag set only during entity creation
            accessible.can_view = patch.can_view
            accessible.can_edit = patch.can_edit
            accessible.can_delete = patch.can_delete

        db.add(accessible)
        db.commit()

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.share)

        return True

    # noinspection PyShadowingNames
    def create_or_update_likable(self, db: Session, *, requester: models.User, entity: ModelType, rating: int) -> bool:
        r"""Updates likable trait for the entity and the requester."""
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=lazyload(self.model.accessibles))

        if not entity.likable_by(requester):
            raise EntityAccessError('requester has no like access to the entity')

        rating = -1 if rating < 0 else 1 if rating > 0 else 0

        q: Query = db.query(models.Likable).filter(models.Likable.entity_id == entity.id,
                                                   models.Likable.user_id == requester.id)

        likable: models.Likable = q.first()

        # Create a new likable.
        if not likable:
            likable = models.Likable()
            if not likable.id:
                likable.id = uuid.uuid4().hex
            likable.entity_id = entity.id
            likable.user_id = requester.id

        likable.value = rating

        db.add(likable)
        db.commit()
        db.refresh(likable)

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.like)

        return likable

    # noinspection PyShadowingNames,PyShadowingBuiltins
    def create_or_update_property(self, db: Session, *, requester: models.User, entity: Union[str, ModelType], patch: schemas.PropertyCreate) -> bool:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not patch:
            raise EntityParameterError("no property")

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        q: Query = db.query(models.Property).filter(models.Property.entity_id == entity.id,
                                                    models.Property.name == patch.name)

        property: models.Property = q.first()

        # Create if does not exist.
        if not property:
            property = models.Property()
            property.entity_id = entity.id
            property.name = patch.name

        # Update values.
        property.type = patch.type
        property.value = patch.value

        db.add(property)
        db.commit()

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.update)

        return True

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_tags(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity], offset: int, limit: int) -> List[str]:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        entity = self.prepare_entity(db, entity=entity, model=models.Entity)

        if not entity.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        q: Query = db.query(models.Tag).join(models.EntityTagAssociation)

        q = q.filter(models.EntityTagAssociation.entity_id == entity.id)

        q = q.order_by(models.Tag.name)

        total = q.count()

        tags = q.offset(offset).limit(limit).all()

        return EntityBatch[models.Tag](tags, offset, limit, total)

    # noinspection PyShadowingNames
    def update_tags(self, db: Session, *, requester: models.User, entity: Union[str, ModelType], tags: str) -> bool:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not tags:
            raise EntityParameterError("no tags")

        if not re.match("^[ ,]*[a-zA-Z0-9]+(?:[ ,]+[a-zA-Z0-9]+)*[ ,]*$", tags):
            raise EntityParameterError("tags must be alphanumeric characters separated with commas")

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        tags = [tag.lower() for tag in tags.split(',')]
        tags = set(tags)
        if "" in tags:
            tags.remove("")

        for tag in tags:
            m_tag: models.Tag = db.query(models.Tag).filter(models.Tag.name == tag).first()
            if not m_tag:
                m_tag = models.Tag(id=uuid.uuid4().hex, name=tag)
                db.add(m_tag)

            # Update values.
            m_association: models.EntityTagAssociation = db.query(models.EntityTagAssociation).filter(
                models.EntityTagAssociation.entity_id == entity.id,
                models.EntityTagAssociation.tag_id == m_tag.id).first()

            if not m_association:
                m_association = models.EntityTagAssociation()
                m_association.tag = m_tag
                entity.tags.append(m_association)

        db.add(entity)
        db.commit()

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.tag)

        return True

    # noinspection PyShadowingNames
    def delete_tag(self, db: Session, *, requester: models.User, entity: Union[str, ModelType], tag: str) -> bool:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not tag:
            raise EntityParameterError("no tags")

        if not re.match("^[a-zA-Z0-9]+$", tag):
            raise EntityParameterError("tag can include only alphanumeric characters")

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        tag = tag.lower()

        m_tag: models.Tag = db.query(models.Tag).filter(models.Tag.name == tag).first()
        if not m_tag:
            return False

        # Update values.
        m_association: models.EntityTagAssociation = db.query(models.EntityTagAssociation).filter(models.EntityTagAssociation.tag_id == m_tag.id,
                                                                                                  models.EntityTagAssociation.entity_id == entity.id).first()
        if not m_association:
            return False
        else:
            db.delete(m_association)
            db.commit()

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.remove_tag)

        return True

    # noinspection PyShadowingNames,PyShadowingBuiltins
    def delete_property(self, db: Session, *, requester: models.User, entity: Union[str, ModelType], name: str) -> None:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not entity.deletable_by(requester):
            raise EntityAccessError('requester has no delete access to the entity')

        q: Query = db.query(models.Property).filter(models.Property.entity_id == entity.id,
                                                    models.Property.name == name)

        property: models.Property = q.first()

        if not property:
            raise EntityNotFoundError('property does not exist')

        db.delete(property)
        db.commit()

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.update)

    # noinspection PyShadowingNames
    def increment_view_count(self, db: Session, *, requester: models.User, entity: ModelType) -> int:
        r"""Increments view count for the entity."""
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not entity.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        entity.views += 1

        db.add(entity)
        db.commit()
        db.refresh(entity)

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.view)

        return entity.views

    # noinspection PyShadowingNames
    def create_comment(self, db: Session, *, requester: models.User, entity: Union[str, ModelType], source: schemas.CommentCreate) -> models.Comment:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not source:
            raise EntityParameterError('no comment')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not entity.commentable_by(requester):
            raise EntityAccessError('requester has no comment access to the entity')

        comment = models.Comment()
        if comment.id is None:
            comment.id = uuid.uuid4().hex

        # Create an accessible trait for the comment.
        accessible = models.Accessible()
        accessible.entity_id = comment.id
        accessible.user_id = requester.id
        accessible.is_owner = True
        accessible.can_view = True
        accessible.can_edit = True
        accessible.can_delete = True

        # All comments are public by default.
        comment.public = True
        comment.entity_id = entity.id
        comment.user_id = requester.id
        comment.text = source.text

        db.add(comment)
        db.add(accessible)
        db.commit()
        db.refresh(comment)

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.add_comment)

        return comment

    # noinspection PyShadowingNames
    def delete_comment(self, db: Session, *, requester: models.User, entity: Union[str, ModelType], comment: Union[str, models.Comment]):
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not comment:
            raise EntityParameterError('no comment')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))
        comment = self.prepare_entity(db, entity=comment, options=joinedload(models.Comment.accessibles))

        # Allow users with permission to delete entity or the comment to delete comment.
        entity_deletable = entity.deletable_by(requester)
        comment_deletable = comment.deletable_by(requester)

        if not entity_deletable and not comment_deletable:
            raise EntityAccessError('requester has no delete access to the entity')

        self.delete_traits(db, entity_id=comment.id)

        db.delete(comment)
        db.commit()

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.delete_comment)

    # noinspection PyShadowingNames
    def create_for_requester(self, db: Session, *, requester: models.User, source: CreateSchemaType, unique_fields=None) -> ModelType:
        r"""Creates a new entity for the requester."""
        if unique_fields is None:
            unique_fields = []

        if not requester:
            raise EntityParameterError('no requester')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        # Create a JSON-compatible dict.
        json = jsonable_encoder(source, by_alias=False)

        # Check that required properties are in the dict.
        required = self.get_create_required_fields()
        if not all(el in list(json.keys()) for el in required):
            raise EntityParameterError(f"required properties: {', '.join(required)}")

        # Check if entity has a name and the name is available.
        for field in unique_fields:
            if field in json:
                if self.check_exists_by_field(db, name=field, value=json[field]):
                    raise EntityParameterError(f"{field} not unique")

        # Create a new entity using source data.
        entity: models.Entity = self.model(**json)

        # Generate a new UUID if required
        if entity.id is None:
            entity.id = uuid.uuid4().hex

        # Create an accessible trait.
        accessible = models.Accessible()
        accessible.entity_id = entity.id
        accessible.user_id = requester.id
        accessible.is_owner = True
        accessible.can_view = True
        accessible.can_edit = True
        accessible.can_delete = True

        # Store the entity and trait in the database.
        db.add(entity)
        db.add(accessible)
        db.commit()
        db.refresh(entity)

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.create)

        return entity

    # noinspection PyShadowingNames
    def delete(self, db: Session, *, requester: models.User, entity: Union[str, ModelType]):
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if entity.entity_type == 'user':
            raise EntityAccessError('access denied')

        # Ensure that entity is deletable by the requester.
        if not entity.deletable_by(requester):
            raise EntityAccessError('requester has no delete access to the entity')

        self.delete_traits(db, entity_id=entity.id)

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.delete)

        super().delete(db, requester=requester, entity=entity)

    def delete_traits(self, db: Session, *, entity_id: str):
        # Delete traits.
        db.query(models.Likable).filter(models.Likable.entity_id == entity_id).delete()
        db.query(models.Accessible).filter(models.Accessible.entity_id == entity_id).delete()
        # Delete all file traits from the database and uploaded files from the cloud storage.
        files = db.query(models.File).filter(models.File.entity_id == entity_id).all()
        for file in files:
            self.__safe_delete_file_by_url(db, url=file.url)
            db.delete(file)

    # region Files

    def get_file(self, db: Session, *, requester: models.User, id: str) -> models.File:
        if not requester:
            raise EntityParameterError('no requester')

        if not id:
            raise EntityParameterError('no id')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        q: Query = db.query(models.File)

        q.filter(models.File.id == id)

        file = q.first()

        # Get entity to check for requester entity access
        entity = self.prepare_entity(db, entity=file.entity_id, model=models.Entity)
        if not entity.viewable_by(requester):
            raise EntityAccessError('requester has no access to the file')

        return file

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_files(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity], offset: int, limit: int, type: str = '') -> EntityBatch[models.File]:
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

        q: Query = db.query(models.File)

        q = q.filter(models.File.entity_id == entity.id)
        if type:
            q = q.filter(models.File.type == type)

        total = self.get_total(q, models.File.id)

        q = q.order_by(models.File.created_at)

        files = q.offset(offset).limit(limit).all()

        # Filter away users the requester can't view.
        files = [self._omit_trait_user(file, requester) for file in files]

        return EntityBatch[models.File](files, offset, limit, total)

    def add_file(self, db: Session, *, requester: models.User,
                 entity: ModelType, type: str, platform: Optional[str], version: Optional[int], deployment_type: Optional[str] = None, filename: str, mime: str = 'binary/octet-stream',
                 size: int = 0) -> models.File:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(models.Entity.accessibles))

        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        if type == 'pdf':
            with tempfile.TemporaryDirectory() as temp_dir:

                r = requests.get(filename, stream=True)
                with open(f'{temp_dir}/temp.pdf', 'ab+') as fd:
                    for chunk in r.iter_content(2000):
                        fd.write(chunk)
                    fd.seek(0)
                    b = bytearray(fd.read())
                    file_id = self.get_file_id(db, entity.id, type, platform, version, deployment_type)
                    file_key = f"{entity.id}/{file_id}"
                    extra_args = {
                        "Metadata": {
                            "x-amz-meta-content-type": 'application/x-pdf',
                            "x-amz-meta-filename": filename,
                            "x-amz-meta-extension": "pdf",
                            "x-amz-meta-type": "pdf"
                        }
                    }
                    uploaded_file = self.uploadService.upload_file(file_key, b, extra_args=extra_args)
                    file = self.create_or_replace_file(db=db, entity_id=entity.id, type=type, platform=platform, version=version, deployment_type=deployment_type,
                                                       uploaded_file=uploaded_file, requester=requester, id=file_id, original_name=filename)

                    uploaded_files = self.__upload_pdf(file_key=entity.id, file_bytes=b)
                    logger.info(f"uploaded files: {len(uploaded_files)}")
                    # Assign the file to the entity.
                    i = 0
                    for u_file in uploaded_files:
                        logger.info(f"storing file: {u_file['id']} entity_id: {entity.id}, type: {type}, platform: {platform}, version: {version}, deployment_type: {deployment_type}, id: {file_id}, filename: {filename}, var: {i}")
                        self.create_or_replace_file(db=db, entity_id=entity.id, type="pdf_image", platform=platform, version=version, deployment_type=deployment_type,
                                                    uploaded_file=u_file["file"], requester=requester, id=u_file["id"], original_name=filename, variation=i)
                        i = i + 1
        else:
            uploaded_file = s3.UploadedFile(filename, mime, size)

            # Assign the file to the entity.
            file_id = uuid.uuid4().hex
            file = self.create_or_replace_file(db=db, entity_id=entity.id, type=type, platform=platform, version=version, deployment_type=deployment_type,
                                               uploaded_file=uploaded_file, requester=requester, id=file_id, original_name=filename)

            db.commit()

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.add_file)

        return file

    async def replace_file(self, db: Session, *, requester: models.User,
                           entity: ModelType, type: str, filename: str, platform: Optional[str] = None, version: Optional[int] = None, deployment_type: Optional[str] = None,
                           mime: str = 'binary/octet-stream', size: int = 0) -> models.File:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(models.Entity.accessibles))

        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        uploaded_file = s3.UploadedFile(filename, mime, size)

        # Special case, use initial full image to generate diffuse texture and preview image automatically.
        if type == 'image_full_initial':
            # Upload full-sized image and assign it to the entity.
            file_id = uuid.uuid4().hex
            file = self.create_or_replace_file(db=db, entity_id=entity.id, type='image_full', platform=platform, version=version, deployment_type=deployment_type,
                                               uploaded_file=uploaded_file, requester=requester, id=file_id, original_name=filename)

            # Upload texture image and assign it to the entity.
            file_id = uuid.uuid4().hex
            self.create_or_replace_file(db=db, entity_id=entity.id, type='texture_diffuse', platform=platform, version=version, deployment_type=deployment_type,
                                        uploaded_file=uploaded_file, requester=requester, id=file_id)

            # Upload preview image and assign it to the entity.
            file_id = uuid.uuid4().hex
            self.create_or_replace_file(db=db, entity_id=entity.id, type='image_preview', platform=platform, version=version, deployment_type=deployment_type,
                                        uploaded_file=uploaded_file, requester=requester, id=file_id)
        elif type == 'pdf':
            with tempfile.TemporaryDirectory() as temp_dir:

                r = requests.get(filename, stream=True)
                with open(f'{temp_dir}/temp.pdf', 'ab+') as fd:
                    for chunk in r.iter_content(2000):
                        fd.write(chunk)
                    fd.seek(0)
                    b = bytearray(fd.read())
                    file_id = self.get_file_id(db, entity.id, type, platform, version, deployment_type)
                    file_key = f"{entity.id}/{file_id}"
                    extra_args = {
                        "Metadata": {
                            "x-amz-meta-content-type": 'application/x-pdf',
                            "x-amz-meta-filename": filename,
                            "x-amz-meta-extension": "pdf",
                            "x-amz-meta-type": "pdf"
                        }
                    }
                    uploaded_file = self.uploadService.upload_file(file_key, b, extra_args=extra_args)
                    file = self.create_or_replace_file(db=db, entity_id=entity.id, type=type, platform=platform, version=version, deployment_type=deployment_type,
                                                       uploaded_file=uploaded_file, requester=requester, id=file_id, original_name=filename)

                    uploaded_files = self.__upload_pdf(file_key=entity.id, file_bytes=b)
                    logger.info(f"uploaded files: {len(uploaded_files)}")
                    # Assign the file to the entity.
                    i = 0
                    for u_file in uploaded_files:
                        logger.info(f"storing file: {u_file['id']} entity_id: {entity.id}, type: {type}, platform: {platform}, version: {version}, deployment_type: {deployment_type}, id: {file_id}, filename: {filename}, var: {i}")
                        self.create_or_replace_file(db=db, entity_id=entity.id, type="pdf_image", platform=platform, version=version, deployment_type=deployment_type,
                                                    uploaded_file=u_file["file"], requester=requester, id=u_file["id"], original_name=filename, variation=i)
                        i = i + 1
        else:
            # Assign the file to the entity.
            file_id = uuid.uuid4().hex
            file = self.create_or_replace_file(db=db, entity_id=entity.id, type=type, platform=platform, version=version, deployment_type=deployment_type,
                                               uploaded_file=uploaded_file, requester=requester, id=file_id, original_name=filename)

        db.commit()

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.add_file)

        return file

    # noinspection PyShadowingNames
    async def upload_file(self, db: Session, *, requester: models.User,
                          entity: ModelType, upload: UploadFile, type: str, platform: str, version: int, deployment_type: str) -> models.File:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(models.Entity.accessibles))

        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        # Read the uploaded file stream as an array of bytes.
        b = bytearray(await upload.read())

        # Special case, use initial full image to generate diffuse texture and preview image automatically.
        if type == 'image_full_initial':
            # Upload full-sized image and assign it to the entity.
            file_id = self.get_file_id(db, entity.id, type, platform, version, deployment_type)
            file_key = f"{entity.id}/{file_id}"
            extra_args = {
                "Metadata": {
                    "x-amz-meta-content-type": upload.content_type,
                    "x-amz-meta-filename": upload.filename,
                    "x-amz-meta-extension": os.path.splitext(upload.filename)[1],
                    "x-amz-meta-type": "image-original"
                }
            }
            uploaded_file = self.uploadService.upload_file(file_key, b, extra_args=extra_args)
            file = self.create_or_replace_file(db=db, entity_id=entity.id, type='image_full', platform=platform, version=version, deployment_type=deployment_type,
                                               uploaded_file=uploaded_file, requester=requester, id=file_id, original_name=upload.filename)

            # Upload texture image and assign it to the entity.
            file_id = self.get_file_id(db, entity.id, type, platform, version, deployment_type)
            file_key = f"{entity.id}/{file_id}"
            extra_args = {
                "Metadata": {
                    "x-amz-meta-content-type": upload.content_type,
                    "x-amz-meta-filename": upload.filename,
                    "x-amz-meta-extension": os.path.splitext(upload.filename)[1],
                    "x-amz-meta-type": "image-texture2d-diffuse"
                }
            }
            uploaded_file = self.__upload_texture(file_key, b, extra_args=extra_args)
            self.create_or_replace_file(db=db, entity_id=entity.id, type='texture_diffuse', platform=platform, version=version, deployment_type=deployment_type,
                                        uploaded_file=uploaded_file, requester=requester, id=file_id)

            # Upload preview image and assign it to the entity.
            file_id = self.get_file_id(db, entity.id, type, platform, version, deployment_type)
            file_key = f"{entity.id}/{file_id}"
            extra_args = {
                "Metadata": {
                    "x-amz-meta-content-type": upload.content_type,
                    "x-amz-meta-filename": upload.filename,
                    "x-amz-meta-extension": os.path.splitext(upload.filename)[1],
                    "x-amz-meta-type": "image-preview"
                }
            }
            uploaded_file = self.__upload_preview(file_key, b, extra_args=extra_args)
            self.create_or_replace_file(db=db, entity_id=entity.id, type='image_preview', platform=platform, version=version, deployment_type=deployment_type,
                                        uploaded_file=uploaded_file, requester=requester, id=file_id)
        elif type == 'uplugin':
            file_id = self.get_file_id(db, entity.id, type, platform, version, deployment_type)
            file_key = f"{entity.id}/{file_id}"
            extra_args = {
                "Metadata": {
                    "x-amz-meta-content-type": upload.content_type,
                    "x-amz-meta-filename": upload.filename,
                    "x-amz-meta-extension": os.path.splitext(upload.filename)[1],
                    "x-amz-meta-type": "uplugin"
                }
            }
            uploaded_file = self.uploadService.upload_file(file_key, b, extra_args=extra_args)
            file = self.create_or_replace_file(db=db, entity_id=entity.id, type=type, platform=platform, version=version, deployment_type=deployment_type,
                                               uploaded_file=uploaded_file, requester=requester, id=file_id, original_name=upload.filename)
            if isinstance(entity, models.Mod):
                configuration = 'Shipping'
                platforms = ['Win64', 'Linux', 'Mac', 'Android', 'IOS']
                crud.build_job.add_pending_job(mod_id=entity.id, db=db, requester=requester, configuration=configuration, release_name=entity.release_name, platforms=platforms, map=entity.map)
        elif type == 'pdf':
            file_id = self.get_file_id(db, entity.id, type, platform, version, deployment_type)
            file_key = f"{entity.id}/{file_id}"
            extra_args = {
                "Metadata": {
                    "x-amz-meta-content-type": upload.content_type,
                    "x-amz-meta-filename": upload.filename,
                    "x-amz-meta-extension": "pdf",
                    "x-amz-meta-type": "pdf"
                }
            }
            uploaded_file = self.uploadService.upload_file(file_key, b, extra_args=extra_args)
            file = self.create_or_replace_file(db=db, entity_id=entity.id, type=type, platform=platform, version=version, deployment_type=deployment_type,
                                               uploaded_file=uploaded_file, requester=requester, id=file_id, original_name=upload.filename)

            uploaded_files = self.__upload_pdf(file_key=entity.id, file_bytes=b)
            # Assign the file to the entity.
            i = 0
            for u_file in uploaded_files:
                logger.info(f"storing file: {file_id}")
                self.create_or_replace_file(db=db, entity_id=entity.id, type="pdf_image", platform=platform, version=version, deployment_type=deployment_type,
                                            uploaded_file=u_file["file"], requester=requester, id=u_file["id"], original_name=upload.filename, variation=i)
                i = i + 1
        else:
            file_id = self.get_file_id(db, entity.id, type, platform, version, deployment_type)
            file_key = f"{entity.id}/{file_id}"
            extra_args = {
                "Metadata": {
                    "x-amz-meta-content-type": upload.content_type,
                    "x-amz-meta-filename": upload.filename,
                    "x-amz-meta-extension": os.path.splitext(upload.filename)[1],
                    "x-amz-meta-type": type
                }
            }
            if type.startswith('texture'):
                extra_args["Metadata"]["x-amz-meta-type"] = "image-texture2d-diffuse"
                uploaded_file = self.__upload_texture(file_key, b, extra_args=extra_args)
            elif type.endswith('preview') and not type.startswith('cubemap'):
                extra_args["Metadata"]["x-amz-meta-type"] = "image-preview"
                uploaded_file = self.__upload_preview(file_key, b, extra_args=extra_args)
            else:
                uploaded_file = self.uploadService.upload_file(file_key, b, extra_args=extra_args)

            # Assign the file to the entity.
            file = self.create_or_replace_file(db=db, entity_id=entity.id, type=type, platform=platform, version=version, deployment_type=deployment_type,
                                               uploaded_file=uploaded_file, requester=requester, id=file_id, original_name=upload.filename)

        db.commit()

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.upload_file)

        return file

    async def download_file(self, db: Session, *, requester: models.User, file_id: str) -> str:
        r"""Delete all file traits of the entity using specified url."""
        if not requester:
            raise EntityParameterError('no requester')

        if not file_id:
            raise EntityParameterError('no id')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        q: Query = db.query(models.File)

        try:
            uuid_obj = uuid.UUID(file_id, version=4)
        except ValueError:
            uuid_obj = None

        file_url = file_id

        if str(uuid_obj).lower() == str(file_id).lower():
            q = q.filter(models.File.id == file_id)
        else:
            file_url = unquote(file_id)
            q = q.filter(models.File.url == file_url)

        file = q.first()

        if not file:
            if "://" in file_url:
                return file_url
            else:
                return file_id

        # Get entity to check for requester entity access
        entity = self.prepare_entity(db, entity=file.entity_id, model=models.Entity, options=joinedload(models.Entity.accessibles))
        if not entity.viewable_by(requester):
            raise EntityAccessError('requester has no access to the file')

        # Forbid download of metaverse source files for viewers
        if file.type == 'uplugin' or file.type == 'uplugin_content':
            if not entity.editable_by(requester):
                raise EntityAccessError('requester has no access to the file')

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.download)

        prefix = f"https://veverse-" if os.getenv('ENVIRONMENT') == 'prod' else f"https://veverse-{os.getenv('ENVIRONMENT')}"
        if file.url.startswith(prefix) and '.s3' in file.url and 'amazonaws.com/' in file.url:
            # New file format
            download_url = self.s3Service.get_download_url(file.get_file_key())
            if download_url:
                return download_url
            else:
                raise EntityNotFoundError("file not found")
        else:
            # legacy files
            return file.url

    # noinspection PyShadowingNames
    async def delete_file_by_type(self, db: Session, *,
                                  requester: models.User,
                                  entity: ModelType,
                                  type: str) -> ModelType:
        r"""Delete file of the entity by its type."""
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not entity.deletable_by(requester):
            raise EntityAccessError('requester has no delete access to the entity')

        files: List[models.File] = db.query(models.File).filter(
            models.File.entity_id == entity.id,
            models.File.type == type
        ).all()

        for file in files:
            self.__safe_delete_file_by_url(db, url=file.url)
            db.delete(file)

        db.commit()
        db.refresh(entity)

        return entity

    # noinspection PyShadowingNames
    async def delete_file_by_url(self, db: Session, *,
                                 requester: models.User,
                                 entity: ModelType,
                                 url: str) -> ModelType:
        r"""Delete all file traits of the entity using specified url."""
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not entity.deletable_by(requester):
            raise EntityAccessError('requester has no delete access to the entity')

        files: List[models.File] = db.query(models.File).filter(
            models.File.entity_id == entity.id,
            models.File.url == url
        ).all()

        for file in files:
            # Check if there are no other file traits using the same URL so the file at the storage should be deleted.
            self.__safe_delete_file_by_url(db, url=file.url)
            db.delete(file)

        db.commit()
        db.refresh(entity)

        return entity

    # noinspection PyShadowingNames
    async def delete_file_by_id(self, db: Session, *, requester: models.User, entity: ModelType, id: str) -> ModelType:
        r"""Delete all file traits of the entity using specified url."""
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(models.Entity.accessibles))

        if not entity.deletable_by(requester):
            raise EntityAccessError('requester has no delete access to the entity')

        file: models.File = db.query(models.File).filter(models.File.entity_id == entity.id, models.File.id == id).first()

        if not file:
            raise EntityNotFoundError('no file')

        # Delete file from the storage.
        self.uploadService.delete_file(file.url)

        # Delete file trait.
        db.delete(file)
        db.commit()

        return entity

    # noinspection PyShadowingNames
    async def delete_avatar_by_id(self, db: Session, *, requester: models.User, entity: ModelType, file_id: str) -> ModelType:
        r"""Delete all file traits of the entity using specified url."""
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not entity.deletable_by(requester):
            raise EntityAccessError('requester has no delete access to the entity')

        file: models.File = db.query(models.File).filter(models.File.entity_id == entity.id, models.File.type == "image_avatar", models.File.id == file_id).first()

        if not file:
            raise EntityNotFoundError('no file')

        self.__safe_delete_file_by_url(db, url=file.url)

        # Delete file trait.
        db.delete(file)
        db.commit()

        return entity

    # noinspection PyShadowingNames
    async def delete_stored_files(self, db: Session, *, entity: Union[str, ModelType], requester: models.User) -> bool:
        if not requester:
            raise EntityParameterError('no requester')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not requester.is_admin:
            raise EntityAccessError('access denied')

        try:
            entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.files))
        except EntityNotFoundError:
            logging.log(logging.WARN, f"failed to delete files for entity: {entity}")
            return False

        for file in entity.files:
            self.uploadService.delete_file(file.url)

        return True

    async def delete_all_files_by_url(self, db: Session, *,
                                      requester: models.User,
                                      url: str) -> None:
        r"""Delete all file traits of the entity using specified url. Only admins."""
        if not requester:
            raise EntityParameterError('no requester')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not requester.is_admin:
            raise EntityAccessError('access denied')

        files: List[models.File] = db.query(models.File).filter(
            models.File.url == url
        ).all()

        for file in files:
            self.uploadService.delete_file(file.url)
            db.delete(file)

        db.commit()

        return None

    # noinspection PyShadowingNames
    def link_to_existing_file(self, db: Session, *,
                              requester: models.User,
                              entity: ModelType,
                              type: str,
                              uploaded_file: s3.UploadedFile) -> ModelType:
        """Links the object to existing file (e.g. creating previews for collections based on their objects) without replacing."""
        if not uploaded_file:
            raise EntityParameterError('no uploaded file')

        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        file = db.query(models.File).filter(
            models.File.entity_id == entity.id,
            models.File.type == type,
            models.File.url == uploaded_file.url).first()

        if file is not None:
            raise FileExistsError('file already exists')
        else:
            file = models.File()
            file.id = uuid.uuid4().hex
            file.entity_id = entity.id
            file.type = type
            file.mime = uploaded_file.mime
            file.url = uploaded_file.url

            db.add(file)
            db.commit()
            db.refresh(entity)

        return entity

    def __safe_delete_file_by_url(self, db: Session, *, url: str):
        # Delete the file from the cloud storage if there are no other avatars or other file traits with the same url.
        count = db.query(models.File).filter(models.File.url == url).count()
        if count == 1:
            self.uploadService.delete_file(url)

    def get_file_id(self, db: Session, entity_id: str, type: str, platform: Optional[str] = None, version: Optional[int] = None, deployment_type: Optional[str] = None, variation: Optional[int] = None):
        file = db.query(models.File).filter(
            models.File.entity_id == entity_id,
            models.File.type == type,
            models.File.version == version,
            models.File.deployment_type == deployment_type,
            models.File.variation == variation,
            models.File.platform == platform).first()
        if file:
            logger.info(f"file found: {file.id} {file.url}")
            return file.id
        new_id = str(uuid.uuid4())
        logger.info(f"new file: {new_id}")
        return new_id

    def create_or_replace_file(self, db: Session, entity_id: str, type: str,
                               uploaded_file: s3.UploadedFile, requester: models.User = None, id: Optional[str] = None, original_name: Optional[str] = None, platform: Optional[str] = None,
                               deployment_type: Optional[str] = None, version: Optional[int] = None, variation: Optional[int] = None) -> models.File:
        if not uploaded_file:
            raise EntityParameterError('no uploaded file')

        file = db.query(models.File).filter(
            models.File.entity_id == entity_id,
            models.File.type == type,
            models.File.version == version,
            models.File.variation == variation,
            models.File.deployment_type == deployment_type,
            models.File.platform == platform).first()

        if file is None:
            file = models.File()
            file.id = uuid.uuid4().hex if not id else id
            file.entity_id = entity_id
            file.type = type
            file.platform = platform
            file.deployment_type = deployment_type
            file.version = version
            file.variation = variation

        if id:
            file.id = id
        file.mime = uploaded_file.mime
        file.url = uploaded_file.url
        file.size = uploaded_file.size
        file.original_name = original_name
        file.deployment_type = deployment_type
        file.variation = variation
        if requester and requester.id:
            file.uploaded_by = requester.id

        db.add(file)
        db.commit()
        db.refresh(file)

        return file

    # noinspection PyShadowingNames
    def __upload_texture(self, file_key: str, file_bytes: bytearray, image_quality: Optional[int] = None, extra_args: dict = None):
        r"""Uploads the file as the power-of-two texture."""
        # Create image object
        image = Image.open(io.BytesIO(file_bytes))
        # Convert to a texture image
        image_texture = self.imageService.make_texture(image)
        # Convert texture to bytes
        image_bytes = self.imageService.to_bytes(image_texture, image.format, image_quality).getvalue()
        # Upload image file
        return self.uploadService.upload_file(file_key, image_bytes, extra_args=extra_args)

    # noinspection PyShadowingNames
    def __upload_preview(self, file_key: str, file_bytes: bytearray, image_quality: Optional[int] = None, extra_args: dict = None):
        r"""Uploads the file as the small preview image."""
        # Create image object
        image = Image.open(io.BytesIO(file_bytes))
        # Convert to a preview image
        image_preview = self.imageService.make_preview(image)
        # Convert image to bytes
        image_bytes = self.imageService.to_bytes(image_preview, image.format, image_quality).getvalue()
        # Upload image file
        return self.uploadService.upload_file(file_key, image_bytes, extra_args=extra_args)

    def __upload_pdf(self, file_key: str, file_bytes: bytearray, image_quality: Optional[int] = None, extra_args: dict = None):
        logger.info('upload pdf')
        uploaded_files = []
        # save temp image files in temp dir, delete them after we are finished
        with tempfile.TemporaryDirectory() as temp_dir:
            # convert pdf to multiple image
            logger.info('converting images')
            images = convert_from_bytes(file_bytes, output_folder=temp_dir, dpi=72)
            # save images to temporary directory
            temp_images = []
            logger.info(f'image count: {len(images)}')
            for i in range(len(images)):
                image_path = f'{temp_dir}/{i}.jpg'
                images[i].save(image_path, 'JPEG')
                temp_images.append(image_path)
                logger.info(f'image_path: {image_path}')
            # read images into pillow.Image
            imgs = list(map(Image.open, temp_images))
            i = 0
            for img in imgs:
                logger.info(f'i: {i}')
                image_bytes = self.imageService.to_bytes(img, img.format, image_quality)
                file_id = str(uuid.uuid4())
                file_res_key = f"{file_key}/{file_id}"
                logger.info(f'uploading file: {file_res_key}')
                uf = self.uploadService.upload_file(f"{file_res_key}", image_bytes.read(), extra_args=extra_args)
                uploaded_files.append({"file":uf, "id": file_id})
                i = i + 1
        logger.info(f'uploaded files: {len(uploaded_files)}')
        return uploaded_files

    # endregion

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def check_exists_by_field(self, db: Session, *, name: str, value: str) -> bool:
        r"""Use only for create, login and update."""
        if not name or not value:
            raise EntityParameterError('no field')

        if not hasattr(self.model, name):
            raise EntityParameterError('incorrect entity type')

        q = db.query(self.model).filter(getattr(self.model, name).ilike(value))

        count = q.count()

        if count > 0:
            return True

        return False

    @staticmethod
    def _omit_trait_user(trait, requester):
        r"""Omit user information from comments if the requester can't view the user."""
        if trait and hasattr(trait, 'user') and not trait.user.viewable_by(requester):
            # Get all attributes.
            keys: List[str] = list(trait.user.__dict__.keys())
            # Preserve ID and required ORM fields.
            keys.remove('id')
            keys.remove('_sa_instance_state')
            # Reset all keys.
            for k in keys:
                delattr(trait.user, k)
            # Api key and password hash are not included into key list, so reset them manually..
            trait.user.password_hash = None
            trait.user.api_key = None
            # Reset the avatar properties to default values.
            default_avatar_url = 'https://www.gravatar.com/avatar/whoamitoaskthesequestions?s=100&r=g&d=identicon'
            default_avatar_mime = 'image/png'
            trait.user.avatar.url = default_avatar_url
            trait.user.avatar.mime = default_avatar_mime
        return trait

    @staticmethod
    def get_public_fields() -> List[str]:
        return [models.Entity.id,
                models.Entity.entity_type,
                models.Entity.created_at,
                models.Entity.updated_at,
                models.Entity.public,
                models.Entity.views]

    @staticmethod
    def get_create_required_fields() -> List[str]:
        raise NotImplementedError('use derived entity class')

    @staticmethod
    def check_file_type(file_type):
        expected_file_types = ["image_preview", "image_full", "image_full_initial", "model", "texture_diffuse",
                               "texture_normal", "audio", "video", "image_avatar"]

        if file_type not in expected_file_types:
            raise EntityParameterError(f"unknown file type, allowed: [{expected_file_types}]")


entity = CRUDEntity(models.Entity)
