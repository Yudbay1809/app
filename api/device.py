import os
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
DEVICE_OFFLINE_AFTER_SEC = int(os.getenv("SIGNAGE_DEVICE_OFFLINE_AFTER_SEC", "70"))

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


def _resolve_client_ip(request: Request) -> str | None:
    forwarded = (request.headers.get("X-Forwarded-For") or "").strip()
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    real_ip = (request.headers.get("X-Real-IP") or "").strip()
    if real_ip:
        return real_ip
    if request.client and request.client.host:
        return request.client.host
    return None


def _enforce_device_owner(device: Device, account_id: str | None) -> None:
    if not device.owner_account or not account_id:
        return
    if device.owner_account != account_id:
        raise HTTPException(
            status_code=403,
            detail="Device sudah terikat ke akun lain. Login kedua ditolak.",
        )


def _find_device(db: Session, device_id: str) -> Device | None:
    direct = db.query(Device).get(device_id)
    if direct:
        return direct
    return db.query(Device).filter(Device.legacy_id == device_id).first()


def _assign_unique_client_ip(db: Session, device: Device, client_ip: str | None) -> None:
    if not client_ip:
        return
    duplicates = db.query(Device).filter(Device.client_ip == client_ip, Device.id != device.id).all()
    for duplicate in duplicates:
        duplicate.client_ip = None
    device.client_ip = client_ip


def _sync_runtime_status(device: Device, now: datetime | None = None) -> bool:
    current_time = now or datetime.utcnow()
    is_online = device.last_seen is not None and (current_time - device.last_seen).total_seconds() <= DEVICE_OFFLINE_AFTER_SEC
    next_status = "online" if is_online else "offline"
    if device.status != next_status:
        device.status = next_status
        return True
    return False


def _next_device_id(db: Session) -> str:
    rows = db.query(Device.id).filter(Device.id.like("Device-%")).all()
    max_seq = 0
    for (device_id,) in rows:
        value = (device_id or "").strip()
        if not value.startswith("Device-"):
            continue
        suffix = value.split("Device-", 1)[1]
        if suffix.isdigit():
            seq = int(suffix)
            if seq > max_seq:
                max_seq = seq

    next_seq = max_seq + 1
    candidate = f"Device-{next_seq:04d}"
    while db.query(Device).get(candidate) is not None:
        next_seq += 1
        candidate = f"Device-{next_seq:04d}"
    return candidate

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
    client_ip = _resolve_client_ip(request)

    existing = None
    if client_ip:
        existing = db.query(Device).filter(Device.client_ip == client_ip).first()
    if existing is not None:
        _enforce_device_owner(existing, resolved_account)
        if not existing.owner_account and resolved_account:
            existing.owner_account = resolved_account
        existing.name = name
        existing.location = location
        existing.orientation = orientation
        existing.last_seen = datetime.utcnow()
        existing.status = "online"
        _assign_unique_client_ip(db, existing, client_ip)
        db.commit()
        db.refresh(existing)
        return {
            "id": str(existing.id),
            "legacy_id": existing.legacy_id,
            "client_ip": existing.client_ip,
            "name": existing.name,
            "location": existing.location,
            "last_seen": existing.last_seen,
            "status": existing.status,
            "orientation": existing.orientation,
            "owner_account": existing.owner_account,
        }

    device = Device(
        id=_next_device_id(db),
        client_ip=client_ip,
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
        "legacy_id": device.legacy_id,
        "client_ip": device.client_ip,
        "name": device.name,
        "location": device.location,
        "last_seen": device.last_seen,
        "status": device.status,
        "orientation": device.orientation,
        "owner_account": device.owner_account,
    }

@router.post("/{device_id}/heartbeat")
def heartbeat(device_id: str, request: Request, db: Session = Depends(get_db)):
    device = _find_device(db, device_id)
    if device:
        _enforce_device_owner(device, _resolve_account_id(request))
        device.last_seen = datetime.utcnow()
        device.status = "online"
        _assign_unique_client_ip(db, device, _resolve_client_ip(request))
        db.commit()
    return {"ok": True}

@router.get("")
@router.get("/")
def list_devices(request: Request, account_id: str | None = None, db: Session = Depends(get_db)):
    resolved_account = _resolve_account_id(request, account_id)
    devices = db.query(Device).all()
    status_changed = False
    now = datetime.utcnow()
    for device in devices:
        if _sync_runtime_status(device, now):
            status_changed = True
    if status_changed:
        db.commit()
        for device in devices:
            db.refresh(device)
    if resolved_account:
        devices = [d for d in devices if not d.owner_account or d.owner_account == resolved_account]
    return [
        {
            "id": str(d.id),
            "legacy_id": d.legacy_id,
            "client_ip": d.client_ip,
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
    device = _find_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    resolved_account = _resolve_account_id(request, account_id)
    _enforce_device_owner(device, resolved_account)
    if not device.owner_account and resolved_account:
        device.owner_account = resolved_account
    if orientation is not None:
        device.orientation = orientation
    _assign_unique_client_ip(db, device, _resolve_client_ip(request))
    db.commit()
    db.refresh(device)
    return {
        "id": str(device.id),
        "legacy_id": device.legacy_id,
        "client_ip": device.client_ip,
        "name": device.name,
        "location": device.location,
        "last_seen": device.last_seen,
        "status": device.status,
        "orientation": device.orientation,
        "owner_account": device.owner_account,
    }

@router.delete("/{device_id}")
def delete_device(device_id: str, request: Request, account_id: str | None = None, db: Session = Depends(get_db)):
    device = _find_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    _enforce_device_owner(device, _resolve_account_id(request, account_id))

    screens = db.query(Screen).filter(Screen.device_id == device.id).all()
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
    device = _find_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    resolved_account = _resolve_account_id(request, account_id)
    _enforce_device_owner(device, resolved_account)
    need_commit = False
    if not device.owner_account and resolved_account:
        device.owner_account = resolved_account
        need_commit = True
    status_changed = _sync_runtime_status(device)
    if status_changed:
        need_commit = True
    if need_commit:
        db.commit()
        db.refresh(device)

    screens = db.query(Screen).filter(Screen.device_id == device.id).all()

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
            "legacy_id": device.legacy_id,
            "client_ip": device.client_ip,
            "name": device.name,
            "location": device.location,
            "orientation": device.orientation,
            "owner_account": device.owner_account,
        },
        "screens": [
            {
                "screen_id": str(s.id),
                "name": s.name,
                "active_playlist_id": str(s.active_playlist_id) if s.active_playlist_id else None,
                "grid_preset": s.grid_preset or "1x1",
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
                "name": pl.name,
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
