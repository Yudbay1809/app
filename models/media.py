import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, BigInteger, DateTime
from app.db import Base

class Media(Base):
    __tablename__ = "media"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    path = Column(String, nullable=False)
    duration_sec = Column(Integer, default=10)
    size = Column(BigInteger, nullable=False)
    checksum = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
