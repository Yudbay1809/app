import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, Text

from app.db import Base


class DeviceSyncState(Base):
    __tablename__ = "device_sync_state"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), ForeignKey("device.id"), nullable=False, unique=True)
    plan_revision = Column(String(64), nullable=True)
    queue_status = Column(String(32), nullable=False, default="idle")
    downloaded_bytes = Column(BigInteger, nullable=False, default=0)
    total_bytes = Column(BigInteger, nullable=False, default=0)
    completed_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    eta_sec = Column(Integer, nullable=True)
    current_media_id = Column(String(36), nullable=True)
    last_error = Column(Text, nullable=True)
    last_report_at = Column(DateTime, nullable=True)
    ack_source = Column(String(64), nullable=True)
    ack_reason = Column(Text, nullable=True)
    ack_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DeviceSyncItem(Base):
    __tablename__ = "device_sync_item"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), ForeignKey("device.id"), nullable=False)
    plan_revision = Column(String(64), nullable=False)
    media_id = Column(String(36), ForeignKey("media.id"), nullable=False)
    priority = Column(String(16), nullable=False, default="P3")
    required_by = Column(String(64), nullable=False, default="background")
    status = Column(String(32), nullable=False, default="queued")
    retry_count = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
