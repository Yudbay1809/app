# Release Notes v1.0.2 (2026-02-14)

## Summary
Patch release focused on safer media ingestion and stronger client playback contract.

## Added
- `media[].size` now included in `GET /devices/{device_id}/config`.

## Changed
- Media upload validation improved in `/media/upload` and `/media/upload-to-playlist`:
  - allowed media type: `image` or `video`
  - extension whitelist per type
  - max file size limit enforcement (configurable by env vars)
  - empty file rejection

## Compatibility
- Backward compatible for existing clients.
- New `media.size` field is additive and optional for clients.

## Verification
- Python compile check passed (`python -m compileall app`).
- PM2 runtime remains compatible (no migration needed).

