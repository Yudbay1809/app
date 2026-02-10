# Release Checklist

## Git
- [ ] `git push origin main`
- [ ] `git push origin v1.0.0`

## GitHub Release
- [ ] Open: `https://github.com/Yudbay1809/app/releases/new`
- [ ] Tag: `v1.0.0`
- [ ] Title: `v1.0.0 - Signage Flow Stabilization`
- [ ] Paste body from `GITHUB_RELEASE_TEMPLATE.md`

## Upload Artifacts
- [ ] Upload `E:\APP\android\signage_android_player-release.apk`
- [ ] Zip and upload desktop package from `E:\APP\desktop\`

## Post Release
- [ ] Verify API health: `/healthz`
- [ ] Verify device config fetch on one Android player
- [ ] Verify desktop can read/update playlists normally
