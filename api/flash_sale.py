import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.device import Device
from app.models.flash_sale import FlashSaleConfig
from app.models.media import Media

router = APIRouter(prefix="/flash-sale", tags=["flash-sale"])


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


def _normalize_time_hms(value: str) -> str:
    raw = (value or "").strip()
    parts = raw.split(":")
    if len(parts) not in (2, 3):
        raise HTTPException(status_code=400, detail="Time must be HH:MM or HH:MM:SS")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) == 3 else 0
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid time value") from exc
    if hour < 0 or hour > 23 or minute < 0 or minute > 59 or second < 0 or second > 59:
        raise HTTPException(status_code=400, detail="Invalid time range")
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def _normalize_schedule_days(values: str) -> str:
    raw = (values or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="schedule_days is required")
    days: set[int] = set()
    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        try:
            day = int(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="schedule_days must be comma-separated 0-6") from exc
        if day < 0 or day > 6:
            raise HTTPException(status_code=400, detail="schedule_days must be in range 0-6")
        days.add(day)
    if not days:
        raise HTTPException(status_code=400, detail="schedule_days must contain at least one day")
    return ",".join(str(day) for day in sorted(days))


def _normalize_products_json(value: str | None, db: Session) -> str:
    raw = (value or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="products_json is required")
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid products_json: {exc.msg}") from exc
    if not isinstance(decoded, list):
        raise HTTPException(status_code=400, detail="products_json must be a JSON array")

    rows: list[dict[str, str]] = []
    media_ids: set[str] = set()
    for index, row in enumerate(decoded):
        if not isinstance(row, dict):
            raise HTTPException(status_code=400, detail=f"products_json[{index}] must be an object")
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
                detail=f"products_json[{index}].media_id is required when name is set",
            )
        rows.append(normalized)
        media_ids.add(normalized["media_id"])

    if not rows:
        raise HTTPException(status_code=400, detail="products_json must contain at least one product with name")

    found_ids = {
        media_id
        for (media_id,) in db.query(Media.id).filter(Media.id.in_(list(media_ids))).all()
    }
    missing = sorted(media_ids - found_ids)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"products_json contains unknown media_id: {', '.join(missing)}",
        )
    return json.dumps(rows, separators=(",", ":"))


def _find_device_or_404(db: Session, device_id: str) -> Device:
    item = db.query(Device).get(device_id)
    if not item:
        raise HTTPException(status_code=404, detail="Device not found")
    return item


def _find_or_create_config(db: Session, device_id: str) -> FlashSaleConfig:
    config = db.query(FlashSaleConfig).filter(FlashSaleConfig.device_id == device_id).first()
    if config:
        return config
    config = FlashSaleConfig(device_id=device_id, enabled=True)
    db.add(config)
    db.flush()
    return config


@router.get("/device/{device_id}")
def get_flash_sale(device_id: str, db: Session = Depends(get_db)):
    _find_device_or_404(db, device_id)
    config = db.query(FlashSaleConfig).filter(FlashSaleConfig.device_id == device_id).first()
    if not config:
        return {"device_id": device_id, "flash_sale": None}
    return {
        "device_id": device_id,
        "flash_sale": {
            "enabled": bool(config.enabled),
            "note": config.note,
            "countdown_sec": config.countdown_sec,
            "products_json": config.products_json,
            "schedule_days": config.schedule_days,
            "schedule_start_time": config.schedule_start_time,
            "schedule_end_time": config.schedule_end_time,
            "activated_at": config.activated_at.isoformat() if config.activated_at else None,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        },
    }


@router.put("/device/{device_id}/now")
def upsert_flash_sale_now(
    device_id: str,
    note: str | None = None,
    countdown_sec: int | None = None,
    products_json: str | None = None,
    db: Session = Depends(get_db),
):
    _find_device_or_404(db, device_id)
    config = _find_or_create_config(db, device_id)
    config.enabled = True
    config.note = (note or "").strip() or None
    config.countdown_sec = _normalize_countdown(countdown_sec)
    config.products_json = _normalize_products_json(products_json, db)
    config.schedule_days = None
    config.schedule_start_time = None
    config.schedule_end_time = None
    config.activated_at = datetime.utcnow()
    config.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(config)
    return {"ok": True, "device_id": device_id}


@router.put("/device/{device_id}/schedule")
def upsert_flash_sale_schedule(
    device_id: str,
    note: str | None = None,
    countdown_sec: int | None = None,
    products_json: str | None = None,
    schedule_days: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    db: Session = Depends(get_db),
):
    _find_device_or_404(db, device_id)
    config = _find_or_create_config(db, device_id)
    config.enabled = True
    config.note = (note or "").strip() or None
    config.countdown_sec = _normalize_countdown(countdown_sec)
    config.products_json = _normalize_products_json(products_json, db)
    config.schedule_days = _normalize_schedule_days(schedule_days or "")
    config.schedule_start_time = _normalize_time_hms(start_time or "")
    config.schedule_end_time = _normalize_time_hms(end_time or "")
    config.activated_at = datetime.utcnow()
    config.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(config)
    return {"ok": True, "device_id": device_id}


@router.delete("/device/{device_id}")
def disable_flash_sale(device_id: str, db: Session = Depends(get_db)):
    _find_device_or_404(db, device_id)
    config = db.query(FlashSaleConfig).filter(FlashSaleConfig.device_id == device_id).first()
    if not config:
        return {"ok": True, "device_id": device_id}
    config.enabled = False
    config.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "device_id": device_id}
