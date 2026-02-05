from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models.device import Device
from app.models.screen import Screen
from app.models.schedule import Schedule
from app.models.playlist import Playlist, PlaylistItem
from app.models.media import Media
from datetime import datetime

router = APIRouter(prefix="/devices", tags=["devices"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register")
def register_device(name: str, location: str = "", db: Session = Depends(get_db)):
    device = Device(name=name, location=location, last_seen=datetime.utcnow(), status="online")
    db.add(device)
    db.commit()
    db.refresh(device)
    screen_a = Screen(device_id=device.id, name="Screen A")
    screen_b = Screen(device_id=device.id, name="Screen B")
    db.add(screen_a)
    db.add(screen_b)
    db.commit()
    return {
        "id": str(device.id),
        "name": device.name,
        "location": device.location,
        "last_seen": device.last_seen,
        "status": device.status,
    }

@router.post("/{device_id}/heartbeat")
def heartbeat(device_id: str, db: Session = Depends(get_db)):
    device = db.query(Device).get(device_id)
    if device:
        device.last_seen = datetime.utcnow()
        device.status = "online"
        db.commit()
    return {"ok": True}

@router.get("")
def list_devices(db: Session = Depends(get_db)):
    devices = db.query(Device).all()
    return [
        {
            "id": str(d.id),
            "name": d.name,
            "location": d.location,
            "last_seen": d.last_seen,
            "status": d.status,
        }
        for d in devices
    ]

@router.get("/{device_id}/config")
def device_config(device_id: str, db: Session = Depends(get_db)):
    device = db.query(Device).get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    screens = db.query(Screen).filter(Screen.device_id == device_id).all()

    schedules = []
    playlists = []
    playlist_items = []
    media_ids = set()

    for screen in screens:
        screen_schedules = db.query(Schedule).filter(Schedule.screen_id == screen.id).all()
        schedules.extend(screen_schedules)

        screen_playlists = db.query(Playlist).filter(Playlist.screen_id == screen.id).all()
        playlists.extend(screen_playlists)

        for pl in screen_playlists:
            items = db.query(PlaylistItem).filter(PlaylistItem.playlist_id == pl.id).all()
            playlist_items.extend(items)
            for it in items:
                media_ids.add(it.media_id)

    media = []
    if media_ids:
        media = db.query(Media).filter(Media.id.in_(list(media_ids))).all()

    return {
        "device_id": str(device.id),
        "screens": [
            {
                "screen_id": str(s.id),
                "name": s.name,
                "schedules": [
                    {
                        "day_of_week": sc.day_of_week,
                        "start_time": str(sc.start_time),
                        "end_time": str(sc.end_time),
                        "playlist_id": str(sc.playlist_id),
                    }
                    for sc in schedules if sc.screen_id == s.id
                ],
            }
            for s in screens
        ],
        "playlists": [
            {
                "id": str(pl.id),
                "screen_id": str(pl.screen_id),
                "items": [
                    {
                        "order": it.order,
                        "media_id": str(it.media_id),
                        "duration_sec": it.duration_sec,
                    }
                    for it in playlist_items if it.playlist_id == pl.id
                ],
            }
            for pl in playlists
        ],
        "media": [
            {
                "id": str(m.id),
                "type": m.type,
                "path": m.path,
                "checksum": m.checksum,
                "duration_sec": m.duration_sec,
            }
            for m in media
        ],
    }
