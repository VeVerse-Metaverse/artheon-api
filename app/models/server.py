from sqlalchemy import Column, func, Boolean, Integer, ForeignKey, select, and_, Text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship, column_property

from app.database import Base


class Server(Base):
    """Base class for all polymorphic entities. Entities can be viewed, liked, shared, tagged, owned by user, etc."""
    __tablename__ = "servers"

    id = Column(UUID, primary_key=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_onupdate=func.now())
    public = Column(Boolean, default=True)
    build = Column(Text, default=None, nullable=True)
    map = Column(Text, default=None, nullable=True)
    host = Column(Text, index=True)
    port = Column(Integer)
    space_id = Column(UUID, ForeignKey("spaces.id", ondelete="CASCADE"))
    max_players = Column(Integer, default=64)
    game_mode = Column(Text, nullable=True)
    user_id = Column(UUID)  # Who has started the server.
    status = Column(Text)  # Status of the server, created,starting,online,offline,error
    details = Column(Text)  # Error details if any
    name = Column(Text)  # Name of the server in the cluster
    image = Column(Text)  # Image used to run the server

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
        if user.is_internal:
            return True
        return False

class ServerPlayer(Base):
    """Base class for all polymorphic entities. Entities can be viewed, liked, shared, tagged, owned by user, etc."""
    __tablename__ = "server_players"
    id = Column(UUID, primary_key=True)
    server_id = Column(UUID, ForeignKey("servers.id", ondelete="CASCADE"))
    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"))
    connected_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    disconnected_at = Column(TIMESTAMP, nullable=True)
    server = relationship(Server, foreign_keys=[server_id], lazy="noload")


Server.online_players = column_property(select([func.count(ServerPlayer.id)]).where(and_(ServerPlayer.server_id == Server.id, ServerPlayer.disconnected_at == None)))
