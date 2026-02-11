import uuid
from sqlalchemy import Column, Integer, String, ForeignKey
from app.db import Base


class Screen(Base):
    __tablename__ = "screen"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), ForeignKey("device.id"), nullable=False)
    name = Column(String, nullable=False)
    active_playlist_id = Column(String(36), nullable=True)
    grid_preset = Column(String(16), default="1x1")
    transition_duration_sec = Column(Integer, default=1)
