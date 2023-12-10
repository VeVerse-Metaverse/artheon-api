from sqlalchemy import Column, Text, ForeignKey, Float, Boolean, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app.models import Entity


class Space(Entity):
    __tablename__ = "spaces"

    id = Column(UUID, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    name = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    map = Column(Text, nullable=True)
    mod_id = Column(UUID, ForeignKey("mods.id", ondelete="CASCADE"), nullable=True)
    type = Column(Text, nullable=True)
    scheduled = Column(Boolean)
    game_mode = Column(Text, nullable=True)

    mod: InstrumentedAttribute
    placeables: InstrumentedAttribute  # = relationship("Placeable", back_populates="space", lazy='noload', viewonly=True)

    __mapper_args__ = dict(polymorphic_identity="space")


class Placeable(Entity):
    __tablename__ = "placeables"

    id = Column(UUID, ForeignKey('entities.id', ondelete='CASCADE'), primary_key=True)
    entity_id = Column(UUID, ForeignKey("entities.id", ondelete="SET NULL"))
    space_id = Column(UUID, ForeignKey("spaces.id", ondelete="CASCADE"))
    placeable_class_id = Column(UUID, ForeignKey("placeable_classes.id", ondelete="CASCADE"))

    slot_id = Column(UUID, name="slot_id", nullable=True)
    p_x = Column(Float, name="offset_x", nullable=True)
    p_y = Column(Float, name="offset_y", nullable=True)
    p_z = Column(Float, name="offset_z", nullable=True)
    r_x = Column(Float, name="rotation_x", nullable=True)
    r_y = Column(Float, name="rotation_y", nullable=True)
    r_z = Column(Float, name="rotation_z", nullable=True)
    s_x = Column(Float, name="scale_x", nullable=True)
    s_y = Column(Float, name="scale_y", nullable=True)
    s_z = Column(Float, name="scale_z", nullable=True)
    type = Column(Text, name="type", nullable=True, index=True)

    # Relations
    entity = relationship("Entity", foreign_keys=[entity_id], viewonly=True, lazy='select')
    # space = relationship("Space", back_populates="placeables", foreign_keys=[space_id], cascade="none", viewonly=True, lazy='noload')

    __mapper_args__ = dict(polymorphic_identity='placeable', inherit_condition=id == Entity.id)


Space.mod = relationship("Mod", foreign_keys="[Space.mod_id]", back_populates="spaces", lazy='select')
Placeable.placeable_class = relationship("PlaceableClass", foreign_keys="[Placeable.placeable_class_id]", lazy='select')

Space.placeables = relationship("Placeable", foreign_keys="[Placeable.space_id]", lazy='noload', passive_deletes=True)
