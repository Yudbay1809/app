from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models.screen import Screen

router = APIRouter(prefix="/screens", tags=["screens"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("")
def create_screen(device_id: str, name: str, db: Session = Depends(get_db)):
    screen = Screen(device_id=device_id, name=name)
    db.add(screen)
    db.commit()
    db.refresh(screen)
    return screen


@router.get("")
def list_screens(device_id: str, db: Session = Depends(get_db)):
    return db.query(Screen).filter(Screen.device_id == device_id).all()


@router.put("/{screen_id}")
def update_screen(screen_id: str, name: str, db: Session = Depends(get_db)):
    screen = db.query(Screen).get(screen_id)
    if not screen:
        raise HTTPException(status_code=404, detail="Screen not found")
    screen.name = name
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
