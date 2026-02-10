from pydantic import BaseModel, Field
from datetime import datetime

class DeviceRegisterIn(BaseModel):
    name: str = Field(..., min_length=1)
    location: str = ""
    orientation: str = "portrait"
    account_id: str | None = None

class DeviceOut(BaseModel):
    id: str
    legacy_id: str | None = None
    client_ip: str | None = None
    name: str
    location: str | None = None
    last_seen: datetime | None = None
    status: str
    orientation: str | None = None
    owner_account: str | None = None

    class Config:
        from_attributes = True
