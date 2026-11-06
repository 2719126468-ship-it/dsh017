#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remote API token authentication for DSH017.

The server host is trusted by source IP (loopback + discovered local interface
addresses + explicitly configured exact IPs). Forwarded headers are never used.
Remote callers use HTTP Basic (username: dsh017, password: token) or Bearer tokens.
"""
from __future__ import annotations

import base64
import binascii
import hmac
import ipaddress
import os
import secrets
import socket
from pathlib import Path
from typing import Iterable

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_USERNAME = "dsh017"
_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_ADMIN_EXACT_PATHS = {
    ("/api/workspace/rules", "POST"),
    ("/api/workspace/rules", "DELETE"),
    ("/api/backup", "POST"),
}


def _token_file(path: Path) -> str:
    """Read an existing token or atomically create a private random one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f"Refusing to read token symlink: {path}")
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if not path.is_file():
            raise RuntimeError(f"Token path is not a regular file: {path}")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        value = path.read_text(encoding="utf-8").strip()
    else:
        value = secrets.token_urlsafe(32)
       ¶»§q«^