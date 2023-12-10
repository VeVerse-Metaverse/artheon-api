from sqlalchemy import Column, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app import models


class Collection(models.Entity):
    __tablename__ = "collections"
    __mapper_args__ = dict(polymorphic_identity="collection")

    id = Column(UUID, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    name = Column(Text, nullable=True)
    description = Column(Text, nullable=True)

    collectables = relationship("Collectable", foreign_keys="[Collectable.collection_id]", cascade="all, delete", passive_deletes=True)
