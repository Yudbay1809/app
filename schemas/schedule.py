from pydantic import BaseModel
from uuid import UUID
from datetime import time

class ScheduleOut(BaseModel):
    id: UUID
    screen_id: UUID
    playlist_id: UUID
    day_of_week: int
    start_time: time
    end_time: time

    class Config:
        from_attributes = True
