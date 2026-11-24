# Export data from an already-installed v0.1.2 Android Debug APK

The published v0.1.2 APK uses the debuggable package ID
com.dsh017.android.debug. It predates the in-app SAF export action. A later
Debug APK cannot be assumed to update that installation because GitHub-hosted
Debug signing identities are not guaranteed to persist between workflow runs.

This host-side ADB helper provides a non-destructive fallback for that exact
legacy package. It reads the app-private files through Android's run-as
facility and then calls the repository's existing scripts/data_backup.py to
produce the normal version-1 DSH-017 archive.

## Requirements

- A computer with Android SDK Platform-Tools (adb) and Python 3.10 or newer.
- USB debugging enabled and this computer authorized on the device.
- The old com.dsh017.android.debug APK still installed.
- The old APK must be debuggable. The published v0.1.2 tag uses the Gradle
  Debug variant; run-as deliberately fails closed for non-debuggable apps.
- The old app must be stopped before copying its SQLite database. Exit it
  normally, then confirm Android has stopped the process. The script checks
  the process state and refuses to copy while it is running.

## Export

From the repository root:

    adb devices -l
    python3 scripts/export_legacy_android_data.py --output-dir ./dsh017-migration

If more than one authorized device is connected, specify its serial:

    python3 scripts/export_legacy_android_data.py \
      --serial DEVICE_SERIAL \
      --output-dir ./dsh017-migration

If adb is not on PATH, pass its executable path with --adb.

The script:

1. Confirms exactly one selected, authorized device and verifies the legacy
   package is installed and accessible through run-as.
2. Refuses to continue while the old app process is running. It does not issue
   am force-stop or otherwise change the device's process state.
3. Streams only bili_data.db, its SQLite WAL/SHM/journal sidecars,
   providers.json, and presets/*.txt into a private temporary directory.
4. Rejects symlinks, hard links, unexpected files, duplicate names, path
   traversal, oversized members and incomplete data.
5. Calls scripts/data_backup.py backup to create the standard version-1
   archive. That tool takes a transaction-consistent SQLite snapshot, checks
   PRAGMA integrity_check, validates provider metadata and presets, and
   writes the resulting archive with owner-only permissions on POSIX systems.

The ADB operations are read-only: the helper does not install, uninstall,
force-stop, push, delete or rename anything on the device. It does not export
provider_secrets.json, auth_token, admin_token, API keys or Android
Keystore entries. Provider metadata is preserved; credentials must be entered
again in the new Release app.

The archive contains conversations and Workspace data and is private user
data. Keep it in a protected local directory and do not upload it to Issues,
pull requests or chat.

## Import and verification

Keep the old Debug app installed. Install the persistent-signed Release app
only after the archive has been created. On the Release app's first-run
migration prompt, select the generated .tar.gz archive. The Release importer
must validate and restore it before backend services initialize.

Verify chats, Workspace projects/files/versions/rules, favorites, watch
progress, search history, presets and Provider metadata in the new app. Re-enter
Provider credentials and recreate access/admin tokens. Do not uninstall the
old Debug app until the new installation has been checked.

The helper only solves the legacy export side. It does not prove SAF import,
Android 10 first-run ordering, signer continuity, or a real-device migration.
Those acceptance steps remain open under Issue #46.

## Tests

    python3 -m unittest discover -s tests -p 'test_android_legacy_export.py' -v

The tests use a synthetic SQLite database and a fake ADB transport. They do not
require a connected device and do not access real application data.
