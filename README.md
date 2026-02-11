# Digital Signage Backend API

[![Backend CI](https://github.com/Yudbay1809/app/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/Yudbay1809/app/actions/workflows/backend-ci.yml)
![Python](https://img.shields.io/badge/python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.128-009688)
![License](https://img.shields.io/badge/license-MIT-informational)

FastAPI backend for digital signage operations: media catalog, playlists, schedules, device registration, Flash Sale campaign, and realtime config updates.

## Features
- Device provisioning with ownership guard
- Media upload/catalog with checksum and pagination
- Playlist and playlist-item management
- Screen schedule orchestration
- Screen grid + transition duration control (`transition_duration_sec`, range `0..30`)
- Device-level Flash Sale campaign (independent from playlist)
- Realtime update broadcast over WebSocket
- Health and server discovery endpoints

## Stack
- FastAPI
- SQLAlchemy ORM
- SQLite (default; can be replaced with PostgreSQL)
- Uvicorn

## Project Layout
```text
api/         HTTP endpoints
models/      SQLAlchemy models
schemas/     Request/response schemas
services/    Storage + realtime hub
db.py        Database bootstrap and schema helpers
main.py      FastAPI entrypoint
```

## Quick Start
```bash
cd "D:\APP Video Promosi"
.\app\.venv\Scripts\python.exe -m pip install -r .\app\requirements.txt
.\app\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open docs:
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

## Key Endpoints
- `GET /healthz`
- `GET /server-info`
- `POST /devices/register`
- `POST /devices/{device_id}/heartbeat`
- `GET /devices/{device_id}/config`
- `PUT /flash-sale/device/{device_id}/now`
- `PUT /flash-sale/device/{device_id}/schedule`
- `DELETE /flash-sale/device/{device_id}`
- `GET /screens?device_id=<device_id>`
- `PUT /screens/{screen_id}?grid_preset=2x2&transition_duration_sec=2`
- `GET /media/page`
- `WS /ws/updates`

## Screen Transition Duration
- Field: `transition_duration_sec` (seconds)
- Allowed range: `0..30`
- Default: `1`
- Available in:
  - `GET /screens`
  - `POST /screens`
  - `PUT /screens/{screen_id}`
  - `GET /devices/{device_id}/config` inside each screen object

## Flash Sale Campaign
- Flash Sale is configured per-device and decoupled from playlist.
- Campaign payload supports:
  - `note` (running text)
  - `countdown_sec`
  - `products_json` (must include `media_id` per product)
  - optional schedule (`schedule_days`, `start_time`, `end_time`)
- Runtime status is exposed in `GET /devices/{device_id}/config` under top-level `flash_sale`.

## VS Code Setup
- Open folder: `D:\APP Video Promosi\app`
- Interpreter: `D:\APP Video Promosi\app\.venv\Scripts\python.exe`
- If imports fail, reinstall:
```bash
cd "D:\APP Video Promosi\app"
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Security
Report vulnerabilities privately following `SECURITY.md`.

## Contributing
Contribution guidelines are in `CONTRIBUTING.md`.

## License
MIT License. See `LICENSE`.
