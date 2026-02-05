import uuid
from sqlalchemy import Column, String, ForeignKey
from app.db import Base

class Screen(Base):
    __tablename__ = "screen"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), ForeignKey("device.id"), nullable=False)
    name = Column(String, nullable=False)
