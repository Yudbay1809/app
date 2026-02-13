# Changelog

All notable changes to this project are documented in this file.

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
