import json
import os
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models.device import Device
from app.models.device_sync import DeviceSyncItem, DeviceSyncState
from app.models.flash_sale import FlashSaleConfig
from app.models.screen import Screen
from app.models.schedule import Schedule
from app.models.playlist import Playlist, PlaylistItem
from app.models.media import Media
from app.schemas.device import DeviceRegisterIn
from datetime import datetime, timedelta

router = APIRouter(prefix="/devices", tags=["devices"])
DEVICE_OFFLINE_AFTER_SEC = int(os.getenv("SIGNAGE_DEVICE_OFFLINE_AFTER_SEC", "70"))
DEFAULT_TRANSITION_DURATION_SEC = 1
SYNC_PRELOAD_WINDOW_MIN = int(os.getenv("SIGNAGE_SYNC_PRELOAD_WINDOW_MIN", "30"))

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


def _parse_hms(value: str) -> tuple[int, int, int] | None:
    raw = (value or "").strip()
    parts = raw.split(":")
    if len(parts) not in (2, 3):
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) == 3 else 0
    except ValueError:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59 or second < 0 or second > 59:
        return None
    return hour, minute, second


def _normalize_media_id_set(values: list[str] | None) -> list[str]:
    if not values:
        return []
    normalized: set[str] = set()
    for item in values:
        value = str(item or "").strip()
        if value:
            normalized.add(value)
    return sorted(normalized)


def _parse_cached_media_ids(csv: str | None) -> set[str]:
    output: set[str] = set()
    for item in (csv or "").split(","):
        value = item.strip()
        if value:
            output.add(value)
    return output


def _download_status_presentation(download_status: str) -> tuple[str, str]:
    mapping = {
        "completed": ("Selesai", "#16A34A"),
        "in_progress": ("Sedang Download", "#F59E0B"),
        "not_reported": ("Belum Lapor", "#6B7280"),
        "no_content": ("Tidak Ada Konten", "#2563EB"),
    }
    return mapping.get(download_status, ("Unknown", "#6B7280"))


def _compute_media_cache_status(db: Session, device: Device) -> dict:
    required_ids = _collect_required_media_ids(db, device)
    cached_ids = _parse_cached_media_ids(device.cached_media_ids)
    missing_ids = sorted(required_ids - cached_ids)
    extra_ids = sorted(cached_ids - required_ids)
    has_report = device.media_cache_updated_at is not None

    if len(required_ids) == 0:
        download_status = "no_content"
    elif not has_report:
        download_status = "not_reported"
    elif len(missing_ids) == 0:
        download_status = "completed"
    else:
        download_status = "in_progress"
    status_label, status_color = _download_status_presentation(download_status)

    return {
        "required_count": len(required_ids),
        "cached_count": len(cached_ids),
        "missing_count": len(missing_ids),
        "ready": len(missing_ids) == 0,
        "download_status": download_status,
        "download_status_label": status_label,
        "download_status_color": status_color,
        "required_media_ids": sorted(required_ids),
        "missing_media_ids": missing_ids,
        "extra_cached_media_ids": extra_ids,
        "cache_updated_at": device.media_cache_updated_at.isoformat() if device.media_cache_updated_at else None,
    }


def _collect_required_media_ids(db: Session, device: Device) -> set[str]:
    screens = db.query(Screen).filter(Screen.device_id == device.id).all()
    schedules = []
    playlists = []
    playlist_items = []
    media_ids: set[str] = set()

    for screen in screens:
        screen_schedules = db.query(Schedule).filter(Schedule.screen_id == screen.id).all()
        schedules.extend(screen_schedules)

        screen_playlists = db.query(Playlist).filter(Playlist.screen_id == screen.id).all()
        playlists.extend(screen_playlists)

        for pl in screen_playlists:
            items = db.query(PlaylistItem).filter(PlaylistItem.playlist_id == pl.id).all()
            playlist_items.extend(items)
            for it in items:
                media_ids.add(str(it.media_id))

    known_playlist_ids = {str(pl.id) for pl in playlists}
    referenced_playlist_ids: set[str] = set()
    for screen in screens:
        active_id = str(screen.active_playlist_id or "").strip()
        if active_id:
            referenced_playlist_ids.add(active_id)
    for sc in schedules:
        pid = str(sc.playlist_id or "").strip()
        if pid:
            referenced_playlist_ids.add(pid)

    missing_referenced_ids = [
        pid for pid in referenced_playlist_ids if pid not in known_playlist_ids
    ]
    if missing_referenced_ids:
        referenced_playlists = db.query(Playlist).filter(Playlist.id.in_(missing_referenced_ids)).all()
        for pl in referenced_playlists:
            items = db.query(PlaylistItem).filter(PlaylistItem.playlist_id == pl.id).all()
            playlist_items.extend(items)
            for it in items:
                media_ids.add(str(it.media_id))

    flash_sale_config = db.query(FlashSaleConfig).filter(FlashSaleConfig.device_id == device.id).first()
    flash_sale_runtime = _resolve_flash_sale_runtime(flash_sale_config, datetime.utcnow())
    if flash_sale_runtime and flash_sale_runtime.get("products_json"):
        try:
            rows = json.loads(flash_sale_runtime["products_json"])
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    media_id = str(row.get("media_id", "")).strip()
                    if media_id:
                        media_ids.add(media_id)
        except Exception:
            pass

    return media_ids


def _resolve_flash_sale_runtime(config: FlashSaleConfig | None, now: datetime) -> dict | None:
    if not config:
        return None
    enabled = bool(config.enabled)
    countdown_sec = config.countdown_sec if (config.countdown_sec or 0) > 0 else None
    active = False
    runtime_start: datetime | None = None
    runtime_end: datetime | None = None
    countdown_end: datetime | None = None

    has_schedule = bool(
        (config.schedule_days or "").strip()
        and (config.schedule_start_time or "").strip()
        and (config.schedule_end_time or "").strip()
    )
    if enabled and has_schedule:
        allowed_days: set[int] = set()
        for item in (config.schedule_days or "").split(","):
            value = item.strip()
            if not value:
                continue
            try:
                day = int(value)
            except ValueError:
                continue
            if 0 <= day <= 6:
                allowed_days.add(day)
        hms_start = _parse_hms(config.schedule_start_time or "")
        hms_end = _parse_hms(config.schedule_end_time or "")
        if allowed_days and hms_start and hms_end:
            now_day = now.weekday() % 7
            if now_day in allowed_days:
                start = datetime(now.year, now.month, now.day, hms_start[0], hms_start[1], hms_start[2])
                end = datetime(now.year, now.month, now.day, hms_end[0], hms_end[1], hms_end[2])
                if end <= start:
                    end = end + timedelta(days=1)
                if (now >= start) and (now < end):
                    active = True
                    runtime_start = start
                    runtime_end = end
    elif enabled:
        active = True
        runtime_start = config.activated_at

    if countdown_sec is not None:
        if runtime_start is not None:
            countdown_end = runtime_start + timedelta(seconds=countdown_sec)
        elif config.activated_at is not None:
            countdown_end = config.activated_at + timedelta(seconds=countdown_sec)
        if countdown_end is not None and runtime_end is not None and countdown_end > runtime_end:
            countdown_end = runtime_end
        if countdown_end is not None and now >= countdown_end:
            active = False

    return {
        "enabled": enabled,
        "active": active,
        "note": config.note,
        "countdown_sec": countdown_sec,
        "products_json": config.products_json,
        "schedule_days": config.schedule_days,
        "schedule_start_time": config.schedule_start_time,
        "schedule_end_time": config.schedule_end_time,
        "runtime_start_at": runtime_start.isoformat() if runtime_start else None,
        "runtime_end_at": runtime_end.isoformat() if runtime_end else None,
        "countdown_end_at": countdown_end.isoformat() if countdown_end else None,
        "activated_at": config.activated_at.isoformat() if config.activated_at else None,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


def _priority_rank(priority: str) -> int:
    ranking = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return ranking.get(priority, 9)


def _playlist_media_ids(db: Session, playlist_id: str) -> set[str]:
    if not playlist_id:
        return set()
    rows = db.query(PlaylistItem.media_id).filter(PlaylistItem.playlist_id == playlist_id).all()
    return {str(media_id) for (media_id,) in rows if media_id}


def _schedule_start_datetime_for_day(base_day: datetime, value) -> datetime | None:
    if value is None:
        return None
    return datetime(
        base_day.year,
        base_day.month,
        base_day.day,
        value.hour,
        value.minute,
        value.second,
    )


def _build_device_sync_plan(db: Session, device: Device) -> dict:
    now = datetime.utcnow()
    flash_media_ids: set[str] = set()
    active_playlist_media_ids: set[str] = set()
    upcoming_playlist_media_ids: set[str] = set()

    # P0: flash sale active now
    flash_sale_config = db.query(FlashSaleConfig).filter(FlashSaleConfig.device_id == device.id).first()
    flash_sale_runtime = _resolve_flash_sale_runtime(flash_sale_config, now)
    if flash_sale_runtime and flash_sale_runtime.get("active") and flash_sale_runtime.get("products_json"):
        try:
            rows = json.loads(flash_sale_runtime["products_json"])
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    media_id = str(row.get("media_id", "")).strip()
                    if media_id:
                        flash_media_ids.add(media_id)
        except Exception:
            pass

    screens = db.query(Screen).filter(Screen.device_id == device.id).all()
    preload_until = now + timedelta(minutes=SYNC_PRELOAD_WINDOW_MIN)

    # P1: active playlist per-screen
    for screen in screens:
        active_id = str(screen.active_playlist_id or "").strip()
        if active_id:
            active_playlist_media_ids.update(_playlist_media_ids(db, active_id))

    # P2: schedule starting soon (within preload window)
    for screen in screens:
        schedules = db.query(Schedule).filter(Schedule.screen_id == screen.id).all()
        for item in schedules:
            if item.start_time is None:
                continue
            for day_offset in (0, 1):
                base_day = now + timedelta(days=day_offset)
                if int(item.day_of_week) != (base_day.weekday() % 7):
                    continue
                start_at = _schedule_start_datetime_for_day(base_day, item.start_time)
                if start_at is None:
                    continue
                if now <= start_at <= preload_until:
                    upcoming_playlist_media_ids.update(_playlist_media_ids(db, str(item.playlist_id)))

    all_required_ids = _collect_required_media_ids(db, device)
    cached_ids = _parse_cached_media_ids(device.cached_media_ids)

    priority_by_media: dict[str, tuple[str, str]] = {}

    for media_id in flash_media_ids:
        priority_by_media[media_id] = ("P0", "flash_sale_active")
    for media_id in active_playlist_media_ids:
        existing = priority_by_media.get(media_id)
        if not existing or _priority_rank("P1") < _priority_rank(existing[0]):
            priority_by_media[media_id] = ("P1", "playlist_active")
    for media_id in upcoming_playlist_media_ids:
        existing = priority_by_media.get(media_id)
        if not existing or _priority_rank("P2") < _priority_rank(existing[0]):
            priority_by_media[media_id] = ("P2", "schedule_upcoming")
    for media_id in all_required_ids:
        if media_id not in priority_by_media:
            priority_by_media[media_id] = ("P3", "background_required")

    ordered_ids = sorted(
        priority_by_media.keys(),
        key=lambda media_id: (_priority_rank(priority_by_media[media_id][0]), media_id),
    )
    media_rows = (
        db.query(Media)
        .filter(Media.id.in_(ordered_ids))
        .all()
        if ordered_ids
        else []
    )
    media_by_id = {str(row.id): row for row in media_rows}

    plan_items: list[dict] = []
    total_bytes = 0
    total_download_bytes = 0
    download_count = 0
    for media_id in ordered_ids:
        media_row = media_by_id.get(media_id)
        if media_row is None:
            continue
        priority, required_by = priority_by_media[media_id]
        size = int(media_row.size or 0)
        total_bytes += size
        action = "skip" if media_id in cached_ids else "download"
        if action == "download":
            total_download_bytes += size
            download_count += 1
        plan_items.append(
            {
                "media_id": media_id,
                "name": media_row.name,
                "path": media_row.path,
                "checksum": media_row.checksum,
                "size": size,
                "priority": priority,
                "required_by": required_by,
                "action": action,
            }
        )

    status = "ready" if download_count == 0 else "queued"
    return {
        "plan_revision": now.strftime("%Y%m%d%H%M%S%f"),
        "generated_at": now.isoformat(),
        "preload_window_min": SYNC_PRELOAD_WINDOW_MIN,
        "queue_status": status,
        "items": plan_items,
        "summary": {
            "total_items": len(plan_items),
            "download_count": download_count,
            "skip_count": len(plan_items) - download_count,
            "total_bytes": total_bytes,
            "download_bytes": total_download_bytes,
        },
    }


def _upsert_device_sync_state(db: Session, device_id: str) -> DeviceSyncState:
    state = db.query(DeviceSyncState).filter(DeviceSyncState.device_id == device_id).first()
    if state:
        return state
    state = DeviceSyncState(device_id=device_id, queue_status="idle")
    db.add(state)
    db.flush()
    return state


def _persist_device_sync_plan(db: Session, device_id: str, plan: dict) -> dict:
    revision = str(plan.get("plan_revision", "")).strip()
    rows = plan.get("items", []) if isinstance(plan.get("items", []), list) else []
    now = datetime.utcnow()

    db.query(DeviceSyncItem).filter(DeviceSyncItem.device_id == device_id).delete(synchronize_session=False)
    for row in rows:
        media_id = str(row.get("media_id", "")).strip()
        if not media_id:
            continue
        item_status = "skipped" if row.get("action") == "skip" else "queued"
        db.add(
            DeviceSyncItem(
                device_id=device_id,
                plan_revision=revision,
                media_id=media_id,
                priority=str(row.get("priority", "P3")),
                required_by=str(row.get("required_by", "background_required")),
                status=item_status,
            )
        )

    state = _upsert_device_sync_state(db, device_id)
    summary = plan.get("summary", {}) if isinstance(plan.get("summary"), dict) else {}
    state.plan_revision = revision
    state.queue_status = str(plan.get("queue_status", "queued"))
    state.total_bytes = int(summary.get("download_bytes", 0) or 0)
    state.downloaded_bytes = 0
    state.completed_count = int(summary.get("skip_count", 0) or 0)
    state.failed_count = 0
    state.current_media_id = None
    state.eta_sec = None
    state.last_error = None
    state.last_report_at = now
    state.ack_source = None
    state.ack_reason = None
    state.ack_at = None
    db.commit()

    return {
        "queue_status": state.queue_status,
        "completed_count": state.completed_count,
        "failed_count": state.failed_count,
        "downloaded_bytes": state.downloaded_bytes,
        "total_bytes": state.total_bytes,
        "last_report_at": state.last_report_at.isoformat() if state.last_report_at else None,
    }


def _device_sync_status_payload(db: Session, device_id: str) -> dict:
    state = db.query(DeviceSyncState).filter(DeviceSyncState.device_id == device_id).first()
    items = (
        db.query(DeviceSyncItem)
        .filter(DeviceSyncItem.device_id == device_id)
        .all()
    )
    if state is None:
        return {
            "queue_status": "idle",
            "plan_revision": None,
            "progress_percent": 0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "completed_count": 0,
            "failed_count": 0,
            "queued_count": 0,
            "downloading_count": 0,
            "verifying_count": 0,
            "ready": True,
            "items": [],
            "last_report_at": None,
            "ack_source": None,
            "ack_reason": None,
            "ack_at": None,
        }

    queued_count = 0
    downloading_count = 0
    verifying_count = 0
    completed_count = 0
    failed_count = 0
    failed_items: list[dict] = []
    for row in items:
        status = str(row.status or "queued")
        if status == "queued":
            queued_count += 1
        elif status == "downloading":
            downloading_count += 1
        elif status == "verifying":
            verifying_count += 1
        elif status in {"completed", "skipped"}:
            completed_count += 1
        elif status == "failed":
            failed_count += 1
            failed_items.append(
                {
                    "media_id": str(row.media_id),
                    "priority": row.priority,
                    "required_by": row.required_by,
                    "error": row.error,
                    "retry_count": row.retry_count,
                }
            )

    denominator = int(state.total_bytes or 0)
    progress_percent = 100 if denominator == 0 else min(100, int((int(state.downloaded_bytes or 0) * 100) / denominator))
    ready = state.queue_status == "ready"

    return {
        "queue_status": state.queue_status,
        "plan_revision": state.plan_revision,
        "progress_percent": progress_percent,
        "downloaded_bytes": int(state.downloaded_bytes or 0),
        "total_bytes": denominator,
        "completed_count": completed_count,
        "failed_count": failed_count,
        "queued_count": queued_count,
        "downloading_count": downloading_count,
        "verifying_count": verifying_count,
        "current_media_id": state.current_media_id,
        "eta_sec": state.eta_sec,
        "ready": ready,
        "failed_items": failed_items[:20],
        "last_error": state.last_error,
        "last_report_at": state.last_report_at.isoformat() if state.last_report_at else None,
        "ack_source": state.ack_source,
        "ack_reason": state.ack_reason,
        "ack_at": state.ack_at.isoformat() if state.ack_at else None,
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    }


def _summarize_sync_items(db: Session, device_id: str, plan_revision: str) -> dict:
    rows = (
        db.query(DeviceSyncItem.status, DeviceSyncItem.priority)
        .filter(
            DeviceSyncItem.device_id == device_id,
            DeviceSyncItem.plan_revision == plan_revision,
        )
        .all()
    )
    queued_count = 0
    downloading_count = 0
    verifying_count = 0
    completed_count = 0
    failed_count = 0
    critical_total = 0
    critical_completed = 0
    critical_failed = 0
    critical_blocking = 0
    noncritical_failed = 0

    for status, priority in rows:
        normalized = str(status or "queued").strip().lower()
        lane = str(priority or "P3").strip().upper()
        is_critical = lane in {"P0", "P1"}
        if is_critical:
            critical_total += 1

        if normalized in {"completed", "skipped"}:
            completed_count += 1
            if is_critical:
                critical_completed += 1
        elif normalized == "failed":
            failed_count += 1
            if is_critical:
                critical_failed += 1
            else:
                noncritical_failed += 1
        elif normalized == "downloading":
            downloading_count += 1
            if is_critical:
                critical_blocking += 1
        elif normalized == "verifying":
            verifying_count += 1
            if is_critical:
                critical_blocking += 1
        else:
            queued_count += 1
            if is_critical:
                critical_blocking += 1

    return {
        "total_items": len(rows),
        "queued_count": queued_count,
        "downloading_count": downloading_count,
        "verifying_count": verifying_count,
        "completed_count": completed_count,
        "failed_count": failed_count,
        "critical_total": critical_total,
        "critical_completed": critical_completed,
        "critical_failed": critical_failed,
        "critical_blocking": critical_blocking,
        "noncritical_failed": noncritical_failed,
    }


@router.post("/{device_id}/media-cache-report")
def media_cache_report(
    device_id: str,
    request: Request,
    media_ids: list[str] = Body(default=[]),
    account_id: str | None = None,
    db: Session = Depends(get_db),
):
    device = _find_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    _enforce_device_owner(device, _resolve_account_id(request, account_id))

    normalized = _normalize_media_id_set(media_ids)
    device.cached_media_ids = ",".join(normalized)
    device.media_cache_updated_at = datetime.utcnow()
    db.commit()

    return {
        "ok": True,
        "device_id": str(device.id),
        "cached_count": len(normalized),
        "updated_at": device.media_cache_updated_at.isoformat() if device.media_cache_updated_at else None,
    }


@router.get("/{device_id}/media-cache-status")
def media_cache_status(
    device_id: str,
    request: Request,
    account_id: str | None = None,
    db: Session = Depends(get_db),
):
    device = _find_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    _enforce_device_owner(device, _resolve_account_id(request, account_id))
    return {"device_id": str(device.id), **_compute_media_cache_status(db, device)}


@router.post("/{device_id}/request-media-download")
def request_media_download(
    device_id: str,
    request: Request,
    account_id: str | None = None,
    db: Session = Depends(get_db),
):
    device = _find_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    _enforce_device_owner(device, _resolve_account_id(request, account_id))

    return {
        "ok": True,
        "device_id": str(device.id),
        "accepted_at": datetime.utcnow().isoformat(),
        "hint": "Permintaan diterima. Player akan sinkron saat menerima event config_changed/polling berikutnya.",
    }


@router.get("/{device_id}/sync-plan")
def device_sync_plan(
    device_id: str,
    request: Request,
    account_id: str | None = None,
    db: Session = Depends(get_db),
):
    device = _find_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    _enforce_device_owner(device, _resolve_account_id(request, account_id))

    plan = _build_device_sync_plan(db, device)
    persisted = _persist_device_sync_plan(db, str(device.id), plan)
    return {
        "device_id": str(device.id),
        **plan,
        "state": persisted,
    }


@router.post("/{device_id}/sync-progress")
def device_sync_progress(
    device_id: str,
    request: Request,
    plan_revision: str | None = None,
    queue_status: str | None = None,
    downloaded_bytes: int | None = None,
    total_bytes: int | None = None,
    current_media_id: str | None = None,
    eta_sec: int | None = None,
    completed_ids: list[str] = Body(default=[]),
    failed_items: list[dict] = Body(default=[]),
    account_id: str | None = None,
    db: Session = Depends(get_db),
):
    device = _find_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    _enforce_device_owner(device, _resolve_account_id(request, account_id))

    state = _upsert_device_sync_state(db, str(device.id))
    if plan_revision:
        state.plan_revision = str(plan_revision).strip()
    if queue_status:
        state.queue_status = str(queue_status).strip().lower()
    if downloaded_bytes is not None and downloaded_bytes >= 0:
        state.downloaded_bytes = int(downloaded_bytes)
    if total_bytes is not None and total_bytes >= 0:
        state.total_bytes = int(total_bytes)
    if eta_sec is not None:
        state.eta_sec = int(eta_sec) if eta_sec >= 0 else None
    if current_media_id is not None:
        state.current_media_id = str(current_media_id).strip() or None
    state.last_report_at = datetime.utcnow()

    revision = str(state.plan_revision or "").strip()
    if revision:
        completion_set = {str(item).strip() for item in (completed_ids or []) if str(item).strip()}
        if completion_set:
            rows = (
                db.query(DeviceSyncItem)
                .filter(
                    DeviceSyncItem.device_id == str(device.id),
                    DeviceSyncItem.plan_revision == revision,
                    DeviceSyncItem.media_id.in_(list(completion_set)),
                )
                .all()
            )
            for row in rows:
                row.status = "completed"
                row.error = None

        for row in failed_items or []:
            if not isinstance(row, dict):
                continue
            media_id = str(row.get("media_id", "")).strip()
            if not media_id:
                continue
            sync_item = (
                db.query(DeviceSyncItem)
                .filter(
                    DeviceSyncItem.device_id == str(device.id),
                    DeviceSyncItem.plan_revision == revision,
                    DeviceSyncItem.media_id == media_id,
                )
                .first()
            )
            if not sync_item:
                continue
            sync_item.status = "failed"
            sync_item.error = str(row.get("error", "")).strip() or "download_failed"
            retry_value = row.get("retry_count")
            if isinstance(retry_value, int) and retry_value >= 0:
                sync_item.retry_count = retry_value

        summary = _summarize_sync_items(db, str(device.id), revision)
        state.completed_count = int(summary["completed_count"])
        state.failed_count = int(summary["failed_count"])
        blocking_count = (
            int(summary["queued_count"])
            + int(summary["downloading_count"])
            + int(summary["verifying_count"])
        )
        if blocking_count == 0:
            if int(summary["failed_count"]) == 0:
                state.queue_status = "ready"
            elif int(summary["critical_failed"]) == 0:
                state.queue_status = "ready_with_warnings"
            else:
                state.queue_status = "failed"

    db.commit()
    return {
        "ok": True,
        "device_id": str(device.id),
        **_device_sync_status_payload(db, str(device.id)),
    }


@router.get("/{device_id}/sync-status")
def device_sync_status(
    device_id: str,
    request: Request,
    account_id: str | None = None,
    db: Session = Depends(get_db),
):
    device = _find_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    _enforce_device_owner(device, _resolve_account_id(request, account_id))
    return {
        "device_id": str(device.id),
        **_device_sync_status_payload(db, str(device.id)),
    }


@router.post("/{device_id}/sync-ack")
def device_sync_ack(
    device_id: str,
    request: Request,
    plan_revision: str | None = None,
    queue_status: str | None = "ready",
    ack_source: str | None = "device",
    ack_reason: str | None = None,
    account_id: str | None = None,
    db: Session = Depends(get_db),
):
    device = _find_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    _enforce_device_owner(device, _resolve_account_id(request, account_id))

    state = _upsert_device_sync_state(db, str(device.id))
    if plan_revision:
        state.plan_revision = str(plan_revision).strip()
    revision = str(state.plan_revision or "").strip()
    if not revision:
        raise HTTPException(status_code=400, detail="sync-ack requires plan_revision")

    summary = _summarize_sync_items(db, str(device.id), revision)
    state.completed_count = int(summary["completed_count"])
    state.failed_count = int(summary["failed_count"])
    cache_status = _compute_media_cache_status(db, device)
    blocking_count = (
        int(summary["queued_count"])
        + int(summary["downloading_count"])
        + int(summary["verifying_count"])
    )
    critical_complete = int(summary["critical_completed"]) >= int(summary["critical_total"])
    critical_clean = int(summary["critical_failed"]) == 0 and int(summary["critical_blocking"]) == 0
    queue_empty = blocking_count == 0
    no_failures = int(summary["failed_count"]) == 0
    cache_ready = cache_status.get("ready") is True

    can_ready = no_failures and queue_empty and critical_complete and critical_clean and cache_ready
    can_ready_with_warnings = (
        queue_empty
        and critical_complete
        and critical_clean
        and int(summary["noncritical_failed"]) > 0
    )

    state.ack_source = (ack_source or "").strip() or "device"
    state.ack_reason = (ack_reason or "").strip() or None
    state.ack_at = datetime.utcnow()
    state.last_report_at = state.ack_at

    if can_ready:
        state.queue_status = "ready"
    elif can_ready_with_warnings:
        state.queue_status = "ready_with_warnings"
    else:
        state.queue_status = "failed"
        state.last_error = "sync_ack_rejected_guard_failed"
        db.commit()
        raise HTTPException(
            status_code=409,
            detail={
                "message": "sync-ack rejected by guard",
                "required": {
                    "failed_count": 0,
                    "queued_downloading_verifying": 0,
                    "critical_p0_p1_completed": True,
                    "media_cache_ready": True,
                },
                "actual": {
                    "failed_count": int(summary["failed_count"]),
                    "queued_count": int(summary["queued_count"]),
                    "downloading_count": int(summary["downloading_count"]),
                    "verifying_count": int(summary["verifying_count"]),
                    "critical_total": int(summary["critical_total"]),
                    "critical_completed": int(summary["critical_completed"]),
                    "critical_failed": int(summary["critical_failed"]),
                    "noncritical_failed": int(summary["noncritical_failed"]),
                    "media_cache_ready": cache_ready,
                    "media_cache_missing_count": int(cache_status.get("missing_count", 0) or 0),
                },
            },
        )

    state.current_media_id = None
    state.eta_sec = 0
    db.commit()
    return {
        "ok": True,
        "device_id": str(device.id),
        "ack_source": state.ack_source,
        "ack_reason": state.ack_reason,
        "ack_at": state.ack_at.isoformat() if state.ack_at else None,
        **_device_sync_status_payload(db, str(device.id)),
    }


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
    main_screen = Screen(
        device_id=device.id,
        name="Main",
        transition_duration_sec=DEFAULT_TRANSITION_DURATION_SEC,
    )
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
    return_data = []
    for d in devices:
        media_cache_status = _compute_media_cache_status(db, d)
        return_data.append(
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
                "media_download_ready": media_cache_status["ready"],
                "media_download_status": media_cache_status["download_status"],
                "media_download_status_label": media_cache_status["download_status_label"],
                "media_download_status_color": media_cache_status["download_status_color"],
                "media_required_count": media_cache_status["required_count"],
                "media_cached_count": media_cache_status["cached_count"],
                "media_missing_count": media_cache_status["missing_count"],
                "media_cache_updated_at": media_cache_status["cache_updated_at"],
            }
        )
    return return_data

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

    db.query(FlashSaleConfig).filter(FlashSaleConfig.device_id == device.id).delete(synchronize_session=False)
    db.query(DeviceSyncItem).filter(DeviceSyncItem.device_id == device.id).delete(synchronize_session=False)
    db.query(DeviceSyncState).filter(DeviceSyncState.device_id == device.id).delete(synchronize_session=False)
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

    # Allow central/shared playlists to be referenced by active_playlist_id or schedule.playlist_id
    # even when the playlist belongs to a different screen/device.
    known_playlist_ids = {str(pl.id) for pl in playlists}
    referenced_playlist_ids: set[str] = set()
    for screen in screens:
        active_id = str(screen.active_playlist_id or "").strip()
        if active_id:
            referenced_playlist_ids.add(active_id)
    for sc in schedules:
        pid = str(sc.playlist_id or "").strip()
        if pid:
            referenced_playlist_ids.add(pid)

    missing_referenced_ids = [
        pid for pid in referenced_playlist_ids if pid not in known_playlist_ids
    ]
    if missing_referenced_ids:
        referenced_playlists = db.query(Playlist).filter(Playlist.id.in_(missing_referenced_ids)).all()
        playlists.extend(referenced_playlists)
        for pl in referenced_playlists:
            items = db.query(PlaylistItem).filter(PlaylistItem.playlist_id == pl.id).all()
            playlist_items.extend(items)
            for it in items:
                media_ids.add(it.media_id)

    media = []
    flash_sale_runtime = None
    flash_sale_config = db.query(FlashSaleConfig).filter(FlashSaleConfig.device_id == device.id).first()
    flash_sale_runtime = _resolve_flash_sale_runtime(flash_sale_config, datetime.utcnow())
    if flash_sale_runtime and flash_sale_runtime.get("products_json"):
        try:
            rows = json.loads(flash_sale_runtime["products_json"])
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    media_id = str(row.get("media_id", "")).strip()
                    if media_id:
                        media_ids.add(media_id)
        except Exception:
            pass

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
                "transition_duration_sec": (
                    s.transition_duration_sec
                    if s.transition_duration_sec is not None
                    else DEFAULT_TRANSITION_DURATION_SEC
                ),
                "schedules": [
                    {
                        "day_of_week": sc.day_of_week,
                        "start_time": str(sc.start_time),
                        "end_time": str(sc.end_time),
                        "playlist_id": str(sc.playlist_id),
                        "note": sc.note,
                        "countdown_sec": sc.countdown_sec,
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
                "is_flash_sale": bool(pl.is_flash_sale),
                "flash_note": pl.flash_note,
                "flash_countdown_sec": pl.flash_countdown_sec,
                "flash_items_json": pl.flash_items_json,
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
                "size": m.size,
            }
            for m in media
        ],
        "flash_sale": flash_sale_runtime,
    }
