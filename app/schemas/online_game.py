import datetime
from typing import Optional, List

from app.schemas.config import CamelCaseModel


class OnlineGameBase(CamelCaseModel):
    id: Optional[str] = None


# Api properties
class OnlineGame(OnlineGameBase):
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    # session_id: Optional[str] = None
    max_players: Optional[int] = None
    public: Optional[bool] = None
    game_mode: Optional[str] = None
    address: Optional[str] = None
    port: Optional[int] = None
    space_id: Optional[str] = None
    build: Optional[str] = None
    map: Optional[str] = None
    online_players: Optional[int] = None

    class Config:
        orm_mode = True


# Api properties
class OnlineGameRef(OnlineGameBase):
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    max_players: Optional[int] = None
    public: Optional[bool] = None
    game_mode: Optional[str] = None
    address: Optional[str] = None
    port: Optional[int] = None
    space_id: Optional[str] = None
    build: Optional[str] = None
    map: Optional[str] = None
    online_players: Optional[int] = None

    class Config:
        orm_mode = True


# Create properties
class OnlineGameCreate(OnlineGameBase):
    online_players: Optional[int] = None
    max_players: Optional[int] = None
    public: Optional[bool] = None
    game_mode: Optional[str] = None
    address: Optional[str] = None
    port: Optional[int] = None
    space_id: Optional[str] = None
    user_id: Optional[str] = None
    build: Optional[str] = None
    map: Optional[str] = None


# Update properties
class OnlineGameUpdate(OnlineGameBase):
    pass


class OnlineGameQuery(CamelCaseModel):
    space_id: Optional[str] = None
    build: Optional[str] = None


class OnlinePlayerLastSeen(CamelCaseModel):
    last_seen_at: Optional[datetime.datetime] = None

    class Config:
        orm_mode = True
