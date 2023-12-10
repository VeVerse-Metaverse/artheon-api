import datetime
import json
import logging
import os
import random
import re
import time
import uuid
from email.utils import parseaddr
from string import Template
from typing import Optional, Union, Dict, Any, List

from eth_account.messages import encode_defunct
from web3.auto import w3

import inject
import shortuuid
# from faker import Faker
# from faker.providers import internet, person, misc
from fastapi import UploadFile
from itsdangerous import URLSafeTimedSerializer, BadSignature
from sqlalchemy import and_, or_, Column, desc, not_, func
from sqlalchemy.orm import Session, Query, noload, aliased, lazyload, joinedload
from sqlalchemy.orm.interfaces import MapperOption
from werkzeug.security import generate_password_hash, check_password_hash

from app import models, schemas, templates, crud
from app.config import settings
from app.crud.entity import CRUDEntity, EntityBatch, EntityNotFoundError, EntityAccessError, EntityParameterError
# Faker is used to generate random user email and name when registering using device id.
from app.dependencies.auth import requester
from app.services import email, s3

# Faker.seed(int(time.time()))
# fake = Faker()
# fake.add_provider(internet)
# fake.add_provider(person)
# fake.add_provider(misc)

class VerifyError(Exception):
    pass

class VerifyMsgError(VerifyError):
    pass

class CRUDUser(CRUDEntity[models.User, schemas.UserCreate, schemas.UserUpdate]):
    email_service = inject.attr(email.Service)

    @staticmethod
    def get_public_fields() -> List[str]:
        fields = CRUDEntity.get_public_fields()
        fields.extend([models.User.name,
                       models.User.description])
        return fields

    @staticmethod
    def get_create_required_fields() -> List[str]:
        return [models.User.name.name,
                models.User.description.name]

    # region User index

    def index_with_query(self, db, *, requester, offset=0, limit=10, query=None, fields=None, filters=None, options=None) -> EntityBatch[models.User]:
        if fields is None:
            fields = ['name', 'description']

        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        # Polymorphic relation will join entity and user.
        q: Query = db.query(models.User)

        # Exclude private fields such as passwords, etc.
        # q = q.with_entities(*self.get_public_fields())

        # Filter entities invisible by the user if user is not an admin.
        if not requester.is_admin:
            # Join accessibles and apply view filters.
            q = q.join(models.Accessible, models.Accessible.entity_id == models.Entity.id, isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id))
            q = q.filter(not_(models.User.is_internal))

        # Filter by the search query if required.
        if query:
            if not bool(re.match('^[a-zA-Z0-9@.\\-_ #]+$', query)):
                raise EntityParameterError('query contains forbidden characters')
            else:
                f = [getattr(self.model, field).ilike(f"%{query}%") for field in fields]
                q = q.filter(or_(*f))

        # Sort by created date.
        q = q.order_by(models.Entity.created_at)

        # Get total count of entities falling under the query.
        total = self.get_total(q, self.model.id)

        if options and isinstance(options, MapperOption):
            q.options(options)

        # Get users (we get tuples here because we used with_entities above).
        users = q.offset(offset).limit(limit).all()

        # Form entity batch and return.
        return EntityBatch[models.User](users, offset, limit, total)

    def index_admins(self, db: Session, *, requester: models.User,
                     offset: int = 0, limit: int = 10) -> EntityBatch[models.User]:
        r"""Use only with UserAdminRef scheme."""
        if not requester:
            raise EntityParameterError('no requester')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not requester.is_admin:
            raise EntityAccessError('access denied')

        # Polymorphic will join entity and user.
        q: Query = db.query(models.User)

        # Exclude private fields.
        q = q.with_entities(*self.get_public_fields(), models.User.is_admin)

        q = q.filter(models.User.is_admin == True)

        q = q.order_by(models.Entity.created_at)

        total = self.get_total(q, self.model.id)

        admins = q.offset(offset).limit(limit).all()

        return EntityBatch[models.User](admins, offset, limit, total)

    def index_muted(self, db: Session, *, requester: models.User,
                    offset: int = 0, limit: int = 10) -> EntityBatch[models.User]:
        r"""Use only with UserMutedRef scheme."""
        if not requester:
            raise EntityParameterError('no requester')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        # Polymorphic relation will join entity and user.
        q: Query = db.query(models.User)

        # Exclude private fields.
        q = q.with_entities(*self.get_public_fields(), models.User.is_muted)

        # Filter only muted users.
        q = q.filter(models.User.is_muted == True)

        q = q.order_by(models.Entity.created_at)

        total = self.get_total(q, self.model.id)

        users = q.offset(offset).limit(limit).all()

        return EntityBatch[models.User](users, offset, limit, total)

    def index_banned(self, db: Session, *, requester: models.User,
                     offset: int = 0, limit: int = 10) -> EntityBatch[models.User]:
        r"""Use only with UserBannedRef scheme."""
        if not requester:
            raise EntityParameterError('no requester')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        # Polymorphic relation will join entity and user.
        q: Query = db.query(models.User)

        # Exclude private fields.
        q = q.with_entities(*self.get_public_fields(), models.User.is_banned)

        # Filter only banned users.
        q = q.filter(models.User.is_banned == True)

        q = q.order_by(models.Entity.created_at)

        total = self.get_total(q, self.model.id)

        users = q.offset(offset).limit(limit).all()

        return EntityBatch[models.User](users, offset, limit, total)

    # endregion

    # region Related entities index

    # region Entities

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_entities(self, db: Session, *, requester: models.User, user: Union[str, models.User], model=models.Entity, offset: int, limit: int) -> EntityBatch[models.Entity]:
        if not requester:
            raise EntityParameterError('no requester')

        if not user:
            raise EntityParameterError('no user')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        user = self.prepare_user(db, user=user)

        if not user.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        a = aliased(models.Accessible, name='a')

        q: Query = db.query(model)

        # Join accessible for the owner.
        q = q.join(a, and_(a.entity_id == model.id, a.user_id == user.id))
        q = q.filter(a.is_owner == True)

        # Filter entities invisible by the requester if the requester is not an admin.
        if not requester.is_admin:
            ra = aliased(models.Accessible, name='ra')
            q = q.join(ra, and_(ra.entity_id == model.id, ra.user_id == requester.id), isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id, accessible_model=ra))

        # Lazy load entity owner.
        if not user.id == requester.id:
            q = q.options(lazyload(model.owner))

        q = q.order_by(models.Entity.created_at)

        total = self.get_total(q, model.id)

        entities = q.offset(offset).limit(limit).all()

        return EntityBatch[model](entities, offset, limit, total)

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_entities_with_query(self, db: Session, *, requester: models.User, user: Union[str, models.User], model=models.Entity, offset: int, limit: int, query: Optional[str],
                                  fields: Optional[List[str]] = None) -> EntityBatch[models.Entity]:
        if not requester:
            raise EntityParameterError('no requester')

        if not user:
            raise EntityParameterError('no user')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        user = self.prepare_user(db, user=user)

        if not user.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        a = aliased(models.Accessible, name='a')

        q: Query = db.query(model)

        # Join accessible for the owner.
        q = q.join(a, and_(a.entity_id == model.id, a.user_id == user.id))
        q = q.filter(a.is_owner == True)

        # Filter entities invisible by the requester if the requester is not an admin.
        if not requester.is_admin:
            ra = aliased(models.Accessible, name='ra')
            q = q.join(ra, and_(ra.entity_id == model.id, ra.user_id == requester.id), isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id, accessible_model=ra))

        if query:
            if not bool(re.match('^[a-zA-Z0-9@.\\-_ #]+$', query)):
                raise EntityParameterError('query contains forbidden characters')
            else:
                f = [getattr(model, field).ilike(f"%{query}%") for field in fields]
                q = q.filter(or_(*f))

        # Lazy load entity owner.
        if not user.id == requester.id:
            q = q.options(lazyload(model.owner))

        q = q.order_by(models.Entity.created_at)

        total = self.get_total(q, model.id)

        entities = q.offset(offset).limit(limit).all()

        return EntityBatch[model](entities, offset, limit, total)

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_entities_with_query_sorted(self, db: Session, *, requester: models.User, user: Union[str, models.User], model=models.Entity, offset: int, limit: int, query: Optional[str],
                                         sort: int = -1,
                                         fields: Optional[List[str]] = None) -> EntityBatch[models.Entity]:
        if not requester:
            raise EntityParameterError('no requester')

        if not user:
            raise EntityParameterError('no user')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        user = self.prepare_user(db, user=user)

        if not user.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        a = aliased(models.Accessible, name='a')

        q: Query = db.query(model)

        # Join accessible for the owner.
        q = q.join(a, and_(a.entity_id == model.id, a.user_id == user.id))
        q = q.filter(a.is_owner == True)

        # Filter entities invisible by the requester if the requester is not an admin.
        if not requester.is_admin:
            ra = aliased(models.Accessible, name='ra')
            q = q.join(ra, and_(ra.entity_id == model.id, ra.user_id == requester.id), isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id, accessible_model=ra))

        if query:
            if not bool(re.match('^[a-zA-Z0-9@.\\-_ #]+$', query)):
                raise EntityParameterError('query contains forbidden characters')
            else:
                f = [getattr(model, field).ilike(f"%{query}%") for field in fields]
                q = q.filter(or_(*f))

        # Lazy load entity owner.
        if not user.id == requester.id:
            q = q.options(lazyload(model.owner))

        if sort > 0:
            q = q.order_by(models.Entity.created_at)
        elif sort < 0:
            q = q.order_by(desc(models.Entity.created_at))

        total = self.get_total(q, model.id)

        entities = q.offset(offset).limit(limit).all()

        return EntityBatch[model](entities, offset, limit, total)

    # endregion

    # region Liked entities

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_liked_entities(self, db: Session, *, requester: models.User, user: Union[str, models.User], model=models.Entity, offset: int, limit: int) -> EntityBatch[models.Entity]:
        if not requester:
            raise EntityParameterError('no requester')

        if not user:
            raise EntityParameterError('no user')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        user = self.prepare_user(db, user=user)

        if not user.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        accessible_alias = aliased(models.Accessible, name='a')
        likable_alias = aliased(models.Likable, name='l')

        q: Query = db.query(model)

        # Join accessible for the owner.
        q = q.join(accessible_alias, and_(accessible_alias.entity_id == model.id, accessible_alias.user_id == user.id))
        q = q.filter(accessible_alias.is_owner == True)

        # Filter entities invisible by the requester if the requester is not an admin.
        if not requester.is_admin:
            ra = aliased(models.Accessible, name='ra')
            q = q.join(ra, and_(ra.entity_id == model.id, ra.user_id == requester.id), isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id, accessible_model=ra))

        # Filter entities liked by the user.
        q.join(likable_alias, and_(likable_alias.entity_id == model.id, likable_alias.user_id == user.id))
        q.filter(likable_alias.value > 0)

        # Lazy load entity owner.
        q = q.options(lazyload(model.owner))

        q = q.order_by(models.Entity.created_at)

        total = self.get_total(q, model.id)

        entities = q.offset(offset).limit(limit).all()

        return EntityBatch[model](entities, offset, limit, total)

    # endregion

    # region Avatars

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_avatars(self, db: Session, *, requester: models.User, user: Union[str, models.User],
                      offset: int, limit: int) -> EntityBatch[models.File]:
        if not requester:
            raise EntityParameterError('no requester')

        if not user:
            raise EntityParameterError('no user')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        user = self.prepare_user(db, user=user)

        if not user.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        q: Query = db.query(models.File)

        q = q.filter(models.File.type == "image_avatar", models.File.entity_id == user.id)

        q = q.order_by(desc(models.File.created_at))

        total = self.get_total(q, models.File.id)

        files = q.offset(offset).limit(limit).all()

        return EntityBatch[models.File](files, offset, limit, total)

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_avatar_meshes(self, db: Session, *, requester: models.User, user: Union[str, models.User],
                            offset: int, limit: int) -> EntityBatch[models.File]:
        if not requester:
            raise EntityParameterError('no requester')

        if not user:
            raise EntityParameterError('no user')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        user = self.prepare_user(db, user=user)

        if not user.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        q: Query = db.query(models.File)

        q = q.filter(models.File.type == "mesh_avatar", models.File.entity_id == user.id)

        q = q.order_by(desc(models.File.created_at))

        total = self.get_total(q, models.File.id)

        files = q.offset(offset).limit(limit).all()

        return EntityBatch[models.File](files, offset, limit, total)

    # endregion

    # region Followers

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_followers(self, db: Session, *, requester: models.User, user: Union[str, models.User], offset: int, limit: int, include_friends: bool = True) -> EntityBatch[models.User]:
        if not requester:
            raise AttributeError('no requester')

        if not user:
            raise AttributeError('no user')

        # if not requester.is_active:
        #     raise PermissionError('inactive')

        if requester.is_banned:
            raise PermissionError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        user = self.prepare_user(db, user=user)

        if not user.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        q: Query = db.query(models.Follower)

        # Join users who follow the user.
        # if include_friends:
        q = q.join(models.User, and_(models.Follower.follower_id == models.User.id, models.Follower.leader_id == user.id))
        # else:
        #     q = q.join(models.User, and_(and_(models.Follower.follower_id == models.User.id, models.Follower.leader_id == user.id),
        #                                  and_(models.Follower.leader_id == models.User.id, models.Follower.follower_id != user.id)))

        # if not include_friends:
        #     q = q.filter(models.Follower.follower_id != user.id)

        # Filter entities invisible by the requester if the requester is not an admin.
        if not requester.is_admin:
            ra = aliased(models.Accessible, name='ra')
            q = q.join(ra, and_(ra.entity_id == models.User.id, ra.user_id == requester.id), isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id, accessible_model=ra))

        total = self.get_total(q, models.User.id)

        followers = q.with_entities(models.User).offset(offset).limit(limit).all()

        return EntityBatch[models.User](followers, offset, limit, total)

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_leaders(self, db: Session, *, requester: models.User, user: Union[str, models.User],
                      offset: int, limit: int, include_friends: bool = True) -> EntityBatch[models.User]:
        if not requester:
            raise AttributeError('no requester')

        if not user:
            raise AttributeError('no user')

        # if not requester.is_active:
        #     raise PermissionError('inactive')

        if requester.is_banned:
            raise PermissionError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        user = self.prepare_user(db, user=user)

        if not user.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        q: Query = db.query(models.Follower)

        # Join users who lead the user.
        q = q.join(models.User, and_(models.Follower.leader_id == models.User.id, models.Follower.follower_id == user.id))

        # if not include_friends:
        #     q = q.filter(models.Follower.leader_id != user.id)

        # Filter entities invisible by the requester if the requester is not an admin.
        if not requester.is_admin:
            ra = aliased(models.Accessible, name='ra')
            q = q.join(ra, and_(ra.entity_id == models.User.id, ra.user_id == requester.id), isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id, accessible_model=ra))

        total = self.get_total(q, models.User.id)

        leaders = q.with_entities(models.User).offset(offset).limit(limit).all()

        return EntityBatch[models.User](leaders, offset, limit, total)

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def index_friends(self, db: Session, *, requester: models.User, user: Union[str, models.User],
                      offset: int, limit: int) -> EntityBatch[models.User]:
        if not requester:
            raise AttributeError('no requester')

        if not user:
            raise AttributeError('no user')

        # if not requester.is_active:
        #     raise PermissionError('inactive')

        if requester.is_banned:
            raise PermissionError('banned')

        offset, limit = self.prepare_offset_limit(offset, limit)

        user = self.prepare_user(db, user=user)

        if not user.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        # Leaders subquery.
        fl = aliased(models.Follower, name='fl')
        ql: Query = db.query(fl)
        ql = ql.join(models.User, and_(fl.leader_id == models.User.id, fl.follower_id == user.id))
        sq_l = ql.subquery(name='l')

        # Followers subquery.
        ff = aliased(models.Follower, name='ff')
        qf: Query = db.query(ff)
        qf = qf.join(models.User, and_(ff.follower_id == models.User.id, ff.leader_id == user.id))
        sq_f = qf.subquery(name='f')

        # Form query using inner join between two sub-queries and then join users.
        q = db.query(models.User). \
            select_from(sq_l). \
            join(sq_f, and_(sq_l.c.leader_id == sq_f.c.follower_id, sq_f.c.leader_id == sq_l.c.follower_id)). \
            join(models.User, sq_l.c.leader_id == models.User.id)

        # Filter entities invisible by the requester if the requester is not an admin.
        if not requester.is_admin:
            ra = aliased(models.Accessible, name='ra')
            q = q.join(ra, and_(ra.entity_id == models.User.id, ra.user_id == requester.id), isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id, accessible_model=ra))

        total = self.get_total(q, models.User.id)

        leaders = q.offset(offset).limit(limit).all()

        return EntityBatch[models.User](leaders, offset, limit, total)

    # endregion

    # endregion

    # region Authentication Helpers

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def _get_by_email_for_auth(self, db: Session, *, email: str) -> Optional[models.User]:
        r"""Must be used only for authentication as it includes private fields for authentication check."""
        if not email:
            raise EntityParameterError('no email')

        user: models.User = db.query(models.User).filter(
            models.User.email == email
        ).first()

        if not user:
            raise EntityNotFoundError('user does not exist')

        return user

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def _get_by_email(self, db: Session, *, email: str) -> Optional[models.User]:
        if not email:
            raise EntityParameterError('no email')

        user: models.User = db.query(models.User).filter(
            models.User.email == email
        ).first()

        if not user:
            raise EntityNotFoundError('user does not exist')

        return user

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def check_exists_by_email_or_name(self, db: Session, *, email: str, name: str) -> bool:
        r"""Use only for create user and login."""
        if not (email or name):
            raise EntityParameterError('no email or name')

        count: int = db.query(models.User).filter(or_(models.User.email == email, models.User.name.ilike(name))).count()

        if count > 0:
            return True

        return False

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def check_exists_by_email(self, db: Session, *, email: str) -> bool:
        r"""Use only for create user and login."""
        if not (email):
            raise EntityParameterError('no email')

        count: int = db.query(models.User).filter(models.User.email == email).count()

        if count > 0:
            return True

        return False

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def check_invited_by_email(self, db: Session, *, email: str) -> bool:
        r"""Use only for create user and login."""
        if not (email):
            raise EntityParameterError('no email')

        count: int = db.query(models.Invitation).filter(models.Invitation.email == email).count()

        if count > 0:
            return True

        return False

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def check_exists_by_field(self, db: Session, *, name: str) -> bool:
        r"""Use only for create user and login."""
        if not name:
            raise EntityParameterError('no name')

        count: int = db.query(self.model).filter(self.model.name.ilike(name)).count()

        if count > 0:
            return True

        return False

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def check_exists_by_device_id(self, db: Session, *, device_id: str = '') -> bool:
        r"""Use only for create user and login."""
        if not device_id:
            return False

        user: models.User = db.query(models.User).filter(models.User.device_id == device_id).first()

        if user:
            return True

        return False

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def _get_by_device_id(self, db: Session, *, device_id: str) -> Optional[models.User]:
        r"""Use only for create user and login."""
        if not device_id:
            raise EntityParameterError('no device id')

        user: models.User = db.query(models.User).options(
            noload(*self.__private_fields)
        ).filter(
            models.User.device_id == device_id
        ).first()

        if not user:
            user = self._get_by_device_id(db, device_id='XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX')

        if not user:
            raise EntityNotFoundError('user does not exist')

        return user

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def authenticate(self, db: Session, *, email: str, password: str, device_id: str) -> Optional[models.User]:
        if email is None:
            # Authenticate using device id.
            user = self._get_by_device_id(db, device_id=device_id)
            if not user:
                raise EntityNotFoundError('user does not exist')
        else:
            (_, validated_email) = parseaddr(email)
            if not '@' in validated_email:
                raise EntityAccessError('invalid email or password')

            # Get the user by email for authentication.
            user = self._get_by_email_for_auth(db, email=validated_email)
            if not user:
                raise EntityNotFoundError('user does not exist')
            if not check_password_hash(user.password_hash, password):
                raise EntityAccessError('invalid email or password')

        self.grant_experience(db, requester=user, experience=settings.experience.rewards.login)

        return user

    # noinspection PyMethodMayBeStatic,PyShadowingNames
    def verifySignedMsg(self, db: Session, *, requester: models.User, address: str, signature: str, message: str, email: str = None) -> Optional[Any]:
        # The juicy bits. Here I try to verify the signature they sent.
        message = encode_defunct(text=message)
        signed_address = (w3.eth.account.recover_message(message, signature=signature))

        # Same wallet address means same user. I use the cached address here.
        if address == signed_address:
            # Do what you will
            # You can generate the JSON access and refresh tokens here

            if email is not None:
                (_, validated_email) = parseaddr(email)
                if not '@' in validated_email:
                    raise EntityAccessError('invalid email')

                user = self._get_by_email(db=db, email=email)
            else:
                user = self.get_by_eth_address(db, requester=requester, address=address)

            return {"verified": True, "user": user}
        else:
            return {"verified": False, "user": None}

        self.grant_experience(db, requester=user, experience=settings.experience.rewards.verify_signed_msg)

    # endregion

    # region CRUD

    # noinspection PyShadowingNames
    def get(self, db: Session, *, requester: models.User, id: str, options=None) -> Optional[models.User]:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not self.is_valid_uuid(id):
            raise EntityParameterError('invalid id')

        # Polymorphic relation will join entity and user.
        q: Query = db.query(self.model)

        # Exclude private fields.
        # q = q.with_entities(*self.get_public_fields(), self.model.avatar)

        # Filter entities invisible by the user if user is not an admin.
        # if not requester.is_admin:
        # Join accessibles and apply view filters.
        # q = q.join(models.Accessible, and_(models.Accessible.entity_id == models.Entity.id, models.Entity.id == id), isouter=True)
        # q = q.filter(*self.make_can_view_filters(requester.id))

        q = q.filter(self.model.id == id)

        user: models.User = q.first()

        if not user:
            raise EntityNotFoundError('not found')

        return user

    # noinspection PyShadowingNames
    def get_by_eth_address(self, db: Session, *, requester: models.User, address: str) -> Optional[models.User]:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        # Polymorphic relation will join entity and user.
        q: Query = db.query(self.model)

        # Exclude private fields.
        # q = q.with_entities(*self.get_public_fields(), self.model.avatar)

        # Filter entities invisible by the user if user is not an admin.
        # if not requester.is_admin:
        # Join accessibles and apply view filters.
        # q = q.join(models.Accessible, and_(models.Accessible.entity_id == models.Entity.id, models.Entity.id == id), isouter=True)
        # q = q.filter(*self.make_can_view_filters(requester.id))

        q = q.filter(func.lower(self.model.eth_address) == func.lower(address))

        user: models.User = q.first()

        # if not user:
        #     raise EntityNotFoundError('not found')

        return user

    # noinspection PyShadowingNames
    def create(self, db: Session, *, requester: models.User = None, entity: schemas.UserCreate, **data: Any) -> models.User:
        if not entity.name:
            raise EntityParameterError('no name')

        if not entity.email:
            raise EntityParameterError('no email')

        if not entity.password:
            raise EntityParameterError('no password')

        if not self._check_password_str_parameter(entity.password):
            raise EntityParameterError('invalid password')

        # Invitation is optional.
        # if not entity.invite_code:
        #     raise EntityParameterError('no invite code')

        invitation: models.Invitation = db.query(models.Invitation).filter(models.Invitation.email == entity.email, models.Invitation.code == f"{entity.invite_code}".upper()).first()
        # if not invitation:
        #     raise EntityNotFoundError('no invitation')

        if self.check_exists_by_email(db, email=entity.email):
            raise EntityParameterError('email is not available')

        if self.check_exists_by_field(db, name=entity.name):
            raise EntityParameterError('name is not available')

        # We don't use requester here as there can't be any at user registration.
        user = models.User(
            id=uuid.uuid4().hex,
            api_key=uuid.uuid4().hex,
            email=entity.email,
            password_hash=generate_password_hash(entity.password),
            name=entity.name,
            ip=data.get('ip', None),
            is_active=False,  # Activate by email
            is_admin=False,
            is_muted=False,
            is_banned=False,
            public=True,  # New users are public by default
            allow_emails=True,  # Allow emails by default, so user can receive activation emails, e.g.
            experience=0,
        )
        db.add(user)
        db.commit()

        self.create_default_persona(db, requester=user)

        token = self.generate_confirmation_token(user.email)
        env = os.getenv('ENVIRONMENT')
        if env == 'prod':
            link = f"https://api.veverse.com/users/activate/{token}"
        elif env == 'test':
            link = f"https://test.api.veverse.com/users/activate/{token}"
        else:
            link = f"https://dev.api.veverse.com/users/activate/{token}"
        text_template_str = templates.email.activation_text
        text_template = Template(text_template_str)
        text = text_template.substitute(name=user.name, link=link)

        html_template_str = templates.email.activation_html
        html_template = Template(html_template_str)
        html = html_template.substitute(name=user.name, link=link)

        result = self.email_service.send_to_user(subject="Metaverse Registration Confirmation", text=text, html=html, sender_email="no-reply@w3mvrs.com", receiver=user)
        if not result:
            logging.warning(f"failed to send activation email to a user: {user.email}, {user.id}")

        # Update invitation user id and joined time.
        if (invitation):
            invitation.user_id = user.id
            invitation.joined_at = datetime.datetime.now()

            # Update invitation
            db.add(invitation)
            db.commit()

        return user

    # noinspection PyShadowingNames
    def confirm_wallet_with_token(self, db: Session, *, address: str, token: str) -> models.User:
        try:
            email = self.confirm_token(token)
        except BadSignature:
            raise EntityNotFoundError('confirmation link is invalid or has expired')

        user: models.User = db.query(models.User).filter(models.User.email == email).first()

        if user.is_address_confirmed:
            raise EntityParameterError('already confirmed')
        else:
            user.is_address_confirmed = True
            user.eth_address = address
            db.add(user)
            db.commit()

        return user

    # noinspection PyShadowingNames
    def activate_with_token(self, db: Session, *, token: str) -> models.User:
        try:
            email = self.confirm_token(token)
        except BadSignature:
            raise EntityNotFoundError('activation link is invalid or has expired')

        user: models.User = db.query(models.User).filter(models.User.email == email).first()

        if user.is_active:
            raise EntityParameterError('already activated')
        else:
            user.is_active = True
            user.activated_at = datetime.datetime.now()
            db.add(user)

            # Create an invitation for the new user. Fill only inviter id and created at for now.
            invitation = models.Invitation(
                id=uuid.uuid4().hex,
                inviter_id=user.id,
                created_at=datetime.datetime.now()
            )
            db.add(invitation)
            db.commit()

        inviter = db.query(models.User).join(models.Invitation, models.User.id == models.Invitation.inviter_id).first()
        if inviter:
            self.grant_experience(db, requester=inviter, experience=settings.experience.rewards.invite_join)

        # todo: Register in mailchimp

        return user

    # noinspection PyShadowingNames
    def activate_by_email_internal(self, db: Session, *, email: str) -> models.User:
        user: models.User = db.query(models.User).filter(models.User.email == email).first()

        if user.is_active:
            raise EntityParameterError('already activated')
        else:
            user.is_active = True
            user.activated_at = datetime.datetime.now()
            db.add(user)

            # Create an invitation for the new user. Fill only inviter id and created at for now.
            invitation = models.Invitation(
                id=uuid.uuid4().hex,
                inviter_id=user.id,
                created_at=datetime.datetime.now()
            )
            db.add(invitation)
            db.commit()

        inviter = db.query(models.User).join(models.Invitation, models.User.id == models.Invitation.inviter_id).first()
        if inviter:
            self.grant_experience(db, requester=inviter, experience=settings.experience.rewards.invite_join)

        # todo: Register in mailchimp

        return user

    def invite(self, db: Session, *, requester: models.User, email: str) -> bool:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not email:
            raise EntityParameterError('no email')

        if not self.check_email(requester.email):
            raise EntityParameterError('invalid email')

        invitation = self.get_unused_invite(db, requester=requester)

        if not invitation:
            raise EntityParameterError('no unused invites')

        if self.check_exists_by_email(db, email=email):
            raise EntityParameterError('user already registered')

        if self.check_invited_by_email(db, email=email):
            raise EntityParameterError('user already has been invited')

        # Update invitation with invited user email.
        invitation.email = email
        db.add(invitation)
        db.commit()

        link = f"artheon:///register?email={email}&code={invitation.code}"
        download_windows = f"https://api.veverse.com/download/windows?source=email&invite={invitation.code}"
        download_mac = f"https://api.veverse.com/download/mac?source=email&invite={invitation.code}"
        download_linux = f"https://api.veverse.com/download/linux?source=email&invite={invitation.code}"

        text_template_str = templates.email.invitation_text
        text_template = Template(text_template_str)
        text = text_template.substitute(name=email, inviter=requester.name, link=link, download_windows=download_windows, download_mac=download_mac, download_linux=download_linux,
                                        code0=invitation.code[0], code1=invitation.code[1], code2=invitation.code[2], code3=invitation.code[3], code4=invitation.code[4])

        html_template_str = templates.email.invitation_html
        html_template = Template(html_template_str)
        html = html_template.substitute(name=email, inviter=requester.name, link=link, download_windows=download_windows, download_mac=download_mac, download_linux=download_linux,
                                        code0=invitation.code[0], code1=invitation.code[1], code2=invitation.code[2], code3=invitation.code[3], code4=invitation.code[4])

        result = self.email_service.send(subject="VeVerse Invitation", text=text, html=html, sender_email="no-reply@veverse.com", receiver_emails=email)
        if not result:
            logging.warning(f"failed to send invitation email to {email}")
            return False

        self.grant_experience(db, requester=requester, experience=settings.experience.rewards.invite_sent)

        return True

    def update(self, db: Session, *, requester: models.User, entity: Union[str, models.User], patch: Union[schemas.UserUpdate, Dict[str, Any]], unique_fields: List[str] = None):
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_user(db, user=entity)

        if not entity.owned_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        if isinstance(patch, dict):
            patch = patch
        else:
            patch = patch.dict(exclude_unset=True)

        if not (patch["name"] or patch["description"]):
            raise EntityParameterError("nothing to update")

        # Check that name is available if user changed vis name.
        if requester.name != patch['name']:
            if self.check_exists_by_field(db, name=patch["name"]):
                raise EntityParameterError("name unavailable")

        if patch["name"]:
            setattr(requester, "name", patch["name"])

        if patch["description"]:
            setattr(requester, "description", patch["description"])

        db.add(requester)
        db.commit()
        db.refresh(requester)

        self.grant_experience(db, requester=requester, experience=settings.experience.rewards.update)

        return requester

    def update_eth_account(self, db: Session, *, requester: models.User, eth_account: str):
        if not eth_account:
            raise EntityParameterError('no account')

        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        requester.eth_account = eth_account

        db.add(requester)
        db.commit()

        self.grant_experience(db, requester=requester, experience=settings.experience.rewards.update)

        return requester

    def delete(self, db: Session, *, requester: models.User, entity: Union[str, models.User]):
        if not requester.is_super_admin():
            raise EntityAccessError('access denied')

        super().delete(db, requester=requester, entity=entity)

    def update_password(self, db: Session, *, requester: models.User, entity: Union[str, models.User], patch: schemas.UserUpdatePassword) -> bool:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_user(db, user=entity)

        if not entity.owned_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        # Create a JSON-compatible dict.
        if isinstance(patch, dict):
            patch = patch
        else:
            patch = patch.dict(exclude_unset=True)

        # Check that the password provided.
        if "password" not in patch:
            raise EntityParameterError("no password")

        # Check that the new password provided.
        if "new_password" not in patch:
            raise EntityParameterError("no new password")

        # Check that the new password confirmation provided.
        if "new_password_confirmation" not in patch:
            raise EntityParameterError("no password confirmation")

        # Check that the new password differs from the old password.
        if patch["password"] == patch["new_password"]:
            raise EntityParameterError("a new password must differ from the old one")

        # Check that the new password and confirmation match.
        if patch["new_password"] != patch["new_password_confirmation"]:
            raise EntityParameterError("the password confirmation does not match the new password")

        if not check_password_hash(entity.password_hash, patch["password"]):
            raise EntityAccessError('invalid credentials')

        # Hash the new password to update.
        patch["password_hash"] = generate_password_hash(patch["new_password"])

        # Update password hash with the.
        setattr(entity, "password_hash", patch["password_hash"])

        # Store the entity in the database.
        db.add(entity)
        db.commit()

        return True

    async def upload_avatar(self, db: Session, *, requester: models.User, entity: Union[str, models.User], upload_file: UploadFile) -> models.File:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_user(db, user=entity)

        if not entity.owned_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        if not upload_file:
            raise EntityParameterError('no uploaded file')

        b = bytearray(await upload_file.read())

        filetype = "image_avatar"

        file_id = str(uuid.uuid4())
        file_key = f"{entity.id}/{file_id}"

        extra_args = {
            "Metadata": {
                "x-amz-meta-content-type": upload_file.content_type,
                "x-amz-meta-filename": upload_file.filename,
                "x-amz-meta-extension": os.path.splitext(upload_file.filename)[1],
                "x-amz-meta-type": "image-avatar"
            }
        }
        uploaded_file = self.uploadService.upload_file(file_key, b, extra_args=extra_args)

        file = self.create_or_replace_file(db=db, entity_id=entity.id, type=filetype, uploaded_file=uploaded_file, requester=requester, id=file_id)

        self.grant_experience(db, requester=requester, experience=settings.experience.rewards.upload_avatar)

        return file

    async def delete_avatar(self, db: Session, *, requester: models.User, entity: Union[str, models.User], id: str):
        if not requester:
            raise EntityParameterError('no requester')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_user(db, user=entity)

        if not entity.owned_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        if not id:
            raise EntityParameterError('no avatar id')

        await self.delete_avatar_by_id(db, requester=requester, entity=entity, file_id=id)

    def toggle_state(self, db: Session, *, requester: models.User, entity: Union[str, models.User], key: str, value: str) -> bool:
        r"""Admin only."""
        if not requester:
            raise EntityParameterError("no requester")

        if not entity:
            raise EntityParameterError("no entity")

        if not requester.is_active:
            raise EntityAccessError("inactive")

        if requester.is_banned:
            raise EntityAccessError("banned")

        if not requester.is_admin:
            raise EntityAccessError("access denied")

        entity = self.prepare_user(db, user=entity)

        if not entity.editable_by(requester):
            raise EntityAccessError("requester has no edit access to the entity")

        # Allow to modify only these keys.
        if key not in ["is_muted", "is_banned", "is_active"]:
            raise EntityAccessError("no state")

        # Do not modify and return if it already set to desired value.
        if getattr(entity, key) == value:
            return False

        # Update password hash with the.
        setattr(entity, key, value)

        # Store the entity in the database.
        db.add(entity)
        db.commit()
        db.refresh(entity)

        return True

    def follow(self, db: Session, *, requester: models.User, entity: Union[str, models.User]):
        if not requester:
            raise EntityParameterError("no requester")

        if not entity:
            raise EntityParameterError("no entity")

        # if not requester.is_active:
        #     raise EntityAccessError("inactive")

        if requester.is_banned:
            raise EntityAccessError("banned")

        entity = self.prepare_user(db, user=entity)

        if not entity.viewable_by(requester):
            raise EntityAccessError("requester has no view access to the entity")

        # Check if we already follow the entity.
        q = db.query(models.Follower)
        q = q.filter(models.Follower.follower_id == requester.id)
        q = q.filter(models.Follower.leader_id == entity.id)

        is_following = q.count() > 0

        if is_following:
            return False
        else:
            follower = models.Follower(id=uuid.uuid4().hex, leader_id=entity.id, follower_id=requester.id)
            db.add(follower)
            db.commit()

        self.grant_experience(db, requester=requester, experience=settings.experience.rewards.follow)

        return True

    def unfollow(self, db: Session, *, requester: models.User, entity: Union[str, models.User]):
        if not requester:
            raise EntityParameterError("no requester")

        if not entity:
            raise EntityParameterError("no entity")

        # if not requester.is_active:
        #     raise EntityAccessError("inactive")

        if requester.is_banned:
            raise EntityAccessError("banned")

        entity = self.prepare_user(db, user=entity)

        if not entity.viewable_by(requester):
            raise EntityAccessError("requester has no view access to the entity")

        # Check if we already follow the entity.
        q = db.query(models.Follower)
        q = q.filter(models.Follower.follower_id == requester.id)
        q = q.filter(models.Follower.leader_id == entity.id)

        follower = q.first()

        if not follower:
            return False
        else:
            db.delete(follower)
            db.commit()

        self.grant_experience(db, requester=requester, experience=settings.experience.rewards.update)

        return True

    def follows(self, db: Session, *, requester: models.User, follower: Union[str, models.User], leader: Union[str, models.User]):
        if not requester:
            raise EntityParameterError("no requester")

        if not follower:
            raise EntityParameterError("no follower")

        if not leader:
            raise EntityParameterError("no leader")

        # if not requester.is_active:
        #     raise EntityAccessError("inactive")

        if requester.is_banned:
            raise EntityAccessError("banned")

        # Follower
        follower = self.prepare_user(db, user=follower)

        # Leader
        leader = self.prepare_user(db, user=leader)

        if not leader.viewable_by(requester) or not follower.viewable_by(requester):
            raise EntityAccessError("requester has no view access to the entity")

        # Check if we already follow the entity.
        q = db.query(models.Follower)
        q = q.filter(models.Follower.follower_id == follower.id)
        q = q.filter(models.Follower.leader_id == leader.id)

        return q.count() > 0

    # noinspection PyShadowingNames
    def create_persona(self, db: Session, *, requester: models.User, entity: Union[str, models.User], source: schemas.PersonaUpdate) -> models.Persona:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not source:
            raise EntityParameterError('no persona')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        try:
            json.loads(source.configuration)
        except json.decoder.JSONDecodeError:
            raise EntityParameterError('invalid configuration JSON')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        persona: models.Persona = models.Persona()
        if persona.id is None:
            persona.id = uuid.uuid4().hex

        # Create an accessible trait for the comment.
        accessible = models.Accessible()
        accessible.entity_id = persona.id
        accessible.user_id = requester.id
        accessible.is_owner = True
        accessible.can_view = True
        accessible.can_edit = True
        accessible.can_delete = True

        # All comments are public by default.
        persona.public = True
        persona.user_id = requester.id
        persona.name = source.name
        persona.type = source.type
        persona.configuration = source.configuration

        db.add(persona)
        db.add(accessible)
        db.commit()
        db.refresh(persona)

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.add_persona)

        return persona

    # noinspection PyShadowingNames
    def create_default_persona(self, db: Session, *, requester: models.User) -> models.Persona:
        if not requester:
            raise EntityParameterError('no requester')

        persona: models.Persona = models.Persona()
        if persona.id is None:
            persona.id = uuid.uuid4().hex

        # Create an accessible trait for the comment.
        accessible = models.Accessible()
        accessible.entity_id = persona.id
        accessible.user_id = requester.id
        accessible.is_owner = True
        accessible.can_view = True
        accessible.can_edit = True
        accessible.can_delete = True

        # All comments are public by default.
        persona.public = True
        persona.user_id = requester.id
        persona.name = "Default " + requester.name + "'s Persona"
        persona.type = "RPM"
        persona.configuration = "{}"

        db.add(persona)
        db.add(accessible)
        db.commit()
        db.refresh(persona)

        random_avatars = ['XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX']
        random_avatar = random.choice(random_avatars)

        try:
            file_id = uuid.uuid4().hex
            uploaded_file = s3.UploadedFile(url=random_avatar, mime='modle/gltf+binary', size=0)
            # Assign the file to the entity.
            self.create_or_replace_file(db=db, entity_id=persona.id, type='mesh_avatar', platform=None, version=None, deployment_type=None,
                                        uploaded_file=uploaded_file, requester=requester, id=file_id, original_name=random_avatar)
            crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.add_file)
        except:
            print('failed to assign a random avatar to the default persona')

        requester.default_persona_id = persona.id
        db.commit()

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.add_persona)

        return persona

    # noinspection PyShadowingNames
    def update_persona(self, db: Session, *, requester: models.User, entity: Union[str, models.User], id: str, patch: schemas.PersonaUpdate) -> models.Persona:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not patch:
            raise EntityParameterError('no persona patch')

        if not id:
            raise EntityParameterError('no persona id')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        try:
            json.loads(patch.configuration)
        except json.decoder.JSONDecodeError:
            raise EntityParameterError('invalid configuration JSON')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no comment access to the entity')

        persona: models.Persona = self.prepare_entity(db, entity=id, model=models.Persona, options=joinedload(self.model.accessibles))
        if persona is None:
            raise EntityNotFoundError('no persona with this id')

        persona.name = patch.name
        persona.configuration = patch.configuration
        persona.type = patch.type

        db.add(persona)
        db.commit()
        db.refresh(persona)

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.add_persona)

        return persona

    # noinspection PyShadowingNames
    def set_default_persona(self, db: Session, *, requester: models.User, entity: Union[str, models.User], id: str) -> models.Persona:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not id:
            raise EntityParameterError('no persona id')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no comment access to the entity')

        persona: models.Persona = self.prepare_entity(db, entity=id, model=models.Persona, options=joinedload(self.model.accessibles))
        if persona is None:
            raise EntityNotFoundError('no persona with this id')

        entity.default_persona_id = id

        db.add(entity)
        db.commit()
        db.refresh(entity)

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.edit_persona)

        return entity

    def delete_persona(self, db: Session, *, requester: models.User, entity: Union[str, models.User], id: str):
        if not requester:
            raise EntityParameterError('no requester')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_user(db, user=entity)

        if not entity.owned_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        if not id:
            raise EntityParameterError('no avatar id')

        persona: models.Persona = db.query(models.Persona).filter(models.Persona.id == id).first()

        if not persona:
            raise EntityNotFoundError('no persona found')

        # Delete file trait.
        db.delete(persona)
        db.commit()

    # noinspection PyShadowingNames
    def create_or_update_accessible(self, db: Session, *, requester: models.User, entity: Union[str, models.User], patch: schemas.AccessibleUpdate) -> bool:
        r"""Updates accessible trait for the entity and the requester."""
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if patch.can_edit:
            raise EntityAccessError('access denied')

        if patch.can_delete:
            raise EntityAccessError('access denied')

        entity = self.prepare_entity(db, entity=entity, options=joinedload(self.model.accessibles))

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
            accessible.can_edit = False
            accessible.can_delete = False
        else:
            # Create a new accessible between the entity and the user we share access with
            accessible = models.Accessible()
            accessible.entity_id = entity.id
            accessible.user_id = patch.user_id
            accessible.is_owner = False  # Owner flag set only during entity creation
            accessible.can_view = patch.can_view
            accessible.can_edit = False
            accessible.can_delete = False

        db.add(accessible)
        db.commit()

        self.grant_experience(db, requester=requester, experience=settings.experience.rewards.share)

        return True

    # Report that the user is online.
    # noinspection PyMethodMayBeStatic
    def heartbeat(self, db: Session, *, requester: models.User, space_id: str = '', server_id: str = '', status: str = 'offline') -> bool:
        if not requester:
            raise EntityParameterError('no requester')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        requester.last_seen_at = datetime.datetime.utcnow()

        q: Query = db.query(models.Presence).filter(models.Presence.user_id == requester.id)
        presence = q.first()
        if not presence:
            presence = models.Presence()

        presence.space_id = space_id
        presence.server_id = server_id
        if (str(status).lower() in ['available', 'offline', 'away', 'playing']):
            presence.status = status
        else:
            presence.status = 'offline'

        db.add(requester)
        db.add(presence)
        db.commit()

        return True

    # noinspection PyMethodMayBeStatic,PyShadowingNames,PyComparisonWithNone
    def get_online_game(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity]) -> models.OnlineGame:
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

        # if not entity.is_active:
        #     raise EntityAccessError('user is not active')

        if entity.is_banned:
            raise EntityAccessError('user is banned')

        q: Query = db.query(models.OnlinePlayer).join(models.OnlineGame, models.OnlineGame.id == models.OnlinePlayer.online_game_id)

        online_game = q.filter(models.OnlinePlayer.user_id == entity.id, models.OnlinePlayer.disconnected_at == None).with_entities(models.OnlineGame.id).first()

        # todo: check and fix
        if online_game:
            online_game = self.prepare_entity(db, entity=online_game.id, model=models.OnlineGame, options=[])

        return online_game

    # noinspection PyMethodMayBeStatic,PyShadowingNames,PyComparisonWithNone
    def get_last_seen(self, db: Session, *, requester: models.User, entity: Union[str, models.Entity]) -> models.OnlineGame:
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_user(db, user=entity)

        if not requester.id == entity.id and not entity.viewable_by(requester):
            raise EntityAccessError('requester has no view access to the entity')

        # if not entity.is_active:
        #     raise EntityAccessError('user is not active')

        if entity.is_banned:
            raise EntityAccessError('user is banned')

        return entity

    # noinspection PyShadowingNames
    def report_api_action(self, db: Session, *, requester: models.User, action: schemas.ApiActionCreate):
        if not requester:
            raise EntityParameterError("no requester")

        if not action:
            raise EntityParameterError("no action")

        # if not requester.is_active:
        #     raise EntityAccessError("inactive")

        if requester.is_banned:
            raise EntityAccessError("banned")

        user = self.prepare_user(db, user=action.user_id)

        if not user.viewable_by(requester):
            raise EntityAccessError("requester has no view access to the entity")

        m_action = models.ApiAction(id=uuid.uuid4().hex,
                                    user_id=action.user_id,
                                    version=action.version,
                                    method=action.method,
                                    route=action.route,
                                    params=action.params,
                                    result=action.result)

        db.add(m_action)
        db.commit()

        return True

    # noinspection PyShadowingNames
    def report_api_action_internal(self, db: Session, *, action: schemas.ApiActionCreate):
        if not action:
            raise EntityParameterError("no action")

        m_action = models.ApiAction(id=uuid.uuid4().hex,
                                    user_id="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
                                    version=action.version,
                                    method=action.method,
                                    route=action.route,
                                    params=action.params,
                                    result=action.result)

        db.add(m_action)
        db.commit()

        return True

    # noinspection PyShadowingNames
    def report_launcher_action(self, db: Session, *, requester: models.User, action: schemas.LauncherActionCreate):
        if not requester:
            raise EntityParameterError("no requester")

        if not action:
            raise EntityParameterError("no action")

        requester = self.prepare_user(db, user=requester)

        # if not requester.is_active:
        #     raise EntityAccessError("inactive")

        if requester.is_banned:
            raise EntityAccessError("banned")

        if not requester.is_internal:
            raise EntityAccessError("access denied")

        user_id = action.user_id
        if not user_id:
            user_id = requester.id

        m_action = models.LauncherAction(id=uuid.uuid4().hex,
                                         user_id=user_id,
                                         version=action.version,
                                         name=action.name,
                                         machine_id=action.machine_id,
                                         os=action.os,
                                         address=action.address,
                                         details=action.details)

        db.add(m_action)
        db.commit()

        return m_action

    # noinspection PyShadowingNames
    def report_client_action(self, db: Session, *, requester: models.User, action: schemas.ClientActionCreate):
        if not requester:
            raise EntityParameterError("no requester")

        if not action:
            raise EntityParameterError("no action")

        # if not requester.is_active:
        #     raise EntityAccessError("inactive")

        if requester.is_banned:
            raise EntityAccessError("banned")

        user = self.prepare_user(db, user=action.user_id)

        if not user.viewable_by(requester):
            raise EntityAccessError("requester has no view access to the entity")

        action = models.ClientAction(id=uuid.uuid4().hex, user_id=action.user_id, version=action.version,
                                     category=action.category,
                                     name=action.name,
                                     details=action.details)

        db.add(action)
        db.commit()

        return True

    # noinspection PyShadowingNames
    def report_client_interaction(self, db: Session, *, requester: models.User, action: schemas.ClientInteractionCreate):
        if not requester:
            raise EntityParameterError("no requester")

        if not action:
            raise EntityParameterError("no action")

        # if not requester.is_active:
        #     raise EntityAccessError("inactive")

        if requester.is_banned:
            raise EntityAccessError("banned")

        user = self.prepare_user(db, user=action.user_id)

        if not user.viewable_by(requester):
            raise EntityAccessError("requester has no view access to the entity")

        action = models.ClientInteraction(id=uuid.uuid4().hex, user_id=action.user_id, version=action.version,
                                          category=action.category,
                                          name=action.name,
                                          details=action.details,
                                          interactive_id=action.interactive_id,
                                          interactive_name=action.interactive_name,
                                          interactive_type=action.interaction_type)

        db.add(action)
        db.commit()

        return True

    # endregion

    # region Access field groups

    __private_fields: List[Column] = [models.User.api_key.name,
                                      models.User.email.name,
                                      models.User.device_id.name,
                                      models.User.password_hash.name,
                                      models.User.ip.name]
    r"""Private fields to exclude from any query that could leak private information."""

    # endregion

    ACTIVATION_SECRET_KEY = 'xxx'
    ACTIVATION_SECURITY_PASSWORD_SALT = 'xxx'

    def generate_confirmation_token(self, email):
        serializer = URLSafeTimedSerializer(self.ACTIVATION_SECRET_KEY)
        return serializer.dumps(email, salt=self.ACTIVATION_SECURITY_PASSWORD_SALT)

    def confirm_token(self, token, expiration=86400):
        serializer = URLSafeTimedSerializer(self.ACTIVATION_SECRET_KEY)
        email = serializer.loads(
            token,
            salt=self.ACTIVATION_SECURITY_PASSWORD_SALT,
            max_age=expiration
        )
        return email

    def has_invites(self, db, *, requester: models.User):
        if requester.is_admin:
            return True

        q: Query = db.query(models.Invitation).filter(models.Invitation.inviter_id == requester.id,
                                                      models.Invitation.invited_at == None,
                                                      models.Invitation.joined_at == None,
                                                      models.Invitation.user_id == None)
        count = q.count()
        return count > 0

    def generate_invite_code(self, db, *, attempt=0) -> str:
        if attempt > 5:
            raise EntityParameterError('failed to generate a unique invite code')
        code = shortuuid.uuid()[:5].upper()
        count = db.query(models.Invitation).filter(models.Invitation.code == code).count()
        if count > 1:
            return self.generate_invite_code(db, attempt=attempt + 1)
        return code

    def get_invitations(self, db: Session, requester: models.User) -> schemas.InvitationTotal:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        unused = self.get_unused_invite_count(db, requester=requester)
        used = self.get_used_invite_count(db, requester=requester)

        return schemas.InvitationTotal(total=used + unused, used=used, unused=unused)

    def get_unused_invite_count(self, db: Session, requester: models.User) -> int:
        q: Query = db.query(models.Invitation).filter(models.Invitation.inviter_id == requester.id,
                                                      models.Invitation.invited_at == None)
        return q.count()

    def get_used_invite_count(self, db: Session, requester: models.User) -> int:
        q: Query = db.query(models.Invitation).filter(models.Invitation.inviter_id == requester.id,
                                                      models.Invitation.invited_at != None)
        return q.count()

    def get_unused_invite(self, db, *, requester: models.User):
        q: Query = db.query(models.Invitation).filter(models.Invitation.inviter_id == requester.id,
                                                      models.Invitation.invited_at == None)

        invitation = q.first()

        if not invitation:
            if requester.is_admin:
                # Provide an admin with a new invitation.
                invitation = models.Invitation(
                    id=uuid.uuid4().hex,
                    inviter_id=requester.id,
                    created_at=datetime.datetime.now(),
                    code=self.generate_invite_code(db),
                    invited_at=datetime.datetime.now()
                )
                db.add(invitation)
                db.commit()
        else:
            # Update invitation with a new code and invited at timestamp.
            invitation.code = self.generate_invite_code(db)
            invitation.invited_at = datetime.datetime.now()
            db.add(invitation)
            db.commit()

        return invitation

    def grant_experience(self, db, *, requester: models.User, experience: int = 0) -> bool:
        """
        Increases user's experience and grants rewards such as new invites.

        :returns: True if granted a new level
        """
        if experience <= 0:
            return False

        current_level = requester.level

        if requester.level < settings.experience.max_level:
            requester.experience += experience
            new_level = requester.level

            db.add(requester)
            db.commit()

            # Level up
            if new_level > current_level:
                self.grant_level_up_rewards(db, requester=requester)
                return True

        return False

    # noinspection PyMethodMayBeStatic
    def grant_level_up_rewards(self, db, *, requester: models.User):
        if requester.level > 0:
            # Grant new invites.
            invitation = models.Invitation(
                id=uuid.uuid4().hex,
                inviter_id=requester.id,
                created_at=datetime.datetime.now()
            )
            db.add(invitation)
            db.commit()

    # noinspection PyShadowingNames
    def get_internal_user(self, db) -> models.User:
        user = db.query(models.User).filter(models.User.id == settings.internal_user_id).first()
        if not user:
            return models.User(id=settings.internal_user_id, is_active=True, is_banned=False)
        return user

    # noinspection PyShadowingNames
    def set_user_password(self, db, *, requester: models.User, user: Union[str, models.User], password: str):
        r"""Admin only method to delete batch of entities by id list including all related traits and stored files."""
        if not requester:
            raise EntityParameterError("no requester")

        if not user:
            raise EntityParameterError('no user')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not requester.is_admin:
            raise EntityAccessError('access denied')

        if not requester.is_super_admin():
            raise EntityAccessError('access denied')

        if not self._check_password_str_parameter(password):
            raise EntityParameterError('invalid password')

        user = self.prepare_user(db, user=user, options=joinedload(models.User.accessibles))

        if not user:
            raise EntityNotFoundError('no user')

        user.password_hash = generate_password_hash(password)
        db.add(user)
        db.commit()

    def _check_password_str_parameter(self, password: str):
        if password:
            if not isinstance(password, str):
                return False
            if not bool(re.match('^[a-zA-Z0-9.\\-_!@#$%^&*()/+=<>,~`]+$', password)):
                raise EntityParameterError('string contains invalid characters')
            else:
                return True
        return False

    def check_email(self, email):
        regex = '^(\w|\.|\_|\-\+)+[@](\w|\_|\-|\.)+[.]\w{2,63}$'
        if (re.search(regex, email)):
            return True
        else:
            return False

    def confirm_link(self, requester: models.User, address: str):
        token = self.generate_confirmation_token(requester.email)
        env = os.getenv('ENVIRONMENT')

        if env == 'prod':
            link = f"https://api.veverse.com/users/confirm/wallet/{address}/{token}"
        elif env == 'test':
            link = f"https://test.api.veverse.com/users/confirm/wallet/{address}/{token}"
        else:
            link = f"https://dev.api.veverse.com/users/confirm/wallet/{address}/{token}"

        text_template_str = templates.link_wallet.confirmation_text
        text_template = Template(text_template_str)
        text = text_template.substitute(name=requester.name, address=address, link=link)

        html_template_str = templates.link_wallet.confirmation_html
        html_template = Template(html_template_str)
        html = html_template.substitute(name=requester.name, link=link)

        result = self.email_service.send_to_user(subject="Metaverse Wallet Address Confirmation", text=text, html=html, sender_email="no-reply@w3mvrs.com", receiver=requester)

        if not result:
            logging.warning(f"failed to send activation email to a user: {requester.email}, {requester.id}")


user = CRUDUser(models.User)
