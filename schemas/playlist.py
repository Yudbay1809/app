from pydantic import BaseModel

class PlaylistItemOut(BaseModel):
    id: str
    playlist_id: str
    media_id: str
    order: int
    duration_sec: int | None = None
    enabled: bool

    class Config:
        from_attributes = True

class PlaylistOut(BaseModel):
    id: str
    screen_id: str
    name: str

    class Config:
        from_attributes = True
