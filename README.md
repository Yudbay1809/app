# Signage Backend API

Backend FastAPI untuk mengelola media, playlist, schedule, dan device pada sistem digital signage.

## Fitur Utama
- Manajemen media upload/hapus dengan checksum
- Manajemen device + orientasi layar
- Playlist dan schedule per device
- Realtime update via WebSocket (`/ws/updates`)
- Endpoint server discovery (`/server-info`, `/healthz`)
- Pagination media untuk scale besar (`/media/page`)

## Arsitektur Singkat
- `api/` endpoint REST
- `models/` SQLAlchemy model
- `schemas/` validasi request/response
- `services/` storage dan realtime hub
- Database default: SQLite (`signage.db`)

## Endpoint Penting
- `GET /healthz`
- `GET /server-info`
- `GET /media/page?offset=0&limit=120&q=&type=all`
- `POST /devices/register`
- `GET /devices/{device_id}/config`
- `WS /ws/updates`

## Quick Start
```bash
cd "D:\APP Video Promosi"
.\app\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Catatan Produksi
- Gunakan PostgreSQL saat jumlah media/device bertambah besar
- Aktifkan HTTPS reverse proxy (Nginx/Caddy) untuk deployment publik
- Simpan `SIGNAGE_API_KEY` untuk proteksi API

