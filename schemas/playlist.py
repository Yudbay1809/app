from pydantic import BaseModel
from uuid import UUID

class PlaylistItemOut(BaseModel):
    id: UUID
    playlist_id: UUID
    media_id: UUID
    order: int
    duration_sec: int | None = None
    enabled: bool

    class Config:
        from_attributes = True

class PlaylistOut(BaseModel):
    id: UUID
    screen_id: UUID
    name: str

    class Config:
        from_attributes = True
