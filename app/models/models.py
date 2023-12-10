import math
import os
from random import randint

from sqlalchemy import Column, func, Boolean, Integer, ForeignKey, Text, and_, SmallInteger, Unicode, Float
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID, JSON
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, join, aliased, deferred
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app.config import settings
from app.database import Base

metadata = Base.metadata


class EntityTagAssociation(Base):
    __tablename__ = 'entity_tags'
    entity_id = Column(UUID, ForeignKey('entities.id'), primary_key=True)
    tag_id = Column(UUID, ForeignKey('tags.id'), primary_key=True)
    tag = relationship("Tag", back_populates="entities")
    entity = relationship("Entity", back_populates="tags")


class Entity(Base):
    r"""Base class for all polymorphic entities. Entities have traits which specify common behaviour."""
    __tablename__ = "entities"

    id = Column(UUID, primary_key=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_onupdate=func.now())
    entity_type = Column(Text, index=True)
    public = Column(Boolean, default=False)
    views = Column(Integer, default=0)

    # Relations
    accessibles: InstrumentedAttribute = relationship("Accessible", lazy="joined", cascade="all, delete", passive_deletes=True)
    files: InstrumentedAttribute = relationship("File", lazy="joined", cascade="all, delete", passive_deletes=True)
    properties: InstrumentedAttribute = relationship("Property", lazy="noload", cascade="all, delete", passive_deletes=True)
    likables: InstrumentedAttribute = relationship("Likable", lazy="noload", passive_deletes=True)
    comments: InstrumentedAttribute  # = relationship("Comment", back_populates="entity", foreign_keys="[Comment.entity_id]", lazy='noload')
    tags: InstrumentedAttribute = relationship("EntityTagAssociation", back_populates="entity")

    total_likes: int = randint(0, 100)
    total_dislikes: int = randint(0, 100)

    # Declare owner relationship. Defined outside of the class.
    owner: InstrumentedAttribute

    # region Access helpers

    # Check if the user is the owner of the entity.
    def is_owner(self, user):
        if self.id == user.id:
            return True
        for ref in self.accessibles:
            if ref.user_id == user.id:
                return True
        return False

    # Check if the user is the owner of the entity.
    def owned_by(self, user):
        if user.is_super_admin():  # Super admin can delete everything, including users if it is required.
            return True
        if user.is_admin:
            return True
        if self.id == user.id:
            return True
        for ref in self.accessibles:
            if ref.user_id == user.id and ref.is_owner:
                return True
        return False

    # Check if the user can view the entity.
    def viewable_by(self, user):
        if user.is_super_admin():  # Super admin can delete everything, including users if it is required.
            return True
        # if not user.is_active:
        #     return False
        if user.is_banned:
            return False
        if self.public:
            return True
        if user.is_admin:
            return True
        if self.id == user.id:
            return True
        for ref in self.accessibles:
            if ref.user_id == user.id and (ref.can_view or ref.is_owner):
                return True
        return False

    # Check if the user can edit the entity.
    def editable_by(self, user):
        if user.is_super_admin():  # Super admin can delete everything, including users if it is required.
            return True
        # if not user.is_active:
        #     return False
        if user.is_banned:
            return False
        if user.is_admin:
            return True
        if self.id == user.id:
            return True
        for ref in self.accessibles:
            if ref.user_id == user.id and (ref.can_edit or ref.is_owner):
                return True
        return False

    # Check if the user can delete the entity.
    def deletable_by(self, user):
        if user.is_super_admin():  # Super admin can delete everything, including users if it is required.
            return True
        if self.id == user.id:  # Users can't delete themselves.
            return False
        if self.entity_type == 'user':  # Users can't delete other users.
            return False
        if not user.is_active:
            return False
        if user.is_banned:
            return False
        if user.is_admin:
            return True
        for ref in self.accessibles:
            if ref.user_id == user.id and (ref.can_delete or ref.is_owner):
                return True
        return False

    # Check if the user can comment the entity.
    def commentable_by(self, user):
        if user.is_super_admin():  # Super admin can delete everything, including users if it is required.
            return True
        # if not user.is_active:
        #     return False
        if user.is_banned:
            return False
        if user.is_admin:
            return True
        if self.public:
            return True
        if self.id == user.id:
            return True
        for ref in self.accessibles:
            if ref.user_id == user.id and (ref.can_view or ref.is_owner):
                return True
        return False

    # Check if the user can like the entity.
    def likable_by(self, user):
        if user.is_super_admin():  # Super admin can delete everything, including users if it is required.
            return True
        # if not user.is_active:
        #     return False
        if user.is_banned:
            return False
        if user.is_admin:
            return True
        if self.public:
            return True
        if self.id == user.id:
            return True
        for ref in self.accessibles:
            if ref.user_id == user.id and (ref.can_view or ref.is_owner):
                return True
        return False

    # endregion

    __mapper_args__ = dict(polymorphic_identity='entity', polymorphic_on=entity_type, polymorphic_load='inline')


class Tag(Base):
    __tablename__ = "tags"
    id = Column(UUID, primary_key=True)
    name = Column(Unicode(32), index=True, unique=True)
    entities: InstrumentedAttribute = relationship("EntityTagAssociation", back_populates="tag")


ranks = {
    0: 'newcomer',
    10: 'beginner',
    20: 'amateur',
    30: 'apprentice',
    40: 'accustomed',
    50: 'skillful',
    60: 'expert',
    70: 'prodigy',
    80: 'professional',
    90: 'legendary',
    100: 'epic'
}


class Presence(Base):
    __tablename__ = "presence"
    # Timestamp when action was reported.
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    # Id of the user who reported the event.
    user_id = Column(UUID, ForeignKey("users.id", ondelete="SET DEFAULT"), default="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX", primary_key=True)
    # Type of the action: api_action, game_action.
    status = Column(Text, index=True, nullable=True)
    # Current space id
    space_id = Column(UUID, ForeignKey('spaces.id'))
    # Current server id
    server_id = Column(UUID, ForeignKey('servers.id'))


class User(Entity):
    __tablename__ = "users"

    id = Column(UUID, ForeignKey("entities.id", ondelete='CASCADE'), primary_key=True)

    email = deferred(Column(Text, unique=True, nullable=True))
    device_id = deferred(Column(Text, unique=False, nullable=True))
    password_hash = deferred(Column(Text, nullable=True))
    api_key = deferred(Column(Text, unique=True, nullable=False))
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    ip = deferred(Column(Text, nullable=True))
    geolocation = deferred(Column(Text, nullable=True))
    is_active = Column(Boolean, index=True, default=False, nullable=True)
    is_admin = Column(Boolean, index=True, nullable=True, default=False)
    is_muted = Column(Boolean, index=True, nullable=True, default=False)
    is_banned = Column(Boolean, index=True, nullable=True, default=False)
    is_internal = Column(Boolean, index=True, nullable=True, default=False)
    is_address_confirmed = Column(Boolean, index=True, nullable=True, default=False)
    last_seen_at = Column(TIMESTAMP, default=None)
    activated_at = Column(TIMESTAMP, default=None)
    allow_emails = Column(Boolean, default=False)
    experience = Column(Integer, default=0)
    eth_address = Column(Text, nullable=True)
    address = Column(Text, nullable=True)
    default_persona_id = Column(Text, ForeignKey("personas.id"), nullable=True)

    # Check if the user is the owner of the entity.
    def is_super_admin(self):
        if self.is_admin and not self.is_banned and self.is_active and (
                self.id == 'f0000000-0000-4000-a000-00000000000e'):
            return True
        return False

    @hybrid_property
    def level(self) -> int:
        return math.floor(math.pow(self.experience / float(settings.experience.params.base), 1.0 / float(settings.experience.params.exponent)))

    @level.expression
    def level(self):
        return func.floor(func.pow(self.experience / float(settings.experience.params.base), 1.0 / float(settings.experience.params.exponent)))

    @hybrid_property
    def rank(self) -> int:
        try:
            level = self.level
            rank = ranks[round(level / 10) * 10]
            return rank
        except:
            return ranks[0]

    # Relations
    # user_accessible: InstrumentedAttribute = relationship("Accessible", back_populates="user", lazy='noload', viewonly=True)
    # user_likable: InstrumentedAttribute = relationship("Likable", back_populates="user", lazy='noload', viewonly=True)
    # user_comments: InstrumentedAttribute
    followers: InstrumentedAttribute = relationship("Follower", foreign_keys="[Follower.follower_id]", lazy='noload', viewonly=True)
    leaders: InstrumentedAttribute = relationship("Follower", foreign_keys="[Follower.leader_id]", lazy='noload', viewonly=True)
    presence: InstrumentedAttribute = relationship("Presence", foreign_keys="[Presence.user_id]", viewonly=True, uselist=False)
    # avatar: InstrumentedAttribute = relationship("File", uselist=False, order_by="desc(File.created_at)", primaryjoin="and_(Entity.id==File.entity_id,File.type=='image_avatar')", lazy='select',
    #                                              viewonly=True)

    __mapper_args__ = dict(polymorphic_identity="user", inherit_condition=id == Entity.id)


class Persona(Entity):
    __tablename__ = "personas"

    id = Column(UUID, ForeignKey("entities.id", ondelete='CASCADE'), primary_key=True)
    name = Column(Text)
    type = Column(Text)
    configuration = Column(JSON, nullable=True)
    user_id = Column(UUID, ForeignKey('users.id'), primary_key=True)
    user = relationship("User", foreign_keys=user_id, viewonly=True, uselist=False, lazy="noload")

    __mapper_args__ = dict(polymorphic_identity="persona", inherit_condition=id == Entity.id)


class Action(Base):
    __tablename__ = "actions"
    id = Column(UUID, primary_key=True)
    # Timestamp when action was reported.
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    # Id of the user who reported the event.
    user_id = Column(UUID, ForeignKey("users.id", ondelete="SET DEFAULT"), default="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX")
    # Type of the action: api_action, game_action.
    action_type = Column(Text, index=True, nullable=False)
    # Game client or api version.
    version = Column(Text, index=True)

    __mapper_args__ = dict(polymorphic_identity='action', polymorphic_on=action_type, polymorphic_load='inline')


class ApiAction(Action):
    __tablename__ = "api_actions"
    id = Column(UUID, ForeignKey("actions.id", ondelete='CASCADE'), primary_key=True)
    # Route that used to perform the action.
    method = Column(Text, index=True, nullable=False)
    # Route that used to perform the action.
    route = Column(Text, index=True, nullable=False)
    # Optional parameters of the request.
    params = Column(JSON, nullable=True)
    # Optional result of the request.
    result = Column(JSON, nullable=True)

    __mapper_args__ = dict(polymorphic_identity="api_action", inherit_condition=id == Action.id)


class ClientAction(Action):
    __tablename__ = "client_actions"
    id = Column(UUID, ForeignKey("actions.id", ondelete='CASCADE'), primary_key=True)

    # Category of the client action: RPC, Chat, Interaction, UI, Online
    category = Column(Text)
    # Name of the client action: Connect, Disconnect, Login, Logout, Join, Leave, Message
    name = Column(Text)
    # Details of the client action
    details = Column(JSON)

    __mapper_args__ = dict(polymorphic_identity="client_action", inherit_condition=id == Action.id)


class LauncherAction(Action):
    __tablename__ = "launcher_actions"
    id = Column(UUID, ForeignKey("actions.id", ondelete='CASCADE'), primary_key=True)

    name = Column(Text)
    address = Column(Text)
    machine_id = Column(Text, index=True)
    os = Column(Text)
    details = Column(JSON)

    __mapper_args__ = dict(polymorphic_identity="launcher_action", inherit_condition=id == Action.id)


class ClientInteraction(Action):
    __tablename__ = "client_interactions"
    id = Column(UUID, ForeignKey("actions.id", ondelete='CASCADE'), primary_key=True)

    # Category of the client action: RPC, Chat, Interaction, UI, Online
    category = Column(Text)
    # Name of the client action: Connect, Disconnect, Login, Logout, Join, Leave, Message
    name = Column(Text)
    # Details of the client action
    details = Column(JSON)
    # Id of the entity user interacted with, if any
    interactive_id = Column(UUID, nullable=True)
    # Name of the entity user interacted with, if any
    interactive_name = Column(Text, nullable=True)
    # Type of the interaction, if any
    interaction_type = Column(Text, nullable=True)

    __mapper_args__ = dict(polymorphic_identity="client_interaction", inherit_condition=id == Action.id)


class Invitation(Base):
    __tablename__ = "invitations"

    id = Column(UUID, primary_key=True)
    # Inviter id.
    inviter_id = Column(UUID, ForeignKey("users.id", ondelete="SET DEFAULT"), default="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX")
    # Invitation code
    code = Column(Text, nullable=True)
    # Email of the invited user.
    email = Column(Text, unique=True, nullable=True)
    # Target user joined using this code.
    user_id = Column(UUID, ForeignKey("users.id", ondelete="SET DEFAULT"), default="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX", nullable=True)
    # Time when invitation code was created.
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    # Time when user invited.
    invited_at = Column(TIMESTAMP, nullable=True)
    # Time when user joined.
    joined_at = Column(TIMESTAMP, nullable=True)

    def is_used(self) -> bool:
        return self.code or self.email or self.invited_at or self.joined_at or self.user_id

    inviter = relationship("User", foreign_keys=inviter_id, viewonly=True, uselist=False, lazy="noload")
    invited = relationship("User", foreign_keys=user_id, viewonly=True, uselist=False, lazy="noload")


class Follower(Base):
    __tablename__ = "followers"

    id = Column(UUID, primary_key=True)

    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_onupdate=func.now())

    follower_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    leader_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    # follower = relationship("User", back_populates="followers", foreign_keys=[follower_id], viewonly=True)
    # leader = relationship("User", back_populates="leaders", foreign_keys=[leader_id], viewonly=True)


# region Traits

class Accessible(Base):
    __tablename__ = "accessibles"

    user_id = Column(UUID, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    entity_id = Column(UUID, ForeignKey('entities.id', ondelete='CASCADE'), primary_key=True)

    is_owner = Column(Boolean, nullable=True)
    can_view = Column(Boolean, nullable=True)
    can_edit = Column(Boolean, nullable=True)
    can_delete = Column(Boolean, nullable=True)

    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_onupdate=func.now())

    # Relations
    # entity = relationship(Entity, back_populates="accessibles", foreign_keys=[entity_id], cascade="all", viewonly=True)
    # user = relationship(User, back_populates="accessibles", foreign_keys=[user_id], cascade="all", viewonly=True)


class Portal(Entity):
    __tablename__ = "portals"

    id = Column(UUID, ForeignKey('entities.id', ondelete='CASCADE'), primary_key=True)

    name = Column(Text, nullable=True)
    space_id = Column(UUID, ForeignKey('spaces.id'))
    space: InstrumentedAttribute
    destination_id = Column(UUID, ForeignKey('portals.id'), default="00000000-0000-0000-0000-000000000000")
    destination: InstrumentedAttribute

    __mapper_args__ = dict(polymorphic_identity="portal", inherit_condition=id == Entity.id)


class File(Base):
    __tablename__ = "files"

    id = Column(UUID, primary_key=True)
    entity_id = Column(UUID, ForeignKey('entities.id', ondelete='CASCADE'), primary_key=True)

    # Type of the file.
    type = Column(Text, nullable=False, default="binary", primary_key=True)
    # URL of the file stored at cloud storage.
    url = Column(Text, nullable=False)
    # Mime type of the file
    mime = Column(Text, nullable=True, default="application/octet-stream")
    # Size of the file
    size = Column(Integer, nullable=True, default=0)
    # File version
    version = Column(Integer, nullable=False, default=0)
    variation = Column(Integer, nullable=False, default=0)
    # File deployment type (server/client)
    deployment_type = Column(Text, nullable=False, default="")
    # File platform
    platform = Column(Text, nullable=False, default="")

    uploaded_by = Column(UUID, ForeignKey('users.id', ondelete="SET DEFAULT"), default="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX")

    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_onupdate=func.now())

    # Relations
    # entity = relationship('Entity', back_populates="files", foreign_keys=[entity_id], viewonly=True)

    def get_file_key(self):
        file_ext = os.path.splitext(self.url)[1]
        sub = '.' + file_ext if file_ext else ''
        return f"{self.entity_id}/{self.id}{sub}"


class Property(Base):
    __tablename__ = "properties"

    entity_id = Column(UUID, ForeignKey('entities.id', ondelete='CASCADE'), primary_key=True)

    # Type of the field.
    type = Column(Text, nullable=False, default="text")
    name = Column(Text, nullable=False, default="", primary_key=True)
    value = Column(Text, nullable=True, default="")

    # Relations
    # entity = relationship('Entity', back_populates="properties", foreign_keys=[entity_id], viewonly=True)


class Likable(Base):
    __tablename__ = "likables"

    id = Column(UUID, primary_key=True)

    user_id = Column(UUID, ForeignKey('users.id', ondelete="SET DEFAULT"), default="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX", primary_key=True)
    entity_id = Column(UUID, ForeignKey('entities.id', ondelete='CASCADE'), primary_key=True)

    value = Column(SmallInteger, nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_onupdate=func.now())

    # Relations
    # entity = relationship('Entity', back_populates="likables", foreign_keys=[entity_id], cascade="all", viewonly=True)
    user = relationship('User', foreign_keys=[user_id], viewonly=True)


class Comment(Entity):
    __tablename__ = "comments"

    # Inherited polymorphic entity relation
    id = Column(UUID, ForeignKey('entities.id', ondelete='CASCADE'), primary_key=True)

    user_id = Column(UUID, ForeignKey('users.id', ondelete="SET DEFAULT"), default="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX", nullable=True)
    entity_id = Column(UUID, ForeignKey('entities.id'), nullable=True)

    user = relationship('User', foreign_keys=[user_id], lazy="select", viewonly=True)
    # entity = relationship('Entity', back_populates="comments", foreign_keys=[entity_id], lazy="noload", viewonly=True)

    text = Column(Text, nullable=False)

    __mapper_args__ = dict(polymorphic_identity='comment', inherit_condition=id == Entity.id)

    # endregion


class Purchasable(Base):
    __tablename__ = "purchasables"

    id = Column(UUID, primary_key=True)

    # User who owns the purchased entity
    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Entity id
    entity_id = Column(UUID, ForeignKey("entities.id", ondelete="CASCADE"), index=True)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(UUID, primary_key=True)
    email = Column(Text, primary_key=True)
    platform = Column(Text)
    notes = Column(Text)
    name = Column(Text)
    type = Column(Text)


class Template(Entity):
    __tablename__ = "templates"
    id = Column(UUID, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    name = Column(Text, nullable=True)
    title = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    map = Column(Text)
    version = Column(Text)
    community = Column(Boolean)
    __mapper_args__ = dict(polymorphic_identity='template', inherit_condition=id == Entity.id)


class Payment(Base):
    __tablename__ = "payments"
    id = Column(UUID, primary_key=True)
    user_id = Column(UUID, ForeignKey('users.id', ondelete="SET DEFAULT"), default="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX")
    entity_id = Column(UUID, ForeignKey('entities.id', ondelete='SET DEFAULT'), default="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX")
    charge_id = Column(Text)
    balance_transaction_id = Column(Text)
    amount = Column(Integer)
    email = Column(Text)
    currency = Column(Text)
    payment_intent_id = Column(Text)
    payment_method_id = Column(Text)
    receipt_url = Column(Text)
    status = Column(Text)


class Event(Entity):
    __tablename__ = "events"
    id = Column(UUID, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    name = Column(Text, nullable=False)
    title = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    starts_at = Column(TIMESTAMP, nullable=True)
    ends_at = Column(TIMESTAMP, nullable=True)
    type = Column(Text, nullable=True)  # event type id
    price = Column(Float, nullable=True)  # event price paid by scheduler, depends on the type
    active = Column(Boolean, nullable=True)  # event paid flag, if true, must have a transaction id
    payment_id = Column(UUID, ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)
    space_id = Column(UUID, ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True)
    # space = relationship("Space", foreign_keys=[space_id], lazy='select', viewonly=True)
    __mapper_args__ = dict(polymorphic_identity='event', inherit_condition=id == Entity.id)


# region Entity Relationship Definitions

# Entity comments
Entity.comments = relationship(Comment, foreign_keys="[Comment.entity_id]", lazy='noload', viewonly=True)

entity_alias = aliased(Entity)

# Define join of the user to the entity via accessible.
entity_owner_join = join(Accessible, entity_alias, and_(Accessible.entity_id == entity_alias.id, Accessible.is_owner == True)).join(User, Accessible.user_id == User.id)

# Alias join for the user table.
owner_via_accessible = aliased(User, entity_owner_join, flat=True)

# Define the relationship over the entity.
Entity.owner = relationship(owner_via_accessible, primaryjoin=Entity.id == entity_owner_join.c.accessibles_entity_id, lazy="select", uselist=False, viewonly=True)

User.invitations = relationship("Invitation", foreign_keys=[Invitation.inviter_id], lazy='noload', viewonly=True)
User.personas = relationship("Persona", foreign_keys=[Persona.user_id], lazy='noload', viewonly=True)
User.default_persona = relationship("Persona", foreign_keys=[User.default_persona_id], lazy='select', viewonly=True)
# Space.mod = relationship("Mod", foreign_keys="[Space.mod_id]", back_populates="space", lazy='select')
#
# Mod.space = relationship("Space", foreign_keys="[Space.mod_id]", back_populates="mod", uselist=False)
#
# Space.placeables = relationship("Placeable", foreign_keys="[Placeable.space_id]", lazy='noload', passive_deletes=True)

# endregion
