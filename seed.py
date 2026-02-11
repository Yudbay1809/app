import base64
import hashlib
import os
from datetime import time
from sqlalchemy.orm import Session
from app.db import SessionLocal, Base, engine
from app.models.device import Device
from app.models.screen import Screen
from app.models.playlist import Playlist, PlaylistItem
from app.models.schedule import Schedule
from app.models.media import Media


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        os.makedirs("storage/media", exist_ok=True)

        device = Device(name="Device 1", location="Main Location", status="online")
        db.add(device)
        db.commit()
        db.refresh(device)

        screen_a = Screen(device_id=device.id, name="Screen A", transition_duration_sec=1)
        screen_b = Screen(device_id=device.id, name="Screen B", transition_duration_sec=1)
        db.add(screen_a)
        db.add(screen_b)
        db.commit()
        db.refresh(screen_a)
        db.refresh(screen_b)

        playlist_a = Playlist(screen_id=screen_a.id, name="Default A")
        playlist_b = Playlist(screen_id=screen_b.id, name="Default B")
        db.add(playlist_a)
        db.add(playlist_b)
        db.commit()
        db.refresh(playlist_a)
        db.refresh(playlist_b)

        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
        )
        media_entries = []
        for filename, label in [("screen_a.png", "Screen A Placeholder"), ("screen_b.png", "Screen B Placeholder")]:
            path = os.path.join("storage", "media", filename)
            with open(path, "wb") as f:
                f.write(png_bytes)
            size = len(png_bytes)
            checksum = hashlib.sha256(png_bytes).hexdigest()
            media = Media(name=label, type="image", path=f"/storage/media/{filename}", duration_sec=10, size=size, checksum=checksum)
            db.add(media)
            db.commit()
            db.refresh(media)
            media_entries.append(media)

        item_a = PlaylistItem(playlist_id=playlist_a.id, media_id=media_entries[0].id, order=1, duration_sec=10, enabled=True)
        item_b = PlaylistItem(playlist_id=playlist_b.id, media_id=media_entries[1].id, order=1, duration_sec=10, enabled=True)
        db.add(item_a)
        db.add(item_b)
        db.commit()

        schedule_a = Schedule(
            screen_id=screen_a.id,
            playlist_id=playlist_a.id,
            day_of_week=1,
            start_time=time(8, 0, 0),
            end_time=time(17, 0, 0),
        )
        schedule_b = Schedule(
            screen_id=screen_b.id,
            playlist_id=playlist_b.id,
            day_of_week=1,
            start_time=time(8, 0, 0),
            end_time=time(17, 0, 0),
        )
        db.add(schedule_a)
        db.add(schedule_b)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
