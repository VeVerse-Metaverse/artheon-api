from sqlalchemy import Column, ForeignKey, Text, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app.database import Base


class BuildJob(Base):
    __tablename__ = "build_jobs"

    id = Column(UUID, primary_key=True)
    # Link to the mod we build for
    mod_id = Column(UUID, ForeignKey("mods.id", ondelete="CASCADE"), nullable=True)
    mod: InstrumentedAttribute
    # Job status "pending", "processing", "fail", "success"
    status = Column(Text, default="pending")
    # Id of the user that created a job
    user_id = Column(UUID, ForeignKey("users.id", ondelete="SET DEFAULT"), default='XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX', nullable=True)
    # Id of the worker that took the task for processing
    worker_id = Column(UUID, ForeignKey("users.id", ondelete="SET DEFAULT"), default='XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX', nullable=True)
    # Job configuration
    configuration = Column(Text)
    # Job platform
    platform = Column(Text)
    # Job to make a server or client build
    server = Column(Boolean)
    # Map(s) to process
    map = Column(Text)
    # Release name to base
    release_name = Column(Text)
    # Version number
    version = Column(Integer)


BuildJob.mod = relationship("Mod", foreign_keys="[BuildJob.mod_id]", lazy='select')
