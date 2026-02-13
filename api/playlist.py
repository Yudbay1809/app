import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models.playlist import Playlist, PlaylistItem
from app.models.media import Media
from app.models.schedule import Schedule
from app.models.screen import Screen

router = APIRouter(prefix="/playlists", tags=["playlists"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _normalize_countdown(value: int | None) -> int | None:
    if value is None:
        return None
    if value <= 0:
        return None
    return value


def _normalize_entity_id(value: str, field_name: str) -> str:
    normalized = (value or "").strip()
    if normalized.startswith("{") and normalized.endswith("}"):
        normalized = normalized[1:-1].strip()
    if not normalized:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    return normalized


def _normalize_flash_items_json(
    value: str | None,
    db: Session,
) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid flash_items_json: {exc.msg}") from exc
    if not isinstance(decoded, list):
        raise HTTPException(status_code=400, detail="flash_items_json must be a JSON array")

    normalized_rows: list[dict[str, str]] = []
    media_ids: set[str] = set()
    for index, row in enumerate(decoded):
        if not isinstance(row, dict):
            raise HTTPException(status_code=400, detail=f"flash_items_json[{index}] must be an object")
        normalized = {
            "name": str(row.get("name", "")).strip(),
            "brand": str(row.get("brand", "")).strip(),
            "normal_price": str(row.get("normal_price", "")).strip(),
            "promo_price": str(row.get("promo_price", "")).strip(),
            "stock": str(row.get("stock", "")).strip(),
            "media_id": str(row.get("media_id", "")).strip(),
        }
        if not normalized["name"]:
            continue
        if not normalized["media_id"]:
            raise HTTPException(
                status_code=400,
                detail=f"flash_items_json[{index}].media_id is required when name is set",
            )
        normalized_rows.append(normalized)
        media_ids.add(normalized["media_id"])

    if media_ids:
        found = {
            row[0]
            for row in db.query(Media.id).filter(Media.id.in_(list(media_ids))).all()
        }
        missing = sorted(media_ids - found)
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"flash_items_json contains unknown media_id: {', '.join(missing)}",
            )
    return json.dumps(normalized_rows, separators=(",", ":"))

@router.post("")
def create_playlist(
    screen_id: str,
    name: str,
    is_flash_sale: bool = False,
    flash_note: str | None = None,
    flash_countdown_sec: int | None = None,
    flash_items_json: str | None = None,
    db: Session = Depends(get_db),
):
    screen_id = _normalize_entity_id(screen_id, "screen_id")
    playlist = Playlist(
        screen_id=screen_id,
        name=name,
        is_flash_sale=is_flash_sale,
        flash_note=(flash_note or "").strip() or None,
        flash_countdown_sec=_normalize_countdown(flash_countdown_sec),
        flash_items_json=_normalize_flash_items_json(flash_items_json, db),
    )
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    return playlist

@router.get("")
def list_playlists(screen_id: str, db: Session = Depends(get_db)):
    screen_id = _normalize_entity_id(screen_id, "screen_id")
    return db.query(Playlist).filter(Playlist.screen_id == screen_id).all()

@router.put("/{playlist_id}")
def update_playlist(
    playlist_id: str,
    name: str | None = None,
    is_flash_sale: bool | None = None,
    flash_note: str | None = None,
    flash_countdown_sec: int | None = None,
    flash_items_json: str | None = None,
    db: Session = Depends(get_db),
):
    playlist_id = _normalize_entity_id(playlist_id, "playlist_id")
    playlist = db.query(Playlist).get(playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise HTTPException(status_code=400, detail="Playlist name cannot be empty")
        playlist.name = cleaned
    if is_flash_sale is not None:
        playlist.is_flash_sale = is_flash_sale
    if flash_note is not None:
        playlist.flash_note = flash_note.strip() or None
    if flash_countdown_sec is not None:
        playlist.flash_countdown_sec = _normalize_countdown(flash_countdown_sec)
    if flash_items_json is not None:
        playlist.flash_items_json = _normalize_flash_items_json(flash_items_json, db)
    db.commit()
    db.refresh(playlist)
    return playlist

@router.delete("/{playlist_id}")
def delete_playlist(playlist_id: str, db: Session = Depends(get_db)):
    playlist_id = _normalize_entity_id(playlist_id, "playlist_id")
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
    playlist_id = _normalize_entity_id(playlist_id, "playlist_id")
    media_id = _normalize_entity_id(media_id, "media_id")
    item = PlaylistItem(playlist_id=playlist_id, media_id=media_id, order=order, duration_sec=duration_sec, enabled=enabled)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.get("/{playlist_id}/items")
def list_items(playlist_id: str, db: Session = Depends(get_db)):
    playlist_id = _normalize_entity_id(playlist_id, "playlist_id")
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
    item_id = _normalize_entity_id(item_id, "item_id")
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
    item_id = _normalize_entity_id(item_id, "item_id")
    item = db.query(PlaylistItem).get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Playlist item not found")
    db.delete(item)
    db.commit()
    return {"ok": True}
