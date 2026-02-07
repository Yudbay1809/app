from pydantic import BaseModel

class MediaOut(BaseModel):
    id: str
    name: str
    type: str
    path: str
    duration_sec: int
    size: int
    checksum: str

    class Config:
        from_attributes = True
