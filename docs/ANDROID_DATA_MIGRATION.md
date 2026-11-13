# Android Debug-to-Release data migration

## What the migration flow does

The Android Debug variant exposes **Export migration package** after its local services are ready. It creates the same version-1 archive as `scripts/data_backup.py` and sends it to the Android Storage Access Framework (SAF), so the user chooses Downloads or another document provider.

The Release variant checks for a fresh, empty app-private data directory before starting Python services. On first launch it offers **Import backup** or **Start fresh**. Import copies the selected document to private cache, validates the archive and SQLite database, then restores into the app-private `files/dsh017` and `files/dsh017/presets` layout before calling `start_services`. A failed or cancelled import does not start services or overwrite a non-empty destination.

The shared archive validator checks the versioned manifest, exact archive member set, safe paths, duplicate names, member and total size bounds, SHA-256 hashes, SQLite integrity, provider metadata JSON and UTF-8 preset files. Android also caps the compressed SAF import at 520 MiB before writing it into private cache, matching the 512 MiB uncompressed payload ceiling with room for archive headers. The restore helper permits the one Android-specific nested layout (`data/presets`) only when the data directory is otherwise empty and the preset directory is empty. Partial file writes are removed on failure.

## User steps

1. Keep the old Debug app installed and open it.
2. Wait until the embedded services are ready, then choose **Export migration package**.
3. Save the `.tar.gz` archive to Downloads or another user-selected SAF location.
4. Install and open the persistent-signed Release app.
5. On its first-run migration prompt, choose **Import backup** and select the archive.
6. Wait for validation and import to finish, then verify chats, Workspace projects/files/versions/rules, presets, favorites, watch progress, search history and Provider metadata.
7. Re-enter API keys and recreate access/admin tokens. Device-bound Android Keystore keys and secrets are deliberately excluded.
8. Keep the old Debug app and its data until the new app has been checked. Only then may the old app be uninstalled.

The archive contains personal conversations and Workspace files. Store it privately and delete it when no longer needed.

## Important compatibility limitation

The already-published `v0.1.2` Debug APK predates this SAF export button. Updating an installed Android package requires the same signing certificate. CI Debug builds use the runner's debug signing identity, which is not guaranteed to persist between runs. Therefore, the new export UI is not yet proven installable as an in-place update over every existing `v0.1.2` Debug installation.

Do not uninstall the existing Debug app to obtain the new export button: uninstalling removes its private data. Before claiming migration support for existing installations, the project must verify a signing-compatible legacy Debug update path or document and test another safe extraction path. The Release import implementation and automated archive tests do not, by themselves, prove that old installed data can be exported.

## Validation still required

- Python archive tests and both Android ABI build jobs must pass in CI.
- Test SAF create-document/open-document, cancellation and partial I/O behavior on Android.
- Verify first-run import occurs before database/service initialization.
- Verify Release-to-Release upgrades use the same persistent package signer.
- Run the full export/import/record verification on a real Android 10 device before closing Issue #46.
