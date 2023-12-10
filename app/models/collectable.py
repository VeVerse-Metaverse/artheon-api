from sqlalchemy import Column, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship

from app.database import Base


class Collectable(Base):
    __tablename__ = "collectables"

    id = Column(UUID, primary_key=True)
    object_id = Column(UUID, ForeignKey("objects.id", ondelete="CASCADE"))
    collection_id = Column(UUID, ForeignKey("collections.id", ondelete="CASCADE"))

    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())

    # Relations
    object = relationship("Object", foreign_keys=[object_id])
    collection = relationship("Collection", foreign_keys=[collection_id])
