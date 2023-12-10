# noinspection PyUnresolvedReferences
from sqlalchemy.orm import relationship

from ..database import Base
from .models import Entity, User, Accessible, File, Property, Likable, Comment, Follower, Invitation, Tag, EntityTagAssociation, ApiAction, ClientAction, ClientInteraction, LauncherAction, Portal, Persona, Subscription, Presence, Template, Event, Payment
from .object import Object
from .collection import Collection
from .space import Space, Placeable
from .online_game import OnlineGame, OnlinePlayer
from .server import Server, ServerPlayer
from .collectable import Collectable
from .feedback import Feedback
from .mod import ModPlatformAssociation, Platform, ModLink, LinkType, Mod
from .build_job import BuildJob
from .placeable_class import PlaceableClass

Portal.space = relationship("Space", foreign_keys=[Portal.space_id], lazy="select", uselist=False)

Portal.destination = relationship("Portal", foreign_keys=[Portal.destination_id], remote_side=[Portal.id], uselist=False, lazy="select") # , lazy="joined"
# Portal.entrance = relationship("Portal", foreign_keys=[Portal.destination_id], back_populates="destination") # , lazy="joined"

Presence.space = relationship(Space,  viewonly=True,  uselist=False, lazy="select") # foreign_keys=[Presence.space_id], remote_side=[Space.id],
Presence.server = relationship(Server, viewonly=True, uselist=False, lazy="select") # foreign_keys=[Presence.server_id], remote_side=[Server.id],