from pydantic import BaseModel
from uuid import UUID

class MediaOut(BaseModel):
    id: UUID
    name: str
    type: str
    path: str
    duration_sec: int
    size: int
    checksum: str

    class Config:
        from_attributes = True
