# Digital Signage Backend API

[![Backend CI](https://github.com/Yudbay1809/app/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/Yudbay1809/app/actions/workflows/backend-ci.yml)
![Python](https://img.shields.io/badge/python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.128-009688)
![License](https://img.shields.io/badge/license-MIT-informational)

FastAPI backend for digital signage operations: media catalog, playlists, schedules, device registration, Flash Sale campaign, and realtime config updates.

## Final Release Notes
- Media upload path is normalized to URL-safe format (`/storage/media/<file>`), so clients no longer receive Windows backslash paths.
- Server IP selection on Windows prioritizes adapter with Default Gateway to improve `GET /healthz` and `GET /server-info` accuracy.
- Validated with end-to-end API + websocket smoke tests before release.

## Latest Updates (2026-02-14)
- Upload validation hardened:
  - allowed type only `image` or `video`
  - extension whitelist enforced
  - max size guard (env-configurable) to prevent oversized media ingestion
  - empty file upload rejected
- `GET /devices/{id}/config` media payload now includes `size` for client-side playback guard.
- Device config now supports central playlist references: `GET /devices/{id}/config` includes playlists referenced by `active_playlist_id` and schedule even across other screens/devices.
- Playlist media type is now enforced as single-type per playlist (photo-only or video-only). Mixed media insertion is rejected at API level.

## Features
- Device provisioning with ownership guard
- Media upload/catalog with checksum and pagination
- Playlist and playlist-item management
- Screen schedule orchestration
- Screen grid + transition duration control (`transition_duration_sec`, range `0..30`)
- Device-level Flash Sale campaign (independent from playlist)
- Realtime update broadcast over WebSocket
- Health and server discovery endpoints

## Deployment Notes (Current Production Style)
- App process is managed by PM2 (`ecosystem.config.js` / `ecosystem.staging.config.js`).
- SQLite database is file-based (`signage.db`) and is not managed as a separate PM2 process.
- Recommended runtime for current setup: single PM2 instance per environment.

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

Run with PM2:
```bash
cd "D:\APP Video Promosi"
pm2 start ecosystem.config.js
pm2 logs signage-api
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

## Manual Smoke Test Checklist
1. `GET /healthz` returns `200`.
2. Register device and fetch `GET /devices/{device_id}/config`.
3. Upload media and verify `media.path` starts with `/storage/media/`.
4. Publish Flash Sale now and verify config reflects `flash_sale`.
5. Confirm websocket receives `config_changed` after mutation endpoints.

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

## Maintainer
- Yudbay1809

## Security
Report vulnerabilities privately following `SECURITY.md`.

## Contributing
Contribution guidelines are in `CONTRIBUTING.md`.

## License
MIT License. See `LICENSE`.
