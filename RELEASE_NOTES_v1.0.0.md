# Release Notes v1.0.0

## Summary
This release stabilizes the core signage workflow across media, playlist, schedule, and device configuration, while improving repository quality for production collaboration.

## Highlights
- Playlist item management now has a dedicated read endpoint.
- Device config now includes playlist names for richer downstream UI.
- Repository cleaned from generated cache files.
- Documentation upgraded for onboarding and production setup.

## API Notes
- New: `GET /playlists/{playlist_id}/items`

## Upgrade Notes
- No destructive migration required.
- Existing clients can continue using current endpoints.
- Clients that need playlist display labels can now read `playlists[].name` from device config.

## Verification
- Python syntax checks (`py_compile`) passed for updated backend modules.

## Known Constraints
- Push to GitHub from this execution environment may fail due outbound network restrictions.

---

## Patch Update (2026-02-13)

### Bug Fix
- Fixed intermittent failure on `PUT /playlists/{playlist_id}` where certain client-formatted IDs could return `Playlist not found`.
- Backend now normalizes entity IDs (`trim` and `{uuid}` wrapper compatibility) before DB lookup.

### Runtime Validation
- PM2 service health: online and stable.
- Visual flash-sale validation (60s ON -> OFF) succeeded on live online device.
- WebSocket realtime update stream (`/ws/updates`) confirmed to publish `config_changed` on config mutations.
