import datetime
import uuid
from typing import Optional, Dict, Union

from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_
from sqlalchemy.orm import Session, Query
from sqlalchemy.orm.interfaces import MapperOption

from app import models, schemas, crud
from app.config import settings
from app.crud.entity import CRUDBase, EntityBatch, EntityParameterError, EntityAccessError, EntityNotFoundError
from app.schemas.online_game import OnlineGameCreate


class CRUDOnlineGame(CRUDBase[models.OnlineGame, schemas.OnlineGameCreate, schemas.OnlineGameUpdate]):

    def index(self, db, *, requester, query: str = None, build_id: str = None, offset=0, limit=10, filters=None, options=None) -> EntityBatch:
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        # if not build_id:
        #     raise EntityParameterError('no build id')

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
            q = q.join(models.Space, models.OnlineGame.space_id == models.Space.id)
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

        q = q.filter(self.model.build == build_id)

        # Filter entities invisible by the user if user is not an admin.
        if not requester.is_admin:
            # Join accessibles and apply view filters.
            q = q.join(models.Space, models.OnlineGame.space_id == models.Space.id)
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

    def match(self, db: Session, *, requester: models.User, build_id: str, space_id: str, options: Optional[MapperOption] = None):
        if not requester:
            raise EntityParameterError('no requester')

        # if not requester.is_active:
        #     raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        if not build_id:
            raise EntityParameterError('no build id')

        if not space_id:
            raise EntityParameterError('no space id')

        if not self.is_valid_uuid(space_id):
            raise EntityParameterError('invalid id')

        # Polymorphic relation will join entity and user.
        q: Query = db.query(self.model)

        q = q.filter(self.model.build == build_id, self.model.space_id == space_id)

        # Filter entities invisible by the user if user is not an admin.
        if not requester.is_admin:
            # Join accessibles and apply view filters.
            q = q.join(models.Space, models.OnlineGame.space_id == models.Space.id)
            q = q.join(models.Accessible, models.Accessible.entity_id == models.Entity.id, isouter=True)
            q = q.filter(*self.make_can_view_filters(requester.id))

        q = q.filter(or_(self.model.created_at >= datetime.datetime.utcnow() - datetime.timedelta(minutes=2),
                         self.model.updated_at >= datetime.datetime.utcnow() - datetime.timedelta(minutes=2)),
                     self.model.online_players < self.model.max_players)

        # todo: better search for online game by online players, should find game that is not empty and not full to dynamically distribute players among servers
        q = q.order_by(self.model.online_players.desc(), self.model.updated_at.desc())

        if options and isinstance(options, MapperOption):
            q.options(options)

        entity = q.first()

        if not entity:
            raise EntityNotFoundError('no online game found')

        # Form entity batch and return.
        return entity

    # Register an online game server.
    def register(self, db: Session, *, create_data: OnlineGameCreate, requester: models.User):
        if not requester:
            raise EntityParameterError('no requester')

        requester = self.prepare_user(db, user=requester)

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        # Only internal system users are able to update online games.
        if not requester.is_internal:
            raise EntityAccessError('access denied')

        if not create_data:
            raise EntityParameterError('no entity')

        if not create_data.space_id:
            raise EntityParameterError('no space')

        space_exists = db.query(models.Space).filter(models.Space.id == create_data.space_id).count() > 0

        if not space_exists:
            raise EntityNotFoundError('no space')

        source_data = jsonable_encoder(create_data, by_alias=False)
        source_data["user_id"] = requester.id

        entity = models.OnlineGame(**source_data)
        entity.id = uuid.uuid4().hex

        db.add(entity)
        db.commit()
        db.refresh(entity)

        return entity

    # Report that the game is still in progress.
    def heartbeat(self, db: Session, *, entity: Union[str, models.OnlineGame], requester: models.User) -> bool:
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

        entity = self.prepare_base(db, entity=entity, model=models.OnlineGame)

        entity.updated_at = datetime.datetime.utcnow()

        db.add(entity)
        db.commit()

        return True

    # Report that the player joined the online game.
    def connect_online_player(self, db: Session, *, requester: models.User, online_game: Union[str, models.OnlineGame], user: Union[str, models.User]) -> bool:
        if not requester:
            raise EntityParameterError('no requester')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        # Only internal system users are able to update online games.
        if not requester.is_internal:
            raise EntityAccessError('access denied')

        if not online_game:
            raise EntityParameterError('no online game')

        user = self.prepare_user(db, user=user)

        # if not user.is_active:
        #     raise EntityAccessError('user is not active')

        if user.is_banned:
            raise EntityAccessError('user is banned')

        online_game = self.prepare_entity(db, entity=online_game, model=models.OnlineGame)

        online_player = models.OnlinePlayer()
        online_player.id = uuid.uuid4().hex
        online_player.user_id = user.id
        online_player.online_game_id = online_game.id

        db.add(online_player)
        db.commit()

        # User connected to the game
        crud.user.grant_experience(db, requester=user, experience=settings.experience.rewards.join_online_game)

        return True

    # Report that the player left the online game.
    def disconnect_online_player(self, db: Session, *, requester: models.User, online_game: Union[str, models.OnlineGame], user: Union[str, models.User]) -> bool:
        if not requester:
            raise EntityParameterError('no requester')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        # Only internal system users are able to update online games.
        if not requester.is_internal:
            raise EntityAccessError('access denied')

        if not online_game:
            raise EntityParameterError('no online game')

        user = self.prepare_user(db, user=user)

        # if not user.is_active:
        #     raise EntityAccessError('user is not active')

        if user.is_banned:
            raise EntityAccessError('user is banned')

        online_game = self.prepare_entity(db, entity=online_game, model=models.OnlineGame)

        # Search for online player who did not disconnect yet.
        q: Query = db.query(models.OnlinePlayer)
        q = q.filter(models.OnlinePlayer.user_id == user.id, models.OnlinePlayer.online_game_id == online_game.id, models.OnlinePlayer.disconnected_at != None)
        online_player = q.first()

        if not online_player:
            raise EntityNotFoundError('online player not found')

        # Update online player record.
        online_player.disconnected_at = datetime.datetime.now()

        db.add(online_player)
        db.commit()

        return True

    # Get matching games
    def find(self, db: Session, *, space_id: str, offset: int = 0, limit: int = 20) -> Dict:
        q = db.query(models.OnlineGame)

        # Find only servers which updated recently
        updated_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=3)

        filters = [
            models.OnlineGame.updated_at > updated_at,
            models.OnlineGame.public == True,
            models.OnlineGame.space_id == space_id
        ]
        q = q.filter(*filters)
        q = q.offset(offset if offset >= 0 else 0).limit(limit if limit > 0 else 20)

        result = q.all()
        count = CRUDBase.get_total(q, models.OnlineGame.id)
        return {"entities": result, "offset": offset, "limit": limit, "count": count}


online_game = CRUDOnlineGame(models.OnlineGame)
