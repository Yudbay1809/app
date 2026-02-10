# GitHub Release Template (v1.0.0)

## Title
`v1.0.0 - Signage Flow Stabilization`

## Description
Stabilization release for digital signage backend and operational workflow.

### What’s New
- Added endpoint `GET /playlists/{playlist_id}/items`.
- Improved playlist/device config compatibility for desktop/mobile clients.
- Included playlist `name` in device config payload.
- Cleaned repository from generated artifacts (`__pycache__`, `.pyc`).
- Upgraded documentation and production notes.

### Highlights for Operations
- Better consistency for add/delete/reorder media in playlist workflows.
- Improved reliability for downstream client rendering and playlist labeling.

### Artifacts to Upload
- Android APK: `E:\APP\android\signage_android_player-release.apk`
- Desktop package folder: `E:\APP\desktop\`

### API Notes
- New endpoint: `GET /playlists/{playlist_id}/items`

### Upgrade Notes
- No destructive DB migration required.
- Existing clients remain compatible.

### Verification
- Python `py_compile` checks passed on updated backend modules.
- Flutter analyze checks passed on updated desktop/mobile modules.
