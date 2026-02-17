# Changelog

All notable changes to this project are documented in this file.

## [1.0.3] - 2026-02-17

### Added
- Added device media cache telemetry endpoint:
  - `POST /devices/{device_id}/media-cache-report`
- Added device media cache status endpoint:
  - `GET /devices/{device_id}/media-cache-status`
- Added device schema fields for cache tracking:
  - `cached_media_ids`
  - `media_cache_updated_at`

### Changed
- `media-cache-status` now computes required media from active/scheduled playlists and Flash Sale products, then returns `ready`, `missing_count`, and `missing_media_ids`.
- Updated README to document new media cache endpoints and payload behavior.

## [1.0.2] - 2026-02-14

### Added
- Added media file size in device config payload (`GET /devices/{device_id}/config` -> `media[].size`) to support client-side media guard.

### Changed
- Hardened media upload validation:
  - only `image`/`video` media type accepted
  - extension whitelist enforced per media type
  - max size guard enforced (env-configurable)
  - empty upload rejected
- Normalized upload flow to reject invalid media early with HTTP 422.

### Ops
- Updated README with latest validation behavior and payload contract notes.

## [1.0.1] - 2026-02-13

### Fixed
- Hardened playlist ID handling in `api/playlist.py` by normalizing incoming IDs (trim + `{uuid}` compatibility) to prevent intermittent `Playlist not found` during `PUT /playlists/{playlist_id}` calls from some clients.

### Verified
- Visual flash-sale runtime test on live device (`Device-0005`) with 60-second activation and reset completed successfully.
- Realtime websocket sync (`/ws/updates`) emits `config_changed` on mutation and was validated live.

## [1.0.0] - 2026-02-10

### Added
- Added playlist item listing endpoint: `GET /playlists/{playlist_id}/items`.
- Added stronger repository hygiene with ignored database backup pattern (`signage.db.bak*`).

### Changed
- Improved playlist management flow consistency for desktop client integration.
- Improved device config payload with playlist `name` to support richer player UI.
- Updated project README with production-oriented structure and deployment checklist.

### Fixed
- Synced playlist add/delete/reorder operations to use direct playlist item source.
- Removed tracked runtime artifacts (`__pycache__`, `.pyc`) from repository.

### Ops
- Prepared release tag `v1.0.0` for GitHub release publishing.
