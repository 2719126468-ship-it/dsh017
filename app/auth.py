#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remote token authentication for DSH017.

The service host is trusted by actual peer IP only: loopback, detected local
addresses, and explicitly configured exact local IPs. Forwarded headers are ignored.
Remote browsers use HTTP Basic (username dsh017, password token); API clients may
use Authorization: Bearer <token>.
"""
from __future__ import annotations

import base64
import binascii
import fcntl
import hmac
import ipaddress
import os
import secrets
import socket
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_USERNAME = "dsh017"
_MAX_REQUEST_BYTES = 8 * 1024 * 1024
_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_ADMIN_EXACT_PATHS = {
    ("/api/workspace/rules", "POST"),
    ("/api/workspace/rules", "DELETE"),
    ("/api/backup", "POST"),
}


def _validate_token(value: str, label: str) -> None:
    if not isinstance(value, str) or len(value) < 32 or len(value) > 512:
        raise RuntimeError(f"{label} must contain 32–512 characters")
    if any(ch.isspace() for ch in value):
        raise RuntimeError(f"{label} must not contain whitespace")


def _token_file(path: Path) -> str:
    """Read or create one private token, serializing concurrent service starts."""
    path.parent.mkdir(parents=True, exist_ok=True)

    # All four Flask processes share this lock. Without it, a second process
    # could read the token file after O_EXCL creates it but before the first
    # process finishes writing the token.
    lock_path = path.parent / ".dsh017-auth.lock"
    lock_flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        lock_flags |= os.O_NOFOLLOW
    lock_fd = os.open(str(lock_path), lock_flags, 0o600)
    try:
        os.fchmod(lock_fd, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        if path.is_symlink():
            raise RuntimeError(f"Refusing to read token symlink: {path}")
        try:
            create_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                create_flags |= os.O_NOFOLLOW
            fd = os.open(str(path), create_flags, 0o600)
        except FileExistsError:
            if path.is_symlink() or not path.is_file():
                raise RuntimeError(f"Token path is not a regular file: {path}")
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            value = path.read_text(encoding="utf-8").strip()
        else:
            value = secrets.token_urlsafe(32)
            with os.fdopen(fd, "w", encoding="utf-8") as token_file:
                token_file.write(value + "\n")
                token_file.flush()
                os.fsync(token_file.fileno())
        _validate_token(value, str(path))
        return value
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)


def _discover_local_ips() -> set[str]:
    """Discover host-owned addresses without trusting request headers."""
    found = {"127.0.0.1", "::1"}
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None):
            address = item[4][0].split("%", 1)[0]
            ipaddress.ip_address(address)
            found.add(address)
    except (OSError, ValueError):
        pass

    # UDP connect selects the primary outbound interface; it sends no payload.
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        found.add(sock.getsockname()[0])
    except OSError:
        pass
    finally:
        if sock is not None:
            sock.close()

    for raw in os.environ.get("DSH017_AUTH_EXEMPT_IPS", "").split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            found.add(str(ipaddress.ip_address(raw)))
        except ValueError as exc:
            raise RuntimeError(
                f"Invalid DSH017_AUTH_EXEMPT_IPS address: {raw!r}; use exact IPs"
            ) from exc
    return found


def _client_ip_is_local(remote_addr: str | None, local_ips: set[str]) -> bool:
    if not remote_addr:
        return False
    try:
        address = ipaddress.ip_address(remote_addr.split("%", 1)[0])
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        return address.is_loopback or str(address) in local_ips
    except ValueError:
        return False


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, separator, payload = authorization.partition(" ")
    if not separator:
        return None
    if scheme.lower() == "bearer":
        return payload.strip() or None
    if scheme.lower() == "basic":
        try:
            decoded = base64.b64decode(payload.strip(), validate=True).decode("utf-8")
            username, password = decoded.split(":", 1)
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return None
        return password if username == _USERNAME and password else None
    return None


def _requires_admin(path: str, method: str, json_body: dict | None) -> bool:
    if (path, method) in _ADMIN_EXACT_PATHS:
        return True
    if path.startswith("/api/preset/") and method in {"POST", "DELETE"}:
        return True
    if path == "/api/workspace/apply_edit" and method == "POST":
        body = json_body
        if body is None:
            from flask import request
            # The route force-parses JSON too; match it to prevent content-type bypass.
            body = request.get_json(force=True, silent=True)
        if not isinstance(body, dict):
            return True
        return body.get("mode", "ask") == "auto"
    return False


def _is_cross_site_write(request) -> bool:
    """Reject browser write requests whose Fetch Metadata/Origin is cross-site."""
    fetch_site = request.headers.get("Sec-Fetch-Site", "").strip().lower()
    if fetch_site in {"cross-site", "same-site"}:
        return True

    origin = request.headers.get("Origin")
    if not origin:
        origin = request.headers.get("Referer")
    if not origin:
        # Non-browser API clients commonly omit Origin and Referer.
        return False
    try:
        supplied = urlsplit(origin)
        current = urlsplit(request.host_url)
        return not (
            supplied.scheme.lower() == current.scheme.lower()
            and bool(supplied.netloc)
            and supplied.netloc.casefold() == current.netloc.casefold()
        )
    except ValueError:
        return True


def install_auth(
    app,
    *,
    auth_token: str | None = None,
    admin_token: str | None = None,
    data_dir: str | os.PathLike | None = None,
    local_ips: Iterable[str] | None = None,
):
    """Install a fail-closed auth gate on every Flask route.

    Standard token permits normal remote read/write. Admin token permits all
    operations, including policy changes, backup creation and automatic editing.
    Requests originating from this host are exempt.
    """

    # All services share one request-body ceiling to bound memory pressure.
    # Respect an explicit application override when embedding this helper.
    if app.config.get("MAX_CONTENT_LENGTH") is None:
        app.config["MAX_CONTENT_LENGTH"] = _MAX_REQUEST_BYTES
    root = Path(data_dir) if data_dir is not None else Path(
        os.environ.get("DSH017_DATA_DIR", str(_DEFAULT_DATA_DIR))
    )
    root.mkdir(parents=True, exist_ok=True)

    normal = auth_token or os.environ.get("DSH017_AUTH_TOKEN") or _token_file(root / "auth_token")
    admin = admin_token or os.environ.get("DSH017_ADMIN_TOKEN") or _token_file(root / "admin_token")
    _validate_token(normal, "DSH017_AUTH_TOKEN")
    _validate_token(admin, "DSH017_ADMIN_TOKEN")
    if hmac.compare_digest(normal, admin):
        raise RuntimeError("DSH017_AUTH_TOKEN and DSH017_ADMIN_TOKEN must be different")

    trusted = set(local_ips) if local_ips is not None else _discover_local_ips()
    trusted.update({"127.0.0.1", "::1"})
    app.extensions["dsh017_auth"] = {
        "token_files": (str(root / "auth_token"), str(root / "admin_token")),
        "local_ips": frozenset(trusted),
    }

    @app.before_request
    def _dsh017_auth_gate():
        from flask import jsonify, request

        max_bytes = app.config.get("MAX_CONTENT_LENGTH")
        if (
            max_bytes is not None
            and request.content_length is not None
            and request.content_length > max_bytes
        ):
            response = jsonify({
                "code": -413,
                "message": "请求体超过服务端大小限制。",
            })
            response.status_code = 413
            response.headers["Cache-Control"] = "no-store"
            return response

        if _client_ip_is_local(request.remote_addr, trusted):
            request.environ["dsh017.auth_level"] = "local"
            return None

        supplied = _extract_token(request.headers.get("Authorization"))
        level = None
        if supplied and hmac.compare_digest(supplied, admin):
            level = "admin"
        elif supplied and hmac.compare_digest(supplied, normal):
            level = "write"

        if level is None:
            response = jsonify({
                "code": -401,
                "message": "远程访问需要 Token。浏览器用户名填写 dsh017，密码填写访问 Token。",
            })
            response.status_code = 401
            response.headers["WWW-Authenticate"] = 'Basic realm="DSH017 remote access", charset="UTF-8"'
            response.headers["Cache-Control"] = "no-store"
            return response

        body = request.get_json(silent=True) if request.is_json else None
        if _requires_admin(request.path, request.method, body) and level != "admin":
            response = jsonify({"code": -403, "message": "此操作需要管理员 Token。"})
            response.status_code = 403
            response.headers["Cache-Control"] = "no-store"
            return response

        if request.method in _WRITE_METHODS and _is_cross_site_write(request):
            response = jsonify({"code": -403, "message": "拒绝跨站写入请求。"})
            response.status_code = 403
            response.headers["Cache-Control"] = "no-store"
            return response

        if request.method in _WRITE_METHODS and level not in {"write", "admin"}:
            response = jsonify({"code": -403, "message": "此操作需要写入权限。"})
            response.status_code = 403
            response.headers["Cache-Control"] = "no-store"
            return response

        request.environ["dsh017.auth_level"] = level
        return None

    return app.extensions["dsh017_auth"]
