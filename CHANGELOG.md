# Changelog

All notable changes to this project are documented in this file.

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
