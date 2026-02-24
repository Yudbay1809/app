import os
import socket
import asyncio
import logging
import subprocess
import re
import time
from datetime import datetime, timezone
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.db import Base, engine, ensure_sqlite_schema
from app.db import SessionLocal
from app.api import media, device, playlist, schedule, screen, flash_sale
from app.models.device import Device
from app.services.storage import ensure_storage
from app.services.realtime import hub

Base.metadata.create_all(bind=engine)
ensure_sqlite_schema()
ensure_storage()

API_KEY = os.getenv("SIGNAGE_API_KEY", "").strip()
SERVER_PORT = int(os.getenv("SIGNAGE_SERVER_PORT", "8000"))
DEVICE_OFFLINE_AFTER_SEC = int(os.getenv("SIGNAGE_DEVICE_OFFLINE_AFTER_SEC", "70"))
DEVICE_STATUS_SWEEP_SEC = int(os.getenv("SIGNAGE_DEVICE_STATUS_SWEEP_SEC", "5"))
QUIET_ACCESS_LOG = os.getenv("SIGNAGE_QUIET_ACCESS_LOG", "1").strip().lower() in {"1", "true", "yes", "on"}
QUIET_WEBSOCKET_LOG = os.getenv("SIGNAGE_QUIET_WEBSOCKET_LOG", "1").strip().lower() in {"1", "true", "yes", "on"}
_device_status_task: asyncio.Task | None = None
_primary_ip_cache: str | None = None
_primary_ip_cache_at: float = 0.0
PRIMARY_IP_CACHE_TTL_SEC = int(os.getenv("SIGNAGE_PRIMARY_IP_CACHE_TTL_SEC", "15"))

if QUIET_ACCESS_LOG:
    # Keep warning/error lines, suppress normal access noise (200/201 etc).
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

if QUIET_WEBSOCKET_LOG:
    # Intermittent network drop (e.g. WinError 121) can emit noisy stack traces from
    # the websocket transport layer even though reconnect logic is already in place.
    logging.getLogger("websockets").setLevel(logging.CRITICAL)
    logging.getLogger("uvicorn.protocols.websockets").setLevel(logging.CRITICAL)


def _local_ipv4_addresses() -> list[str]:
    candidates: list[str] = []

    def add_candidate(ip: str) -> None:
        if ip and ip != "127.0.0.1" and ip not in candidates:
            candidates.append(ip)

    try:
        host = socket.gethostname()
        for entry in socket.getaddrinfo(host, None, family=socket.AF_INET):
            add_candidate(entry[4][0])
    except Exception:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            add_candidate(sock.getsockname()[0])
    except Exception:
        pass

    return candidates


def _is_private_ip(ip: str) -> bool:
    return ip.startswith("10.") or ip.startswith("192.168.") or ip.startswith("172.")


def _ip_from_default_gateway_adapter() -> str | None:
    # On Windows, pick the IPv4 from the adapter section that has Default Gateway.
    try:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
        completed = subprocess.run(
            ["ipconfig"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=3,
            check=False,
            startupinfo=startupinfo,
            creationflags=creation_flags,
        )
        output = completed.stdout or ""
        if not output:
            return None
    except Exception:
        return None

    blocks = re.split(r"\r?\n\r?\n", output)
    for block in blocks:
        ipv4_match = re.search(r"IPv4 Address[^\n:]*:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", block)
        gw_match = re.search(r"Default Gateway[^\n:]*:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", block)
        if not ipv4_match or not gw_match:
            continue
        ip = ipv4_match.group(1)
        if _is_private_ip(ip):
            return ip
    return None


def _primary_ip() -> str:
    gw_ip = _ip_from_default_gateway_adapter()
    if gw_ip:
        return gw_ip

    ips = _local_ipv4_addresses()
    for ip in ips:
        if _is_private_ip(ip):
            return ip
    if ips:
        return ips[0]
    return "127.0.0.1"


def _primary_ip_cached() -> str:
    global _primary_ip_cache, _primary_ip_cache_at
    now = time.time()
    if _primary_ip_cache and (now - _primary_ip_cache_at) < PRIMARY_IP_CACHE_TTL_SEC:
        return _primary_ip_cache
    _primary_ip_cache = _primary_ip()
    _primary_ip_cache_at = now
    return _primary_ip_cache


def _derive_device_status(last_seen: datetime | None, now_utc: datetime) -> str:
    if last_seen is None:
        return "offline"
    age = (now_utc - last_seen).total_seconds()
    return "online" if age <= DEVICE_OFFLINE_AFTER_SEC else "offline"


async def _device_status_watcher() -> None:
    while True:
        await asyncio.sleep(DEVICE_STATUS_SWEEP_SEC)
        changed_payload: list[dict[str, str | None]] = []
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            devices = db.query(Device).all()
            for item in devices:
                next_status = _derive_device_status(item.last_seen, now)
                if item.status != next_status:
                    item.status = next_status
                    changed_payload.append(
                        {
                            "device_id": str(item.id),
                            "status": next_status,
                            "last_seen": item.last_seen.isoformat() if item.last_seen else None,
                        }
                    )
            if changed_payload:
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

        if changed_payload:
            await hub.publish(
                "device_status_changed",
                {
                    "changes": changed_payload,
                    "offline_after_sec": DEVICE_OFFLINE_AFTER_SEC,
                },
            )

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "ok": True,
        "service": "signage-api",
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "docs": "/docs",
    }

@app.get("/healthz")
def healthz():
    return {"ok": True, "server_ip": _primary_ip_cached(), "server_port": SERVER_PORT}


@app.get("/server-info")
def server_info():
    ip = _primary_ip_cached()
    return {
        "ok": True,
        "server_ip": ip,
        "server_port": SERVER_PORT,
        "base_url": f"http://{ip}:{SERVER_PORT}",
        "ips": _local_ipv4_addresses(),
        "realtime_ws": f"ws://{ip}:{SERVER_PORT}/ws/updates",
        "revision": hub.revision,
    }


@app.websocket("/ws/updates")
async def ws_updates(websocket: WebSocket):
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(websocket)
    except Exception:
        await hub.disconnect(websocket)


@app.on_event("startup")
async def startup_events() -> None:
    global _device_status_task
    if _device_status_task is None or _device_status_task.done():
        _device_status_task = asyncio.create_task(_device_status_watcher())


@app.on_event("shutdown")
async def shutdown_events() -> None:
    global _device_status_task
    if _device_status_task is not None:
        _device_status_task.cancel()
        try:
            await _device_status_task
        except asyncio.CancelledError:
            pass
        _device_status_task = None

@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if not API_KEY:
        return await call_next(request)
    path = request.url.path
    if path.startswith("/docs") or path.startswith("/openapi.json") or path.startswith("/redoc") or path.startswith("/storage"):
        return await call_next(request)
    if request.headers.get("X-API-Key") != API_KEY:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


@app.middleware("http")
async def realtime_mutation_middleware(request: Request, call_next):
    response = await call_next(request)
    method = request.method.upper()
    path = request.url.path
    if response.status_code < 400 and method in {"POST", "PUT", "DELETE"}:
        watched_prefixes = ("/playlists", "/schedules", "/screens", "/devices", "/media", "/flash-sale")
        if path.startswith(watched_prefixes):
            await hub.publish(
                "config_changed",
                {
                    "path": path,
                    "method": method,
                },
            )
    return response

app.include_router(media.router)
app.include_router(device.router)
app.include_router(playlist.router)
app.include_router(schedule.router)
app.include_router(screen.router)
app.include_router(flash_sale.router)

app.mount("/storage", StaticFiles(directory="storage"), name="storage")
