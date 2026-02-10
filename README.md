# Digital Signage Backend API

Backend FastAPI untuk orkestrasi media, playlist, schedule, device, dan realtime update pada sistem digital signage.

## Highlights
- Device provisioning + ownership guard (`/devices/register`, `/devices/{id}`)
- Media management dengan checksum + pagination untuk katalog besar
- Playlist management (create, rename, reorder, add/remove item)
- Scheduling engine per screen (hari + rentang waktu)
- Grid preset dengan validasi orientasi device (portrait/landscape)
- Realtime broadcast perubahan konfigurasi via WebSocket (`/ws/updates`)
- Server discovery endpoint untuk auto base-url pada player (`/server-info`, `/healthz`)

## Tech Stack
- FastAPI
- SQLAlchemy ORM
- SQLite (default development)
- Uvicorn

## Project Structure
- `api/` REST endpoints
- `models/` SQLAlchemy models
- `schemas/` response/request schemas
- `services/` realtime hub + storage helper
- `db.py` bootstrap database + migration ringan
- `main.py` app entrypoint

## Main Endpoints
- `GET /healthz`
- `GET /server-info`
- `POST /devices/register`
- `GET /devices/{device_id}/config`
- `GET /media/page?offset=0&limit=120&q=&type=all`
- `POST /playlists/{playlist_id}/items`
- `GET /playlists/{playlist_id}/items`
- `PUT /playlists/items/{item_id}`
- `DELETE /playlists/items/{item_id}`
- `WS /ws/updates`

## Local Run
```bash
cd "D:\APP Video Promosi"
.\app\.venv\Scripts\python.exe -m pip install -r .\app\requirements.txt
.\app\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## VS Code Interpreter (Important)
- Open folder: `D:\APP Video Promosi\app`
- Select Python interpreter: `D:\APP Video Promosi\app\.venv\Scripts\python.exe`
- If import error remains (for example `from sqlalchemy.orm import Session`), run:

```bash
cd "D:\APP Video Promosi\app"
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Production Checklist
- Ganti SQLite ke PostgreSQL untuk skala besar
- Jalankan di balik reverse proxy (Nginx/Caddy)
- Aktifkan HTTPS/TLS pada public deployment
- Set `SIGNAGE_API_KEY` untuk proteksi API
- Batasi firewall hanya port yang dibutuhkan (contoh 8000 private LAN)

## Notes
- Repo ini fokus backend API; desktop/mobile player berada pada repository/folder terpisah.
- Untuk sinkronisasi real-time stabil, pastikan dependensi websocket (`websockets`/`uvicorn[standard]`) terpasang.
