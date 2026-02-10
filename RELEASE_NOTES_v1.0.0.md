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
