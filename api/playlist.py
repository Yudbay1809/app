from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models.playlist import Playlist, PlaylistItem
from app.models.schedule import Schedule
from app.models.screen import Screen

router = APIRouter(prefix="/playlists", tags=["playlists"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("")
def create_playlist(screen_id: str, name: str, db: Session = Depends(get_db)):
    playlist = Playlist(screen_id=screen_id, name=name)
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    return playlist

@router.get("")
def list_playlists(screen_id: str, db: Session = Depends(get_db)):
    return db.query(Playlist).filter(Playlist.screen_id == screen_id).all()

@router.put("/{playlist_id}")
def update_playlist(playlist_id: str, name: str, db: Session = Depends(get_db)):
    playlist = db.query(Playlist).get(playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    playlist.name = name
    db.commit()
    db.refresh(playlist)
    return playlist

@router.delete("/{playlist_id}")
def delete_playlist(playlist_id: str, db: Session = Depends(get_db)):
    playlist = db.query(Playlist).get(playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    db.query(PlaylistItem).filter(PlaylistItem.playlist_id == playlist_id).delete(synchronize_session=False)
    db.query(Schedule).filter(Schedule.playlist_id == playlist_id).delete(synchronize_session=False)
    db.query(Screen).filter(Screen.active_playlist_id == playlist_id).update(
        {"active_playlist_id": None},
        synchronize_session=False,
    )
    db.delete(playlist)
    db.commit()
    return {"ok": True}

@router.post("/{playlist_id}/items")
def add_item(playlist_id: str, media_id: str, order: int, duration_sec: int | None = None, enabled: bool = True, db: Session = Depends(get_db)):
    item = PlaylistItem(playlist_id=playlist_id, media_id=media_id, order=order, duration_sec=duration_sec, enabled=enabled)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.get("/{playlist_id}/items")
def list_items(playlist_id: str, db: Session = Depends(get_db)):
    playlist = db.query(Playlist).get(playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return (
        db.query(PlaylistItem)
        .filter(PlaylistItem.playlist_id == playlist_id)
        .order_by(PlaylistItem.order.asc(), PlaylistItem.id.asc())
        .all()
    )

@router.put("/items/{item_id}")
def update_item(item_id: str, order: int | None = None, duration_sec: int | None = None, enabled: bool | None = None, db: Session = Depends(get_db)):
    item = db.query(PlaylistItem).get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Playlist item not found")
    if order is not None:
        item.order = order
    if duration_sec is not None:
        item.duration_sec = duration_sec
    if enabled is not None:
        item.enabled = enabled
    db.commit()
    db.refresh(item)
    return item

@router.delete("/items/{item_id}")
def delete_item(item_id: str, db: Session = Depends(get_db)):
    item = db.query(PlaylistItem).get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Playlist item not found")
    db.delete(item)
    db.commit()
    return {"ok": True}
