from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
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

@router.post("/upload")
def upload_media(
    file: UploadFile = File(...),
    name: str = "Unnamed",
    type: str = "image",
    duration_sec: int = 10,
    db: Session = Depends(get_db)
):
    path, size, checksum = save_file(file)
    media = Media(name=name, type=type, path=f"/{path}", duration_sec=duration_sec, size=size, checksum=checksum)
    db.add(media)
    db.commit()
    db.refresh(media)
    return media

@router.post("/upload-to-playlist")
def upload_media_to_playlist(
    playlist_id: str,
    file: UploadFile = File(...),
    name: str = "Unnamed",
    type: str = "image",
    duration_sec: int = 10,
    order: int | None = None,
    enabled: bool = True,
    db: Session = Depends(get_db),
):
    playlist = db.query(Playlist).get(playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    path, size, checksum = save_file(file)
    media = Media(name=name, type=type, path=f"/{path}", duration_sec=duration_sec, size=size, checksum=checksum)
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
