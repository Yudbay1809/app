from fastapi import APIRouter, Depends, HTTPException
from datetime import time
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models.schedule import Schedule

router = APIRouter(prefix="/schedules", tags=["schedules"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _parse_time(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM or HH:MM:SS.") from exc


def _validate_no_overlap(
    db: Session,
    screen_id: str,
    day_of_week: int,
    start_time: time,
    end_time: time,
    exclude_id: str | None = None,
) -> None:
    if start_time >= end_time:
        raise HTTPException(status_code=400, detail="start_time must be before end_time.")

    conditions = [
        Schedule.screen_id == screen_id,
        Schedule.day_of_week == day_of_week,
        Schedule.start_time < end_time,
        Schedule.end_time > start_time,
    ]
    if exclude_id is not None:
        conditions.append(Schedule.id != exclude_id)

    overlap = db.query(Schedule).filter(*conditions).first()
    if overlap:
        raise HTTPException(status_code=400, detail="Schedule overlaps with an existing entry.")


def _normalize_countdown(countdown_sec: int | None) -> int | None:
    if countdown_sec is None:
        return None
    if countdown_sec <= 0:
        return None
    return countdown_sec


@router.post("")
def create_schedule(
    screen_id: str,
    playlist_id: str,
    day_of_week: int,
    start_time: str,
    end_time: str,
    note: str | None = None,
    countdown_sec: int | None = None,
    db: Session = Depends(get_db),
):
    start = _parse_time(start_time)
    end = _parse_time(end_time)
    _validate_no_overlap(db, screen_id, day_of_week, start, end)
    schedule = Schedule(
        screen_id=screen_id,
        playlist_id=playlist_id,
        day_of_week=day_of_week,
        start_time=start,
        end_time=end,
        note=(note or "").strip() or None,
        countdown_sec=_normalize_countdown(countdown_sec),
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule

@router.get("")
def list_schedules(screen_id: str, db: Session = Depends(get_db)):
    return db.query(Schedule).filter(Schedule.screen_id == screen_id).all()

@router.put("/{schedule_id}")
def update_schedule(
    schedule_id: str,
    day_of_week: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    playlist_id: str | None = None,
    note: str | None = None,
    countdown_sec: int | None = None,
    db: Session = Depends(get_db),
):
    schedule = db.query(Schedule).get(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    new_day = day_of_week if day_of_week is not None else schedule.day_of_week
    new_start = _parse_time(start_time) if start_time is not None else schedule.start_time
    new_end = _parse_time(end_time) if end_time is not None else schedule.end_time
    _validate_no_overlap(db, schedule.screen_id, new_day, new_start, new_end, exclude_id=schedule_id)

    schedule.day_of_week = new_day
    schedule.start_time = new_start
    schedule.end_time = new_end
    if playlist_id is not None:
        schedule.playlist_id = playlist_id
    if note is not None:
        schedule.note = note.strip() or None
    if countdown_sec is not None:
        schedule.countdown_sec = _normalize_countdown(countdown_sec)
    db.commit()
    db.refresh(schedule)
    return schedule

@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: str, db: Session = Depends(get_db)):
    schedule = db.query(Schedule).get(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(schedule)
    db.commit()
    return {"ok": True}
