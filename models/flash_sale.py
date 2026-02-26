import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.db import Base


class FlashSaleConfig(Base):
    __tablename__ = "flash_sale_config"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), ForeignKey("device.id"), nullable=False, unique=True)
    enabled = Column(Boolean, nullable=False, default=True)
    note = Column(String, nullable=True)
    countdown_sec = Column(Integer, nullable=True)
    products_json = Column(String, nullable=True)
    schedule_days = Column(String, nullable=True)  # CSV: 0,1,2,3,4,5,6
    schedule_start_time = Column(String, nullable=True)  # HH:MM:SS
    schedule_end_time = Column(String, nullable=True)  # HH:MM:SS
    warmup_minutes = Column(Integer, nullable=True)  # pre-download window before schedule starts
    activated_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
