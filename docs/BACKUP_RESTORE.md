# DSH-017 isolated data backup and restore

This procedure creates a local archive for a DSH-017 instance. It uses SQLite's online backup API, validates the database, and restores only into new or empty directories. Never test restoration over the live data directory.

## What is included

- A transaction-consistent SQLite snapshot: chats, Workspace projects/files/history/rules, Bilibili favorites, watch progress, and search history.
- User preset files with the .txt extension from the configured preset directory.
- Provider metadata (providers.json) without provider credentials.

The archive intentionally excludes provider_secrets.json, auth_token, admin_token, environment variables, and Android Keystore entries. Re-enter provider API keys and create new remote-access tokens after recovery. Android Keystore values are device-bound and are not exported by this tool. Treat the archive as private user data even though API keys are excluded: chats, Workspace files, and presets may contain sensitive material.

## Paths and environment variables

| Value | Resolution |
|---|---|
| Data directory | DSH017_DATA_DIR, otherwise repository data/ |
| SQLite database | DSH017_DB_PATH, otherwise bili_data.db inside the data directory |
| Presets | DSH017_PRESET_DIR, otherwise repository presets/ |
| SQLite daily backups | DSH017_BACKUP_DIR, otherwise backup/ inside the data directory |

Use the same DSH017_DATA_DIR, DSH017_DB_PATH, DSH017_BACKUP_DIR, and DSH017_PRESET_DIR values when starting and stopping services. The supervisor scripts and this utility do not silently move the live database.

## Create a backup

Run from the repository root:

    python3 scripts/data_backup.py backup \
      --data-dir "$DSH017_DATA_DIR" \
      --db-path "$DSH017_DB_PATH" \
      --preset-dir "$DSH017_PRESET_DIR" \
      --backup-dir "$DSH017_BACKUP_DIR"

Each archive is written with mode 0600. It contains a versioned manifest with file sizes and SHA-256 hashes. SQLite PRAGMA integrity_check must return ok before the archive is finalized. The script refuses symlinked databases, provider metadata, preset directories, or preset files, and rejects oversized inputs.

When optional variables are not set, export the same defaults used by the running service:

    export DSH017_DATA_DIR="$PWD/data"
    export DSH017_DB_PATH="$DSH017_DATA_DIR/bili_data.db"
    export DSH017_BACKUP_DIR="$DSH017_DATA_DIR/backup"
    export DSH017_PRESET_DIR="$PWD/presets"

## Restore to a new isolated directory

Stop the target DSH-017 services before using the restored directory. First choose new paths; do not point the restore command at the live data or live preset directory:

    mkdir -p "$HOME/dsh017-recovery"
    python3 scripts/data_backup.py restore \
      --archive "/path/to/dsh017-backup-....tar.gz" \
      --data-dir "$HOME/dsh017-recovery/data" \
      --preset-dir "$HOME/dsh017-recovery/presets"

The restore command verifies every manifest hash, rejects duplicate/path-traversal/symlink members, checks SQLite database integrity, validates provider metadata and UTF-8 presets, and refuses non-empty destinations. It stages and validates all archive files before creating destination files. It does not overwrite an existing database or merge directories.

To run the recovered copy, point the service to the restored paths:

    export DSH017_DATA_DIR="$HOME/dsh017-recovery/data"
    export DSH017_DB_PATH="$DSH017_DATA_DIR/bili_data.db"
    export DSH017_BACKUP_DIR="$DSH017_DATA_DIR/backup"
    export DSH017_PRESET_DIR="$HOME/dsh017-recovery/presets"

Use those exact values for startup and shutdown. Verify chats, Workspace projects and file versions, favorites, progress, search history, presets, and provider metadata before retiring the old data directory. Re-enter API keys and configure new auth tokens separately.

## Failure and rollback

- If archive or manifest validation fails, restore exits non-zero before creating destination data files.
- If a destination is non-empty, restore refuses to proceed; the existing files remain untouched.
- Keep the original data and preset directories until the recovered instance passes the checks above.
- If the recovered instance fails, stop it and point the supervisor scripts back to the original environment-variable values. Do not copy a partially recovered database over the original.
- This utility does not perform device-bound Android Keystore migration or prove an application-upgrade path; those require separate device testing.

## Isolated regression drill

    python3 -m unittest discover -s tests -p 'test_backup_restore.py' -v

The tests create synthetic records in a temporary database, archive and restore them into fresh directories, check representative table data and SQLite integrity, confirm that API keys and auth tokens are excluded, corrupt an archive to prove rejection, and verify that a non-empty destination is never overwritten.
