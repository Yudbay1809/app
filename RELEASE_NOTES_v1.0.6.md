# RELEASE NOTES v1.0.6

Tanggal: 2026-03-22

## Ringkasan
Patch ini menambahkan auto-compress saat upload media agar konten lebih ramah untuk device RAM 2GB.

## Perubahan Utama
- Image upload otomatis resize + kompres JPEG (default 1920x1080, quality 82).
- Video upload otomatis transcode bila besar (memerlukan ffmpeg di PATH).
- Ukuran akhir + checksum media diperbarui setelah optimisasi.

## Dampak
- File besar lebih ringan, playback lebih stabil.
- Operator tidak perlu kompres manual sebelum upload.
