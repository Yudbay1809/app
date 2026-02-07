from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models.device import Device
from app.models.screen import Screen
from app.models.schedule import Schedule
from app.models.playlist import Playlist, PlaylistItem
from app.models.media import Media
from app.schemas.device import DeviceRegisterIn
from datetime import datetime

router = APIRouter(prefix="/devices", tags=["devices"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _resolve_account_id(request: Request, explicit: str | None = None) -> str | None:
    candidate = (explicit or "").strip()
    if candidate:
        return candidate
    header_account = (request.headers.get("X-Account-ID") or "").strip()
    if header_account:
        return header_account
    header_api = (request.headers.get("X-API-Key") or "").strip()
    if header_api:
        return header_api
    return None


def _enforce_device_owner(device: Device, account_id: str | None) -> None:
    if not device.owner_account or not account_id:
        return
    if device.owner_account != account_id:
        raise HTTPException(
            status_code=403,
            detail="Device sudah terikat ke akun lain. Login kedua ditolak.",
        )

@router.post("/register")
def register_device(
    request: Request,
    payload: DeviceRegisterIn | None = Body(None),
    name: str | None = None,
    location: str = "",
    orientation: str = "portrait",
    account_id: str | None = None,
    db: Session = Depends(get_db),
):
    if payload is not None:
        name = payload.name
        location = payload.location
        orientation = payload.orientation
        account_id = payload.account_id

    if not name:
        raise HTTPException(status_code=422, detail="Missing device name")

    resolved_account = _resolve_account_id(request, account_id)
    device = Device(
        name=name,
        location=location,
        owner_account=resolved_account,
        last_seen=datetime.utcnow(),
        status="online",
        orientation=orientation,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    main_screen = Screen(device_id=device.id, name="Main")
    db.add(main_screen)
    db.commit()
    return {
        "id": str(device.id),
        "name": device.name,
        "location": device.location,
        "last_seen": device.last_seen,
        "status": device.status,
        "orientation": device.orientation,
        "owner_account": device.owner_account,
    }

@router.post("/{device_id}/heartbeat")
def heartbeat(device_id: str, request: Request, db: Session = Depends(get_db)):
    device = db.query(Device).get(device_id)
    if device:
        _enforce_device_owner(device, _resolve_account_id(request))
        device.last_seen = datetime.utcnow()
        device.status = "online"
        db.commit()
    return {"ok": True}

@router.get("")
@router.get("/")
def list_devices(request: Request, account_id: str | None = None, db: Session = Depends(get_db)):
    resolved_account = _resolve_account_id(request, account_id)
    devices = db.query(Device).all()
    if resolved_account:
        devices = [d for d in devices if not d.owner_account or d.owner_account == resolved_account]
    return [
        {
            "id": str(d.id),
            "name": d.name,
            "location": d.location,
            "last_seen": d.last_seen,
            "status": d.status,
            "orientation": d.orientation,
            "owner_account": d.owner_account,
        }
        for d in devices
    ]

@router.put("/{device_id}")
def update_device(
    device_id: str,
    request: Request,
    orientation: str | None = None,
    account_id: str | None = None,
    db: Session = Depends(get_db),
):
    device = db.query(Device).get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    resolved_account = _resolve_account_id(request, account_id)
    _enforce_device_owner(device, resolved_account)
    if not device.owner_account and resolved_account:
        device.owner_account = resolved_account
    if orientation is not None:
        device.orientation = orientation
    db.commit()
    db.refresh(device)
    return {
        "id": str(device.id),
        "name": device.name,
        "location": device.location,
        "last_seen": device.last_seen,
        "status": device.status,
        "orientation": device.orientation,
        "owner_account": device.owner_account,
    }

@router.delete("/{device_id}")
def delete_device(device_id: str, request: Request, account_id: str | None = None, db: Session = Depends(get_db)):
    device = db.query(Device).get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    _enforce_device_owner(device, _resolve_account_id(request, account_id))

    screens = db.query(Screen).filter(Screen.device_id == device_id).all()
    screen_ids = [str(screen.id) for screen in screens]

    if screen_ids:
        playlists = db.query(Playlist).filter(Playlist.screen_id.in_(screen_ids)).all()
        playlist_ids = [str(playlist.id) for playlist in playlists]

        if playlist_ids:
            db.query(Schedule).filter(Schedule.playlist_id.in_(playlist_ids)).delete(synchronize_session=False)
            db.query(PlaylistItem).filter(PlaylistItem.playlist_id.in_(playlist_ids)).delete(synchronize_session=False)
            db.query(Playlist).filter(Playlist.id.in_(playlist_ids)).delete(synchronize_session=False)

        db.query(Schedule).filter(Schedule.screen_id.in_(screen_ids)).delete(synchronize_session=False)
        db.query(Screen).filter(Screen.id.in_(screen_ids)).delete(synchronize_session=False)

    db.delete(device)
    db.commit()
    return {"ok": True}

@router.get("/{device_id}/config")
def device_config(device_id: str, request: Request, account_id: str | None = None, db: Session = Depends(get_db)):
    device = db.query(Device).get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    resolved_account = _resolve_account_id(request, account_id)
    _enforce_device_owner(device, resolved_account)
    if not device.owner_account and resolved_account:
        device.owner_account = resolved_account
        db.commit()
        db.refresh(device)

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
        "device": {
            "id": str(device.id),
            "name": device.name,
            "location": device.location,
            "orientation": device.orientation,
            "owner_account": device.owner_account,
        },
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
