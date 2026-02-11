import uuid
from sqlalchemy import Column, Integer, Time, ForeignKey, String
from app.db import Base

class Schedule(Base):
    __tablename__ = "schedule"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    screen_id = Column(String(36), ForeignKey("screen.id"), nullable=False)
    playlist_id = Column(String(36), ForeignKey("playlist.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    note = Column(String, nullable=True)
    countdown_sec = Column(Integer, nullable=True)
