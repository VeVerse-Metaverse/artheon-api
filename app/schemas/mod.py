import datetime
from typing import Optional, List

from app.schemas import UserRef, FileRef, ModLink
from app.schemas.config import to_camel, CamelCaseModel


class SpaceRef(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    map: Optional[str] = None
    game_mode: Optional[str] = None
    owner: Optional[UserRef] = None

    class Config:
        orm_mode = True


class Mod(CamelCaseModel):
    id: Optional[str] = None
    # Name of the dlc
    name: Optional[str] = None
    title: Optional[str] = None
    # Summary
    summary: Optional[str] = None
    # Markdown description
    description: Optional[str] = None
    # User who created and uploaded the dlc
    owner: Optional[UserRef] = None
    # Latest DLC version
    version: Optional[str] = None
    # Base release name
    release_name: Optional[str] = None
    # List of maps to use (e.g. map1+map2)
    map: Optional[str] = None
    # Latest release date
    released_at: Optional[datetime.datetime] = None
    # Files, including the DLC pak files of different versions, images, etc.
    files: Optional[List[FileRef]] = None
    # Tags
    tags: Optional[List[str]] = None

    # Number of views
    views: Optional[int] = None
    # Number of downloads
    downloads: Optional[int] = None

    # Number of likes
    likes: Optional[int] = None
    # Number of dislikes
    dislikes: Optional[int] = None

    # DLC price, 0 for free DLC
    price: Optional[float] = 0
    # Current discount, 0 for no discount
    discount: Optional[float] = 0
    # Has been purchased by the user, double check if requesting the download
    purchased: Optional[bool] = False

    # Mod links (Web, Facebook, Youtube, Twitter, etc.)
    links: Optional[List[ModLink]] = None
    # Mod platforms (Windows, Mac, Linux, SteamVR, Oculus Quest, etc.)
    platforms: Optional[List[str]] = None

    spaces: Optional[List[SpaceRef]] = None
    game_mode: Optional[str] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


class ModCreate(CamelCaseModel):
    public: Optional[bool] = True
    # Name of the dlc
    name: Optional[str] = None
    title: Optional[str] = None
    # Summary
    summary: Optional[str] = None
    # Markdown description
    description: Optional[str] = None
    # Latest DLC version
    version: Optional[str] = None
    # Base release name
    release_name: Optional[str] = None
    # List of maps to use (e.g. map1+map2)
    map: Optional[str] = None
    # Latest release date
    released_at: Optional[datetime.datetime] = None
    game_mode: Optional[str] = None

    # DLC price, 0 for free DLC
    price: Optional[float] = 0
    # Current discount, 0 for no discount
    discount: Optional[float] = 0

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


class ModUpdate(CamelCaseModel):
    # Name of the dlc
    name: Optional[str] = None
    title: Optional[str] = None
    # Summary
    summary: Optional[str] = None
    # Markdown description
    description: Optional[str] = None
    # Latest DLC version
    version: Optional[str] = None
    # Base release name
    release_name: Optional[str] = None
    # List of maps to use (e.g. map1+map2)
    map: Optional[str] = None
    game_mode: Optional[str] = None
    # Latest release date
    released_at: Optional[datetime.datetime] = None

    # DLC price, 0 for free DLC
    price: Optional[float] = 0
    # Current discount, 0 for no discount
    discount: Optional[float] = 0

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


class ModRef(CamelCaseModel):
    id: Optional[str] = None
    # Name of the dlc
    name: Optional[str] = None
    title: Optional[str] = None
    # Summary
    summary: Optional[str] = None
    # Markdown description
    description: Optional[str] = None
    # User who created and uploaded the dlc
    owner: Optional[UserRef] = None
    # Latest DLC version
    version: Optional[str] = None
    # Base release name
    release_name: Optional[str] = None
    # List of maps to use (e.g. map1+map2)
    map: Optional[str] = None
    game_mode: Optional[str] = None
    # Latest release date
    released_at: Optional[datetime.datetime] = None
    # Files, including the DLC pak files of different versions, images, etc.
    files: Optional[List[FileRef]] = None
    # Tags
    tags: Optional[List[str]] = None

    # Number of views
    views: Optional[int] = None
    # Number of downloads
    downloads: Optional[int] = None

    # Number of likes
    likes: Optional[int] = None
    # Number of dislikes
    dislikes: Optional[int] = None

    # DLC price, 0 for free DLC
    price: Optional[float] = 0
    # Current discount, 0 for no discount
    discount: Optional[float] = 0
    # Has been purchased by the user, double check if requesting the download
    purchased: Optional[bool] = False

    # Mod links (Web, Facebook, Youtube, Twitter, etc.)
    links: Optional[List[ModLink]] = None
    # Mod platforms (Windows, Mac, Linux, SteamVR, Oculus Quest, etc.)
    platforms: Optional[List[str]] = None

    spaces: Optional[List[SpaceRef]] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True


class ModSpaceRef(CamelCaseModel):
    id: Optional[str] = None
    # Name of the dlc
    name: Optional[str] = None
    title: Optional[str] = None
    # Summary
    summary: Optional[str] = None
    # Markdown description
    description: Optional[str] = None
    # User who created and uploaded the dlc
    owner: Optional[UserRef] = None
    # Latest DLC version
    version: Optional[str] = None
    # Base release name
    release_name: Optional[str] = None
    # List of maps to use (e.g. map1+map2)
    map: Optional[str] = None
    game_mode: Optional[str] = None
    # Latest release date
    released_at: Optional[datetime.datetime] = None
    # Files, including the DLC pak files of different versions, images, etc.
    files: Optional[List[FileRef]] = None
    # Tags
    tags: Optional[List[str]] = None

    # Number of views
    views: Optional[int] = None
    # Number of downloads
    downloads: Optional[int] = None

    # Number of likes
    likes: Optional[int] = None
    # Number of dislikes
    dislikes: Optional[int] = None

    # DLC price, 0 for free DLC
    price: Optional[float] = 0
    # Current discount, 0 for no discount
    discount: Optional[float] = 0
    # Has been purchased by the user, double check if requesting the download
    purchased: Optional[bool] = False

    # Mod links (Web, Facebook, Youtube, Twitter, etc.)
    links: Optional[List[ModLink]] = None
    # Mod platforms (Windows, Mac, Linux, SteamVR, Oculus Quest, etc.)
    platforms: Optional[List[str]] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        orm_mode = True

class SpaceModRef(CamelCaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    map: Optional[str] = None
    game_mode: Optional[str] = None
    owner: Optional[UserRef] = None
    mod: Optional[ModSpaceRef] = None

    class Config:
        orm_mode = True
