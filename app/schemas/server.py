import datetime
from typing import Optional

from app.schemas.config import CamelCaseModel


class ServerBase(CamelCaseModel):
    id: Optional[str] = None


# Api properties
class Server(ServerBase):
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    public: Optional[bool] = None
    host: Optional[str] = None
    port: Optional[int] = None
    space_id: Optional[str] = None
    max_players: Optional[int] = None
    game_mode: Optional[str] = None
    build: Optional[str] = None
    map: Optional[str] = None
    online_players: Optional[int] = None

    class Config:
        orm_mode = True


# Api properties
class ServerRef(ServerBase):
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    public: Optional[bool] = None
    host: Optional[str] = None
    port: Optional[int] = None
    space_id: Optional[str] = None
    max_players: Optional[int] = None
    game_mode: Optional[str] = None
    build: Optional[str] = None
    map: Optional[str] = None
    online_players: Optional[int] = None
    status: Optional[str] = None
    name: Optional[str] = None
    details: Optional[str] = None
    image: Optional[str] = None

    class Config:
        orm_mode = True


# Create properties
class ServerCreate(ServerBase):
    public: Optional[bool] = None
    host: Optional[str] = None
    port: Optional[int] = None
    space_id: Optional[str] = None
    max_players: Optional[int] = None
    game_mode: Optional[str] = None
    build: Optional[str] = None
    map: Optional[str] = None
    status: Optional[str] = None
    name: Optional[str] = None
    image: Optional[str] = None


class ServerUpdate(ServerBase):
    public: Optional[bool] = None
    online_players: Optional[int] = None
    map: Optional[str] = None
    game_mode: Optional[str] = None
    space_id: Optional[str] = None
    status: Optional[str] = None
    details: Optional[str] = None


class ServerQuery(CamelCaseModel):
    space_id: Optional[str] = None
    build: Optional[str] = None
