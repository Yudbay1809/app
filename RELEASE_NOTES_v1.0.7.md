# RELEASE NOTES v1.0.7

Tanggal: 2026-03-22

## Ringkasan
Patch ini menambah konfigurasi pool DB untuk mencegah timeout koneksi saat beban tinggi.

## Perubahan Utama
- Pool size, overflow, dan timeout DB sekarang bisa diatur via env:
  - `SIGNAGE_DB_POOL_SIZE` (default 15)
  - `SIGNAGE_DB_MAX_OVERFLOW` (default 30)
  - `SIGNAGE_DB_POOL_TIMEOUT` (default 60)
- `pool_pre_ping` diaktifkan agar koneksi idle cepat terdeteksi.

## Dampak
- Mengurangi error `QueuePool limit reached` saat lonjakan request.
- Server lebih stabil, tidak perlu restart manual sesering sebelumnya.
