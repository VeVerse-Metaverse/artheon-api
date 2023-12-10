from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class PlaceableClass(Base):
    __tablename__ = "placeable_classes"

    id = Column(UUID, primary_key=True)
    name = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    category = Column(Text, nullable=True)
    cls = Column(Text, nullable=True)
    # mod_id = Column(UUID, ForeignKey("mods.id", ondelete="CASCADE"), nullable=True)
    # mod: InstrumentedAttribute

# PlaceableClass.mod = relationship("Mod", foreign_keys="[PlaceableClass.mod_id]", back_populates="placeable_classes", lazy='select')
