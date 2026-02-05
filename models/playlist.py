import uuid
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey
from app.db import Base

class Playlist(Base):
    __tablename__ = "playlist"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    screen_id = Column(String(36), ForeignKey("screen.id"), nullable=False)
    name = Column(String, nullable=False)

class PlaylistItem(Base):
    __tablename__ = "playlist_item"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    playlist_id = Column(String(36), ForeignKey("playlist.id"), nullable=False)
    media_id = Column(String(36), ForeignKey("media.id"), nullable=False)
    order = Column(Integer, nullable=False)
    duration_sec = Column(Integer)
    enabled = Column(Boolean, default=True)
