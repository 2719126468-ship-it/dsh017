"""Android SAF adapter for the shared, versioned DSH-017 backup format."""
from __future__ import annotations

import argparse
import os

from dsh017_data_backup import _backup, _restore


def create_backup(data_dir: str, preset_dir: str, backup_dir: str) -> str:
    """Create a validated archive in app cache for a Java SAF export."""
    data_dir = os.path.abspath(data_dir)
    args = argparse.Namespace(
        data_dir=data_dir,
        db_path=os.path.join(data_dir, "bili_data.db"),
        preset_dir=os.path.abspath(preset_dir),
        backup_dir=os.path.abspath(backup_dir),
    )
    return str(_backup(args))


def restore_backup(archive_path: str, data_dir: str, preset_dir: str) -> bool:
    """Validate fully, then restore only to new/empty app-private destinations."""
    args = argparse.Namespace(
        archive=os.path.abspath(archive_path),
        data_dir=os.path.abspath(data_dir),
        preset_dir=os.path.abspath(preset_dir),
        db_name="bili_data.db",
    )
    _restore(args)
    return True
