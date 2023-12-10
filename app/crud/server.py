import datetime
import uuid
from typing import Optional, Dict, Union, List, Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session, Query
from sqlalchemy.orm.interfaces import MapperOption

from app import models, schemas, crud
from app.config import settings
from app.crud.entity import CRUDBase, EntityBatch, EntityParameterError, EntityAccessError, EntityNotFoundError
from app.services import k8s


class CRUDServer(CRUDBase[models.Server, schemas.ServerCreate, schemas.ServerUpdate]):

    def index(self, db, *, requester, query: str = None, build_id: str = None, offset=0, limit=10, filters=None, options=None) -> EntityBatch:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        # Check that offset is valid.
        if not offset >= 0:
            offset = 0

        # Check that limit is valid.
        if not limit > 0:
            limit = 10

        # Query entity model with accessible traits.
        q: Query = db.query(self.model)

        if build_id:
            q = q.filter(self.model.build == build_id)

        # Filter entities invisible by the user if user is not an admin.
        if not requester.is_admin:
            # Join accessibles and apply view filters.
            q = q.join(models.Space, models.Server.space_id == models.Space.id)
            q = q.join(models.Accessible, models.Accessible.entity_id == models.Entity.id, isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id))

        q = q.filter(or_(self.model.created_at >= datetime.datetime.utcnow() - datetime.timedelta(minutes=2),
                         self.model.updated_at >= datetime.datetime.utcnow() - datetime.timedelta(minutes=2)))

        if query:
            q = q.filter(models.Space.name.ilike(f'%{query}%'))

        # Calculate total.
        total = self.get_total(q, self.model.id)

        q = q.order_by(self.model.updated_at)

        if options is not None:
            q = q.options(options)

        # Execute query and get all entities within offset and limit.
        entities = q.offset(offset).limit(limit).all()

        # Return entity batch.
        return EntityBatch(entities, offset, limit, total)

    def index_by_foreign_key_value(self, db, *, requester, build_id: str = None, key=None, value=None, offset=0, limit=10, options=None) -> EntityBatch[models.Entity]:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not build_id:
            raise EntityParameterError('no build id')

        if not key:
            raise EntityParameterError('no key')

        if not value:
            raise EntityParameterError('no value')

        if not self.is_valid_uuid(value):
            raise EntityParameterError('invalid id')

        offset, limit = self.prepare_offset_limit(offset, limit)

        # Polymorphic relation will join entity and user.
        q: Query = db.query(self.model)

        #        q = q.filter(self.model.build == build_id)

        # Filter entities invisible by the user if user is not an admin.
        if not requester.is_admin:
            # Join accessibles and apply view filters.
            q = q.join(models.Space, models.Server.space_id == models.Space.id)
            q = q.join(models.Accessible, models.Accessible.entity_id == models.Entity.id, isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id))

        q = q.filter(getattr(self.model, key) == value)

        created_at = (datetime.datetime.utcnow() - datetime.timedelta(minutes=2))
        updated_at = (datetime.datetime.utcnow() - datetime.timedelta(minutes=2))

        q = q.filter(or_(self.model.created_at >= created_at,
                         self.model.updated_at >= updated_at))

        # Get total count of entities falling under the query.
        total = self.get_total(q, self.model.id)

        q = q.order_by(self.model.updated_at)

        if options and isinstance(options, MapperOption):
            q.options(options)

        entities = q.offset(offset).limit(limit).all()

        # Form entity batch and return.
        return EntityBatch[self.model](entities, offset, limit, total)

    def match(self, db: Session, *, requester: models.User, space_id: str, hostname: str = "", build: str = "", options: Optional[MapperOption] = None):
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not space_id:
            raise EntityParameterError('no space id')

        if not self.is_valid_uuid(space_id):
            raise EntityParameterError('invalid id')

        # Polymorphic relation will join entity and user.
        q: Query = db.query(self.model)

        q = q.filter(self.model.space_id == space_id)

        if hostname:
            q = q.filter(self.model.host == hostname)
        else:
            q = q.filter(or_(self.model.host.ilike("%.veverse.com")))

        if build:
            q = q.filter(self.model.build == build)

        # Filter entities invisible by the user if user is not an admin.
        if not requester.is_admin:
            # Join accessibles and apply view filters.
            q = q.join(models.Space, models.Server.space_id == models.Space.id)
            q = q.join(models.Accessible, models.Accessible.entity_id == models.Entity.id, isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id))

        timeout = (datetime.datetime.utcnow() - datetime.timedelta(minutes=2))

        q = q.filter(or_(self.model.status == 'online', self.model.status == 'starting', self.model.status == 'created'),
                     self.model.updated_at >= timeout,  # if failed to start a server in two minutes, try to start a new one
                     self.model.online_players < self.model.max_players)

        # todo: better search for online game by online players, should find game that is not empty and not full to dynamically distribute players among servers
        q = q.order_by(self.model.online_players.desc(), self.model.updated_at.desc())

        if options and isinstance(options, MapperOption):
            q.options(options)

        entity = q.first()

        if not entity:
            # run a new server
            k8s_service = k8s.k8sServiceInstance
            response = k8s_service.create_server(db=db, requester=requester, space_id=space_id)
            if response["model"]:
                entity = response["model"]

        # Form entity batch and return.
        return entity

    def get_scheduled(self, db: Session, *, platform: str, requester: models.User, options: Optional[MapperOption] = None) -> models.Space:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        # Query spaces
        q1: Query = db.query(models.Space)
        q1 = q1.filter(and_(models.Space.scheduled == True, models.Space.mod_id != None))

        # Filter entities invisible by the user if user is not an admin.
        if not requester.is_admin:
            # Join accessibles and apply view filters.
            q1 = q1.join(models.Accessible, models.Accessible.entity_id == models.Entity.id, isouter=True)
            q1 = q1.filter(*self.make_can_view_filters(requester.id))

        if options and isinstance(options, MapperOption):
            q1.options(options)

        scheduled_spaces = q1.all()

        # Query servers
        q2: Query = db.query(models.Server)

        # Get only active servers having less than max players
        q2 = q2.filter(or_(self.model.created_at >= datetime.datetime.utcnow() - datetime.timedelta(minutes=2),
                           self.model.updated_at >= datetime.datetime.utcnow() - datetime.timedelta(minutes=2)),
                       self.model.online_players < self.model.max_players)
        servers = q2.all()

        # Find space that is not hosted yet and return it
        not_yet_hosted_space: Optional[models.Space] = None
        for scheduled_space in scheduled_spaces:
            # Look for ready to use pak files among mod files
            has_processed_pak = False

            if hasattr(scheduled_space, 'mod'):
                if hasattr(scheduled_space.mod, 'files'):
                    if isinstance(scheduled_space.mod.files, list):
                        file: models.File
                        for file in scheduled_space.mod.files:
                            if file.type == 'pak' and file.deployment_type == 'Server' and file.platform.lower() == platform.lower():
                                has_processed_pak = True
                                break

            if has_processed_pak:
                not_yet_hosted_space = scheduled_space
                for server in servers:
                    if server.space_id == scheduled_space.id:
                        not_yet_hosted_space = None
                        continue
                if not_yet_hosted_space:
                    return not_yet_hosted_space

        if not not_yet_hosted_space:
            raise EntityNotFoundError('no scheduled space found')

    # Register an online game server.
    def register(self, db: Session, *, create_data: schemas.ServerCreate, requester: models.User):
        if not requester:
            raise EntityParameterError('no requester')

        requester = self.prepare_user(db, user=requester)

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not create_data:
            raise EntityParameterError('no entity')

        if not create_data.space_id:
            raise EntityParameterError('no space')

        space_exists = db.query(models.Space).filter(models.Space.id == create_data.space_id).count() > 0

        if not space_exists:
            raise EntityNotFoundError('no space')

        source_data = jsonable_encoder(create_data, by_alias=False)
        source_data["user_id"] = requester.id

        entity = models.Server(**source_data)
        if not entity.id:
            entity.id = uuid.uuid4().hex
        entity.updated_at = datetime.datetime.utcnow()

        db.add(entity)
        db.commit()
        db.refresh(entity)

        return entity

    # Report that the game is still in progress.
    def heartbeat(self, db: Session, *, entity: Union[str, models.Server], requester: models.User, status: str = None, details: str = None) -> bool:
        if not requester:
            raise EntityParameterError('no requester')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        # Only internal system users are able to update online games.
        if not requester.is_internal:
            raise EntityAccessError('access denied')

        if not entity:
            raise EntityParameterError('no entity')

        if status not in ["online", "error"]:
            raise EntityParameterError("invalid status, permitted values: online, error")

        entity: models.Server = self.prepare_base(db, entity=entity, model=models.Server)

        if entity.status == 'starting' or entity.status == 'online':
            entity.updated_at = datetime.datetime.utcnow()
            entity.status = status
            entity.details = details

            db.add(entity)
            db.commit()
            return True

        return False

    # noinspection PyShadowingNames
    def update(self, db: Session, *, requester: models.User, entity: Union[str, models.Server], patch: Union[schemas.ServerUpdate, Dict[str, Any]]):
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity = self.prepare_entity(db, entity=entity, model=self.model, join_accessibles=False)

        # Ensure that the entity is editable by the requester.
        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        # Create a JSON-compatible dict.
        json = jsonable_encoder(patch, by_alias=False)
        if not isinstance(patch, dict):
            patch = patch.dict(exclude_unset=True)

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
    def delete(self, db: Session, *, requester: models.User, entity: Union[str, models.Server]):
        if not requester:
            raise EntityParameterError('no requester')

        if not entity:
            raise EntityParameterError('no entity')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        entity: models.Server = self.prepare_entity(db, entity=entity, model=self.model, join_accessibles=False)

        # Ensure that the entity is editable by the requester.
        if not entity.editable_by(requester):
            raise EntityAccessError('requester has no edit access to the entity')

        entity.status = 'stopping'

        db.add(entity)
        db.commit()
        db.refresh(entity)

        try:
            k8s_service = k8s.k8sServiceInstance
            k8s_service.delete_server(server_id=entity.id)
        except BaseException as ex:
            print(ex)
            return False

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.delete)

        return True

    # Report that the player joined the online game.
    def connect_online_player(self, db: Session, *, requester: models.User, server: Union[str, models.Server], user: Union[str, models.User]) -> bool:
        if not requester:
            raise EntityParameterError('no requester')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        # Only internal system users are able to update online games.
        if not requester.is_internal:
            raise EntityAccessError('access denied')

        if not server:
            raise EntityParameterError('no online game')

        user = self.prepare_user(db, user=user)

        # if not user.is_active:
        #     raise EntityAccessError('user is not active')

        if user.is_banned:
            raise EntityAccessError('user is banned')

        server = self.prepare_entity(db, entity=server, model=models.Server)

        server_player = models.ServerPlayer()
        server_player.id = uuid.uuid4().hex
        server_player.user_id = user.id
        server_player.server_id = server.id

        db.add(server_player)
        db.commit()

        # User connected to the game
        crud.user.grant_experience(db, requester=user, experience=settings.experience.rewards.join_server)

        return True

    # Report that the player left the online game.
    def disconnect_online_player(self, db: Session, *, requester: models.User, server: Union[str, models.Server], user: Union[str, models.User]) -> bool:
        if not requester:
            raise EntityParameterError('no requester')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        # Only internal system users are able to update online games.
        if not requester.is_internal:
            raise EntityAccessError('access denied')

        if not server:
            raise EntityParameterError('no online game')

        user = self.prepare_user(db, user=user)

        # if not user.is_active:
        #     raise EntityAccessError('user is not active')

        if user.is_banned:
            raise EntityAccessError('user is banned')

        server = self.prepare_entity(db, entity=server, model=models.Server)

        # Search for online player who did not disconnect yet.
        q: Query = db.query(models.OnlinePlayer)
        q = q.filter(models.OnlinePlayer.user_id == user.id, models.OnlinePlayer.server_id == server.id, models.OnlinePlayer.disconnected_at != None)
        online_player = q.first()

        if not online_player:
            raise EntityNotFoundError('online player not found')

        # Update online player record.
        online_player.disconnected_at = datetime.datetime.now()

        db.add(online_player)
        db.commit()

        return True

    # noinspection PyShadowingNames
    def get(self, db: Session, *, requester: models.User, id: str, options: Optional[MapperOption] = None) -> Optional[models.Server]:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        q = db.query(models.Server)
        q = q.filter(models.Server.id == id)
        if options:
            if isinstance(options, MapperOption):
                q = q.options(options)
            elif isinstance(options, List):
                q = q.options(*options)
        e = q.first()

        return e

    # Get matching games
    def find(self, db: Session, *, space_id: str, offset: int = 0, limit: int = 20) -> Dict:
        q = db.query(models.Server)

        # Find only servers which updated recently
        updated_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=3)

        filters = [
            models.Server.updated_at > updated_at,
            models.Server.public == True,
            models.Server.space_id == space_id
        ]
        q = q.filter(*filters)
        q = q.offset(offset if offset >= 0 else 0).limit(limit if limit > 0 else 20)

        result = q.all()
        count = CRUDBase.get_total(q, models.Server.id)
        return {"entities": result, "offset": offset, "limit": limit, "count": count}


server = CRUDServer(models.Server)
