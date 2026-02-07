from pydantic import BaseModel
from datetime import time

class ScheduleOut(BaseModel):
    id: str
    screen_id: str
    playlist_id: str
    day_of_week: int
    start_time: time
    end_time: time

    class Config:
        from_attributes = True
