# RELEASE NOTES v1.0.5

Tanggal: 2026-02-23

## Ringkasan
Patch ini menambahkan Smart Media Sync untuk orkestrasi download media per-device berbasis prioritas dan progress queue.

## Perubahan Utama
- Endpoint baru Smart Sync di `devices` API:
  - `GET /devices/{device_id}/sync-plan`
  - `POST /devices/{device_id}/sync-progress`
  - `GET /devices/{device_id}/sync-status`
  - `POST /devices/{device_id}/sync-ack`
- Prioritas plan media:
  - `P0` flash sale aktif
  - `P1` playlist aktif
  - `P2` jadwal terdekat (preload window)
  - `P3` background required
- Penyimpanan state sinkronisasi per-device:
  - model `device_sync_state`
  - model `device_sync_item`
- Cleanup data sync ikut dijalankan saat device dihapus.
- README diperbarui untuk dokumentasi endpoint Smart Sync.

## Dampak
- CMS/mobile sekarang bisa membaca status queue sinkronisasi per-device.
- Sinkronisasi media lebih terarah, tidak perlu unduh semua media sekaligus.
