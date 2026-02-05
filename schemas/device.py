from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class DeviceOut(BaseModel):
    id: UUID
    name: str
    location: str | None = None
    last_seen: datetime | None = None
    status: str

    class Config:
        from_attributes = True
