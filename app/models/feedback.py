from sqlalchemy import Column, func, Text, ForeignKey
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

from app.database import Base


class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(UUID, primary_key=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), primary_key=True)
    user_id = Column(UUID, ForeignKey('users.id', ondelete="SET DEFAULT"), default="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX", primary_key=True)
    email = Column(Text, nullable=False)
    text = Column(Text, nullable=False)
