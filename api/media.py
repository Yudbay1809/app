from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import SessionLocal
from app.models.media import Media
from app.models.playlist import Playlist, PlaylistItem
from app.services.storage import save_file

router = APIRouter(prefix="/media", tags=["media"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _resolved_media_name(name: str | None, file: UploadFile) -> str:
    candidate = (name or "").strip()
    if candidate and candidate.lower() != "unnamed":
        return candidate
    fallback = (file.filename or "").strip()
    if fallback:
        return fallback
    return "media-file"

@router.post("/upload")
def upload_media(
    file: UploadFile = File(...),
    name: str | None = None,
    type: str = "image",
    duration_sec: int = 10,
    db: Session = Depends(get_db)
):
    media_name = _resolved_media_name(name, file)
    path, size, checksum = save_file(file)
    media = Media(name=media_name, type=type, path=f"/{path}", duration_sec=duration_sec, size=size, checksum=checksum)
    db.add(media)
    db.commit()
    db.refresh(media)
    return media

@router.post("/upload-to-playlist")
def upload_media_to_playlist(
    playlist_id: str,
    file: UploadFile = File(...),
    name: str | None = None,
    type: str = "image",
    duration_sec: int = 10,
    order: int | None = None,
    enabled: bool = True,
    db: Session = Depends(get_db),
):
    playlist = db.query(Playlist).get(playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    media_name = _resolved_media_name(name, file)
    path, size, checksum = save_file(file)
    media = Media(name=media_name, type=type, path=f"/{path}", duration_sec=duration_sec, size=size, checksum=checksum)
    db.add(media)
    db.commit()
    db.refresh(media)

    if order is None:
        max_order = db.query(PlaylistItem.order).filter(PlaylistItem.playlist_id == playlist_id).order_by(PlaylistItem.order.desc()).first()
        next_order = (max_order[0] + 1) if max_order else 1
    else:
        next_order = order

    item = PlaylistItem(
        playlist_id=playlist_id,
        media_id=media.id,
        order=next_order,
        duration_sec=duration_sec if type == "image" else None,
        enabled=enabled,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return {"media": media, "playlist_item": item}

@router.get("")
def list_media(db: Session = Depends(get_db)):
    return db.query(Media).all()


@router.get("/page")
def list_media_page(
    offset: int = 0,
    limit: int = 100,
    q: str | None = None,
    type: str | None = None,
    db: Session = Depends(get_db),
):
    safe_offset = max(0, offset)
    safe_limit = max(1, min(limit, 500))

    query = db.query(Media)
    if type:
        normalized_type = type.strip().lower()
        if normalized_type in {"image", "video"}:
            query = query.filter(func.lower(Media.type) == normalized_type)
    if q:
        keyword = f"%{q.strip().lower()}%"
        if keyword != "%%":
            query = query.filter(
                func.lower(Media.name).like(keyword) | func.lower(Media.path).like(keyword)
            )

    total = query.count()
    items = (
        query.order_by(Media.created_at.desc(), Media.id.desc())
        .offset(safe_offset)
        .limit(safe_limit)
        .all()
    )
    return {
        "items": items,
        "total": total,
        "offset": safe_offset,
        "limit": safe_limit,
    }

@router.get("/{media_id}")
def get_media(media_id: str, db: Session = Depends(get_db)):
    media = db.query(Media).get(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    return media

@router.delete("/{media_id}")
def delete_media(media_id: str, db: Session = Depends(get_db)):
    media = db.query(Media).get(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    db.delete(media)
    db.commit()
    return {"ok": True}
