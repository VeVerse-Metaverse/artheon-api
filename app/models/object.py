from sqlalchemy import Column, Float, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID

from app import models


class Object(models.Entity):
    __tablename__ = "objects"
    __mapper_args__ = dict(polymorphic_identity="object")

    id = Column(UUID, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)

    type = Column(Text, nullable=True)  # Object type (drawing, print, photograph, etc)
    name = Column(Text, nullable=True)
    artist = Column(Text, nullable=True)  # Object creator
    date = Column(Text, nullable=True)  # Object origin date
    description = Column(Text, nullable=True)
    medium = Column(Text, nullable=True)
    dimensions = Column(Text, nullable=True)
    museum = Column(Text, nullable=True)
    width = Column(Float, nullable=True)  # cm
    height = Column(Float, nullable=True)
    length = Column(Float, nullable=True)  # cm
    scale_multiplier = Column(Float, nullable=True, default=1) # 
    source = Column(Text, nullable=True)  # Name of the source museum
    source_id = Column(Text, nullable=True)  # ID of the object at source museum API/database
    source_url = Column(Text, nullable=True)  # URL of the source museum
    license = Column(Text, nullable=True)
    copyright = Column(Text, nullable=True)
    credit = Column(Text, nullable=True)
    origin = Column(Text, nullable=True)  # The known origin location of the object where it has been found or created
    location = Column(Text, nullable=True)  # The current known location of the object
    year = Column(Integer, nullable=True)
