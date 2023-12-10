from sqlalchemy import Column, Float, ForeignKey, Text, Integer, TIMESTAMP, func, Unicode
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app import models
from app.database import Base


class ModPlatformAssociation(Base):
    __tablename__ = 'mod_platforms'
    mod_id = Column(UUID, ForeignKey('mods.id'), primary_key=True)
    platform_id = Column(UUID, ForeignKey('platforms.id'), primary_key=True)
    # Relations
    mod = relationship("Mod", back_populates="platforms")
    platform = relationship("Platform", back_populates="mods")


# Windows, Mac, Linux, Android, iOS, Oculus Quest, SteamVR.
class Platform(Base):
    __tablename__ = "platforms"
    id = Column(UUID, primary_key=True)
    name = Column(Text, index=True, unique=True)
    mods: InstrumentedAttribute = relationship("ModPlatformAssociation", back_populates="platform")


class ModLink(Base):
    __tablename__ = 'mod_links'
    mod_id = Column(UUID, ForeignKey('mods.id'), primary_key=True)
    link_type_id = Column(UUID, ForeignKey('link_types.id'), primary_key=True)
    url = Column(Text)
    # Relations
    mod = relationship("Mod", back_populates="links")
    link_type = relationship("LinkType")


class LinkType(Base):
    __tablename__ = "link_types"
    id = Column(UUID, primary_key=True)
    # Web, Facebook, Twitter, Youtube...
    type = Column(Text, index=True, unique=True)


class Mod(models.Entity):
    __tablename__ = "mods"
    __mapper_args__ = dict(polymorphic_identity="mod")

    id = Column(UUID, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    # Name of the dlc
    name = Column(Text, nullable=True)
    # Name of the dlc
    title = Column(Text, nullable=True)
    # Short plain text summary
    summary = Column(Text, nullable=True)
    # Markdown description
    description = Column(Text, nullable=True)
    # Base release version
    release_name = Column(Text)
    # Base release version
    map = Column(Text)
    # Latest DLC version
    version = Column(Text)
    # Latest DLC version release date
    released_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    # Number of downloads
    downloads = Column(Integer, default=0)
    # DLC price, 0 for free DLC
    price = Column(Float, default=0)
    # Current DLC discount, 0 for no discount, 1 for 100% discount.
    discount = Column(Float, default=0)
    # Mod supported platforms
    platforms: InstrumentedAttribute = relationship("ModPlatformAssociation", back_populates="mod")
    # Mod links
    links: InstrumentedAttribute = relationship("ModLink", back_populates="mod")
    # Space ref
    spaces: InstrumentedAttribute
    game_mode = Column(Text, nullable=True)


Mod.spaces = relationship("Space", foreign_keys="[Space.mod_id]", back_populates="mod", uselist=True, lazy='select')
