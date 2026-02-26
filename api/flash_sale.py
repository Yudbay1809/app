import json
import math
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.device import Device
from app.models.flash_sale import FlashSaleConfig
from app.models.media import Media

router = APIRouter(prefix="/flash-sale", tags=["flash-sale"])
DEFAULT_PREFLIGHT_MBPS = float((os.getenv("SIGNAGE_PREFLIGHT_MBPS", "8") or "8").strip())


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


def _normalize_warmup_minutes(value: int | None) -> int | None:
    if value is None:
        return None
    if value <= 0:
        return None
    if value > 240:
        raise HTTPException(status_code=400, detail="warmup_minutes max 240")
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


def _parse_cached_media_ids(csv: str | None) -> set[str]:
    output: set[str] = set()
    for item in (csv or "").split(","):
        value = item.strip()
        if value:
            output.add(value)
    return output


def _parse_product_rows(products_json: str) -> list[dict]:
    try:
        decoded = json.loads(products_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid products_json: {exc.msg}") from exc
    if not isinstance(decoded, list):
        raise HTTPException(status_code=400, detail="products_json must be a JSON array")
    rows: list[dict] = []
    for row in decoded:
        if isinstance(row, dict):
            rows.append(row)
    return rows


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
            "warmup_minutes": config.warmup_minutes,
            "activated_at": config.activated_at.isoformat() if config.activated_at else None,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        },
    }


@router.put("/device/{device_id}/now")
def upsert_flash_sale_now(
    device_id: str,
    note: str | None = None,
    countdown_sec: int | None = None,
    warmup_minutes: int | None = None,
    products_json: str | None = None,
    db: Session = Depends(get_db),
):
    _find_device_or_404(db, device_id)
    config = _find_or_create_config(db, device_id)
    config.enabled = True
    config.note = (note or "").strip() or None
    config.countdown_sec = _normalize_countdown(countdown_sec)
    config.warmup_minutes = _normalize_warmup_minutes(warmup_minutes)
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
    warmup_minutes: int | None = None,
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
    config.warmup_minutes = _normalize_warmup_minutes(warmup_minutes)
    config.products_json = _normalize_products_json(products_json, db)
    config.schedule_days = _normalize_schedule_days(schedule_days or "")
    config.schedule_start_time = _normalize_time_hms(start_time or "")
    config.schedule_end_time = _normalize_time_hms(end_time or "")
    config.activated_at = datetime.utcnow()
    config.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(config)
    return {"ok": True, "device_id": device_id}


@router.get("/device/{device_id}/preflight")
def flash_sale_preflight(
    device_id: str,
    products_json: str | None = None,
    download_mbps: float | None = None,
    db: Session = Depends(get_db),
):
    device = _find_device_or_404(db, device_id)
    config = db.query(FlashSaleConfig).filter(FlashSaleConfig.device_id == device_id).first()
    raw_products = (products_json or "").strip()
    if not raw_products and config:
        raw_products = (config.products_json or "").strip()
    if not raw_products:
        raise HTTPException(status_code=400, detail="products_json is required (query or existing config)")

    normalized_products = _normalize_products_json(raw_products, db)
    rows = _parse_product_rows(normalized_products)
    required_ids = {
        str(row.get("media_id", "")).strip()
        for row in rows
        if str(row.get("name", "")).strip() and str(row.get("media_id", "")).strip()
    }
    cached_ids = _parse_cached_media_ids(device.cached_media_ids)
    missing_ids = sorted(required_ids - cached_ids)
    cached_required_ids = sorted(required_ids & cached_ids)

    missing_media = []
    missing_total_bytes = 0
    if missing_ids:
        missing_media = db.query(Media).filter(Media.id.in_(missing_ids)).all()
        missing_total_bytes = sum(int(item.size or 0) for item in missing_media)

    mbps = download_mbps if (download_mbps is not None and download_mbps > 0) else DEFAULT_PREFLIGHT_MBPS
    bytes_per_sec = max(mbps, 0.1) * 1024 * 1024
    estimated_sec = round(missing_total_bytes / bytes_per_sec, 2) if missing_total_bytes > 0 else 0.0
    recommended_warmup_minutes = 0
    if estimated_sec > 0:
        recommended_warmup_minutes = min(240, max(1, math.ceil((estimated_sec * 1.35) / 60)))

    return {
        "device_id": str(device.id),
        "ready": len(missing_ids) == 0,
        "required_count": len(required_ids),
        "cached_required_count": len(cached_required_ids),
        "missing_count": len(missing_ids),
        "missing_media_ids": missing_ids,
        "missing_total_bytes": missing_total_bytes,
        "download_mbps_used": mbps,
        "estimated_download_sec": estimated_sec,
        "estimated_download_human": str(timedelta(seconds=int(math.ceil(estimated_sec)))),
        "recommended_warmup_minutes": recommended_warmup_minutes,
        "configured_warmup_minutes": (config.warmup_minutes if config else None),
        "cache_updated_at": device.media_cache_updated_at.isoformat() if device.media_cache_updated_at else None,
        "missing_media": [
            {
                "id": str(item.id),
                "name": item.name,
                "type": item.type,
                "path": item.path,
                "size": int(item.size or 0),
            }
            for item in missing_media
        ],
    }


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
