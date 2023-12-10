from sqlalchemy import Column, func, Boolean, Integer, ForeignKey, select, and_, Text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship, column_property

from app.database import Base


class OnlineGame(Base):
    """Base class for all polymorphic entities. Entities can be viewed, liked, shared, tagged, owned by user, etc."""
    __tablename__ = "online_games"

    id = Column(UUID, primary_key=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_onupdate=func.now())
    # UE4 session identifier.
    session_id = Column(Text, nullable=True)
    # Public IP address or domain name.
    address = Column(Text, index=True)
    # Port.
    port = Column(Integer, default=7777)
    # Space ID used for the game.
    space_id = Column(UUID, ForeignKey("spaces.id", ondelete="CASCADE"))
    build = Column(Text)
    user_id = Column(UUID)
    # Map used for the game.
    map = Column(Text, nullable=True)
    game_mode = Column(Text, nullable=True)
    max_players = Column(Integer, default=8)

    public = Column(Boolean, default=True)


class OnlinePlayer(Base):
    """Base class for all polymorphic entities. Entities can be viewed, liked, shared, tagged, owned by user, etc."""
    __tablename__ = "online_players"

    id = Column(UUID, primary_key=True)

    online_game_id = Column(UUID, ForeignKey("online_games.id", ondelete="CASCADE"))
    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"))

    connected_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    disconnected_at = Column(TIMESTAMP, nullable=True)

    online_game = relationship(OnlineGame, foreign_keys=[online_game_id], lazy="noload")


OnlineGame.online_players = column_property(select([func.count(OnlinePlayer.id)]).where(and_(OnlinePlayer.online_game_id == OnlineGame.id, OnlinePlayer.disconnected_at == None)))
