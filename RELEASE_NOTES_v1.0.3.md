# Release Notes v1.0.3

## Date
2026-02-17

## Summary
Patch release to add per-device media cache observability for CMS verification.

## What's New
- New endpoint: `POST /devices/{device_id}/media-cache-report`
  - Used by player clients to report downloaded/cached media IDs.
- New endpoint: `GET /devices/{device_id}/media-cache-status`
  - Returns readiness and missing media list for each device.

## Backend Schema Update
- Device table now includes:
  - `cached_media_ids` (TEXT)
  - `media_cache_updated_at` (DATETIME)
- SQLite runtime schema patch auto-adds these columns when missing.

## Operational Impact
- CMS can now validate whether target device media has been fully downloaded before playback/switch decisions.
- Existing endpoints and playback flow remain backward compatible.

