from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models.device import Device
from app.models.screen import Screen

router = APIRouter(prefix="/screens", tags=["screens"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _parse_grid_preset(value: str) -> tuple[int, int] | None:
    preset = (value or "").strip().lower()
    if "x" not in preset:
        return None
    parts = preset.split("x")
    if len(parts) != 2:
        return None
    rows = int(parts[0]) if parts[0].isdigit() else -1
    cols = int(parts[1]) if parts[1].isdigit() else -1
    if rows < 1 or cols < 1 or rows > 4 or cols > 4:
        return None
    return rows, cols


def _validate_grid_for_device(device: Device, grid_preset: str) -> str:
    preset = (grid_preset or "1x1").strip().lower()
    parsed = _parse_grid_preset(preset)
    if parsed is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid grid_preset format. Use NxM with range 1..4, e.g. 1x2 or 2x1.",
        )
    rows, cols = parsed
    orientation = (device.orientation or "portrait").strip().lower()
    if orientation == "landscape" and cols < rows:
        raise HTTPException(
            status_code=400,
            detail="Grid preset is not valid for landscape device. Landscape requires cols >= rows.",
        )
    if orientation != "landscape" and rows < cols:
        raise HTTPException(
            status_code=400,
            detail="Grid preset is not valid for portrait device. Portrait requires rows >= cols.",
        )
    return preset


@router.post("")
def create_screen(
    device_id: str,
    name: str,
    active_playlist_id: str | None = None,
    grid_preset: str = "1x1",
    db: Session = Depends(get_db),
):
    device = db.query(Device).get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    screen = Screen(
        device_id=device_id,
        name=name,
        active_playlist_id=active_playlist_id,
        grid_preset=_validate_grid_for_device(device, grid_preset),
    )
    db.add(screen)
    db.commit()
    db.refresh(screen)
    return screen


@router.get("")
def list_screens(device_id: str, db: Session = Depends(get_db)):
    return db.query(Screen).filter(Screen.device_id == device_id).all()


@router.put("/{screen_id}")
def update_screen(
    screen_id: str,
    name: str | None = None,
    active_playlist_id: str | None = None,
    grid_preset: str | None = None,
    db: Session = Depends(get_db),
):
    screen = db.query(Screen).get(screen_id)
    if not screen:
        raise HTTPException(status_code=404, detail="Screen not found")
    device = db.query(Device).get(screen.device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if name is not None:
        screen.name = name
    if active_playlist_id is not None:
        screen.active_playlist_id = active_playlist_id or None
    if grid_preset is not None:
        screen.grid_preset = _validate_grid_for_device(device, grid_preset)
    db.commit()
    db.refresh(screen)
    return screen


@router.delete("/{screen_id}")
def delete_screen(screen_id: str, db: Session = Depends(get_db)):
    screen = db.query(Screen).get(screen_id)
    if not screen:
        raise HTTPException(status_code=404, detail="Screen not found")
    db.delete(screen)
    db.commit()
    return {"ok": True}
