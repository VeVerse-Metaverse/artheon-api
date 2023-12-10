import datetime
from typing import Optional, List

from app.schemas.config import CamelCaseModel
from app.schemas.server import ServerRef


class PresenceSpaceRef(CamelCaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

    class Config:
        orm_mode = True


# Api properties
class PresenceServerRef(CamelCaseModel):
    updated_at: Optional[datetime.datetime] = None
    public: Optional[bool] = None
    host: Optional[str] = None
    port: Optional[int] = None
    game_mode: Optional[str] = None
    build: Optional[str] = None
    online_players: Optional[int] = None

    class Config:
        orm_mode = True


class Presence(CamelCaseModel):
    space: Optional[PresenceSpaceRef] = None
    server: Optional[PresenceServerRef] = None
    status: Optional[str] = None

    class Config:
        orm_mode = True


class FileRef(CamelCaseModel):
    id: Optional[str] = None
    type: Optional[str] = None
    url: Optional[str] = None
    mime: Optional[str] = None
    size: Optional[int] = 0
    width: Optional[int] = 0
    height: Optional[int] = 0
    version: Optional[int] = 0
    entity_id: Optional[str] = None

    class Config:
        orm_mode = True


class PersonaRef(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    configuration: Optional[str] = None
    files: Optional[List[FileRef]] = []

    class Config:
        orm_mode = True


class UserBase(CamelCaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None

    class Config:
        orm_mode = True


# Properties to receive via API upon creation
class UserCreate(CamelCaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    name: Optional[str] = None
    invite_code: Optional[str] = None


# Properties to receive via API on update
class UserUpdate(CamelCaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None

    class Config:
        orm_mode = True


# Properties to receive via API on update
class UserUpdatePassword(CamelCaseModel):
    password: Optional[str] = None
    new_password: Optional[str] = None
    new_password_confirmation: Optional[str] = None

    class Config:
        orm_mode = True


# Additional properties to return via API
class User(UserBase):
    id: Optional[str] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    views: Optional[int] = None
    level: Optional[int] = 0
    rank: Optional[str] = None
    experience: Optional[int] = 0
    presence: Optional[Presence] = None
    # likables: Optional[List[Any]] = []  # likable_entities: Optional[List[LikableRef]] = []
    # accessibles: Optional[List[Any]] = []  # accessible_entities: Optional[List[AccessibleEntityRef]] = []
    # files: Optional[List[FileRef]] = []  # files: Optional[List[FileRef]] = []
    # avatar: Optional[FileRef] = None
    # avatars: Optional[List[FileRef]] = []
    # followers: Optional[List[Any]] = []
    # following: Optional[List[Any]] = []
    # ip: Optional[str] = None
    # referer: Optional[str] = None
    # entity_type = 'user'
    api_key: Optional[str] = None
    is_active: Optional[bool] = None
    # avatar_url: Optional[str] = None  # not used
    is_admin: Optional[bool] = None
    is_muted: Optional[bool] = None
    is_banned: Optional[bool] = None
    eth_address: Optional[str] = None
    default_persona: Optional[PersonaRef] = None


# Represents user reference without private user data
class UserRef(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    views: Optional[int] = None
    level: Optional[int] = 0
    rank: Optional[str] = None
    files: Optional[List[FileRef]] = []
    total_likes: Optional[int] = []
    total_dislikes: Optional[int] = []
    eth_address: Optional[str] = None
    address: Optional[str] = None
    default_persona: Optional[PersonaRef] = None
    presence: Optional[Presence] = None
    # avatar: Optional[FileRef] = None

    # avatar_url: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    is_muted: Optional[bool] = None
    is_banned: Optional[bool] = None

    class Config:
        orm_mode = True


# Represents user reference without private user data
class UserFriendRef(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    views: Optional[int] = None
    level: Optional[int] = 0
    rank: Optional[str] = None
    files: Optional[List[FileRef]] = []
    total_likes: Optional[int] = []
    total_dislikes: Optional[int] = []
    server: Optional[ServerRef] = None
    last_seen: Optional[str] = None
    presence: Optional[Presence] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    is_muted: Optional[bool] = None
    is_banned: Optional[bool] = None

    class Config:
        orm_mode = True


class UserExperienceRef(CamelCaseModel):
    id: Optional[str] = None
    level: Optional[int] = 0
    experience: Optional[int] = 0

    class Config:
        orm_mode = True


# Represents user reference without private user data
class UserAdminRef(UserRef):
    is_admin: Optional[bool] = None

    class Config:
        orm_mode = True


# Represents user reference without private user data
class UserMutedRef(UserRef):
    is_muted: Optional[bool] = None

    class Config:
        orm_mode = True


# Represents user reference without private user data
class UserBannedRef(UserRef):
    is_banned: Optional[bool] = None

    class Config:
        orm_mode = True
