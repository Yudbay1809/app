import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from app.db import Base

class Device(Base):
    __tablename__ = "device"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    legacy_id = Column(String(36), nullable=True)
    client_ip = Column(String, nullable=True, unique=True)
    name = Column(String, nullable=False)
    location = Column(String)
    owner_account = Column(String, nullable=True)
    last_seen = Column(DateTime)
    status = Column(String, default="offline")
    orientation = Column(String, default="portrait")
    cached_media_low_ids = Column(Text, nullable=True)
    cached_media_ids = Column(Text, nullable=True)
    cached_media_high_ids = Column(Text, nullable=True)
    media_cache_updated_at = Column(DateTime, nullable=True)
