#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenAI Chat Completions-compatible provider registry.

Provider metadata never contains credentials. On Termux credentials live in a
private 0600 file; the Android WebView bridge keeps them in Android Keystore.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
from urllib.parse import urlsplit, urlunsplit

from flask import Blueprint, jsonify, request

from app.bili_client import client
from app.db import _DATA_DIR

provider_bp = Blueprint("providers", __name__)
_LOCK = threading.RLock()
_RUNTIME_SECRETS = {}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,159}$")
_CONFIG_PATH = os.path.join(_DATA_DIR, "providers.json")
_SECRETS_PATH = os.path.join(_DATA_DIR, "provider_secrets.json")

_BUILTIN = {
    "id": "zhipu",
    "name": "Z.ai / 智谱 GLM",
    "base_url": "https://open.bigmodel.cn/api/paas/v4",
    "protocol": "openai-chat-completions",
    "models": ["glm-4.7-flash", "glm-4.6v-flash"],
    "default_model": "glm-4.7-flash",
    "enabled": True,
    "builtin": True,
}


def _read_json(path, fallback):
    try:
        with open(path, "r", encoding="utf-8") as stream:
            value = json.load(stream)
        return value if isinstance(value, type(fallback)) else fallback
    except (OSError, ValueError, TypeError):
        return fallback


def _write_private_json(path, value):
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    encoded = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(fd)


def _normalise_base_url(raw):
    if not isinstance(raw, str) or not raw.strip() or len(raw.strip()) > 500:
        raise ValueError("Base URL 不能为空，且最多500字符")
    value = raw.strip().rstrip("/")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Base URL 必须是无账号密码、无查询参数的 HTTP(S) 地址")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _clean_models(raw):
    if not isinstance(raw, list) or len(raw) > 100:
        raise ValueError("models 必须是最多100项的数组")
    result = []
    seen = set()
    for item in raw:
        if not isinstance(item, str) or not _MODEL_RE.fullmatch(item.strip()):
            raise ValueError("模型 ID 格式无效")
        model = item.strip()
        if model not in seen:
            seen.add(model)
            result.append(model)
    return result


def _metadata():
    records = _read_json(_CONFIG_PATH, [])
    cleaned = []
    for item in records:
        if not isinstance(item, dict):
            continue
        if not _ID_RE.fullmatch(str(item.get("id", ""))) or item.get("id") == "zhipu":
            continue
        try:
            base_url = _normalise_base_url(item.get("base_url", ""))
            models = _clean_models(item.get("models", []))
        except ValueError:
            continue
        default_model = item.get("default_model", "")
        if default_model not in models:
            default_model = models[0] if models else ""
        cleaned.append({
            "id": item["id"],
            "name": str(item.get("name", item["id"]))[:80],
            "base_url": base_url,
            "protocol": "openai-chat-completions",
            "models": models,
            "default_model": default_model,
            "enabled": item.get("enabled") is not False,
            "builtin": False,
        })
    return cleaned


def list_providers():
    with _LOCK:
        records = [_BUILTIN.copy()] + _metadata()
        result = []
        for item in records:
            result.append({
                **item,
                "secret_configured": bool(get_provider_secret(item["id"])),
            })
        return result


def get_provider(provider_id):
    if not isinstance(provider_id, str) or not _ID_RE.fullmatch(provider_id):
        return None
    for item in [_BUILTIN] + _metadata():
        if item["id"] == provider_id:
            return item.copy()
    return None


def get_provider_secret(provider_id):
    with _LOCK:
        value = _RUNTIME_SECRETS.get(provider_id, "")
        if value:
            return value
        if provider_id == "zhipu":
            return os.environ.get("ZHIPU_API_KEY", "").strip()
        env_name = "DSH017_PROVIDER_" + re.sub(r"[^A-Z0-9]", "_", provider_id.upper()) + "_API_KEY"
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
        secrets_map = _read_json(_SECRETS_PATH, {})
        return str(secrets_map.get(provider_id, "") or "").strip()


def set_runtime_provider_secret(provider_id, value):
    if not isinstance(provider_id, str) or not _ID_RE.fullmatch(provider_id):
        return False
    with _LOCK:
        if value:
            _RUNTIME_SECRETS[provider_id] = str(value).strip()
        else:
            _RUNTIME_SECRETS.pop(provider_id, None)
    return True


def save_provider_secret(provider_id, value, persist=True):
    if not isinstance(provider_id, str) or not _ID_RE.fullmatch(provider_id):
        raise ValueError("供应商 ID 无效")
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError("API Key 必须是最多4096字符的字符串")
    with _LOCK:
        if persist:
            secrets_map = _read_json(_SECRETS_PATH, {})
            if value.strip():
                secrets_map[provider_id] = value.strip()
            else:
                secrets_map.pop(provider_id, None)
            if secrets_map:
                _write_private_json(_SECRETS_PATH, secrets_map)
            elif os.path.exists(_SECRETS_PATH):
                os.remove(_SECRETS_PATH)
        set_runtime_provider_secret(provider_id, value.strip())
    return True


def _save_metadata(records):
    safe_records = []
    for item in records:
        safe_records.append({key: item[key] for key in (
            "id", "name", "base_url", "protocol", "models", "default_model", "enabled"
        )})
    _write_private_json(_CONFIG_PATH, safe_records)


def add_provider(body):
    if not isinstance(body, dict):
        raise ValueError("请求必须是 JSON 对象")
    provider_id = body.get("id")
    name = body.get("name")
    if not isinstance(provider_id, str) or not _ID_RE.fullmatch(provider_id) or provider_id == "zhipu":
        raise ValueError("供应商 ID 只能包含小写字母、数字、下划线和连字符")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        raise ValueError("供应商名称必填，最多80字符")
    base_url = _normalise_base_url(body.get("base_url", ""))
    models = _clean_models(body.get("models", []))
    default_model = body.get("default_model", "")
    if default_model and default_model not in models:
        raise ValueError("默认模型必须包含在模型列表中")
    if not default_model and models:
        default_model = models[0]
    with _LOCK:
        records = _metadata()
        if any(item["id"] == provider_id for item in records):
            raise ValueError("供应商 ID 已存在")
        records.append({
            "id": provider_id, "name": name.strip(), "base_url": base_url,
            "protocol": "openai-chat-completions", "models": models,
            "default_model": default_model, "enabled": body.get("enabled") is not False,
            "builtin": False,
        })
        _save_metadata(records)
        if "api_key" in body:
            save_provider_secret(provider_id, body["api_key"])
    return get_provider(provider_id)


def update_provider(provider_id, body):
    if not isinstance(body, dict):
        raise ValueError("请求必须是 JSON 对象")
    with _LOCK:
        records = _metadata()
        item = next((entry for entry in records if entry["id"] == provider_id), None)
        if item is None:
            raise KeyError("供应商不存在")
        if "name" in body:
            name = body["name"]
            if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
                raise ValueError("供应商名称必填，最多80字符")
            item["name"] = name.strip()
        if "base_url" in body:
            item["base_url"] = _normalise_base_url(body["base_url"])
        if "models" in body:
            item["models"] = _clean_models(body["models"])
        if "default_model" in body:
            default_model = body["default_model"]
            if default_model and default_model not in item["models"]:
                raise ValueError("默认模型必须包含在模型列表中")
            item["default_model"] = default_model
        if "enabled" in body:
            item["enabled"] = bool(body["enabled"])
        _save_metadata(records)
        if "api_key" in body:
            save_provider_secret(provider_id, body["api_key"])
        elif body.get("clear_api_key") is True:
            save_provider_secret(provider_id, "")
    return get_provider(provider_id)


def delete_provider(provider_id):
    if provider_id == "zhipu":
        raise ValueError("内置智谱供应商不能删除")
    with _LOCK:
        records = _metadata()
        updated = [item for item in records if item["id"] != provider_id]
        if len(updated) == len(records):
            raise KeyError("供应商不存在")
        _save_metadata(updated)
        save_provider_secret(provider_id, "")


def _models_url(base_url):
    if base_url.endswith("/chat/completions"):
        return base_url[:-len("/chat/completions")] + "/models"
    if base_url.endswith("/models"):
        return base_url
    return base_url + "/models"


def fetch_provider_models(provider_id):
    provider = get_provider(provider_id)
    if provider is None:
        raise KeyError("供应商不存在")
    key = get_provider_secret(provider_id)
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    response = client.s.get(_models_url(provider["base_url"]), headers=headers, timeout=(5, 15))
    if response.status_code < 200 or response.status_code >= 300:
        raise RuntimeError("HTTP %d: %s" % (response.status_code, response.text[:240]))
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise RuntimeError("供应商没有返回 OpenAI 兼容的 models 数组")
    models = []
    for item in data[:100]:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            model_id = item["id"].strip()
            if _MODEL_RE.fullmatch(model_id):
                models.append(model_id)
    return sorted(set(models))


def resolve_provider(provider_id, model):
    provider = get_provider(provider_id or "zhipu")
    if provider is None or not provider["enabled"]:
        raise ValueError("供应商不存在或已停用")
    if not isinstance(model, str) or not _MODEL_RE.fullmatch(model):
        raise ValueError("模型 ID 无效")
    if model not in provider["models"]:
        raise ValueError("该模型未列入此供应商的允许模型列表")
    key = get_provider_secret(provider["id"])
    if not key:
        raise ValueError("尚未配置该供应商的 API Key")
    endpoint = provider["base_url"]
    if endpoint.endswith("/chat/completions"):
        chat_url = endpoint
    else:
        chat_url = endpoint + "/chat/completions"
    return provider, key, chat_url


@provider_bp.route("/api/providers", methods=["GET", "POST"])
def api_providers():
    if request.method == "GET":
        return jsonify({"code": 0, "items": list_providers()})
    body = request.get_json(force=True, silent=True)
    try:
        item = add_provider(body)
    except (ValueError, TypeError) as error:
        return jsonify({"code": -1, "message": str(error)}), 400
    return jsonify({"code": 0, "item": {
        **item, "secret_configured": bool(get_provider_secret(item["id"]))
    }}), 201


@provider_bp.route("/api/providers/<provider_id>", methods=["PUT", "DELETE"])
def api_provider(provider_id):
    if not _ID_RE.fullmatch(provider_id or ""):
        return jsonify({"code": -1, "message": "供应商 ID 无效"}), 400
    try:
        if request.method == "DELETE":
            delete_provider(provider_id)
            return jsonify({"code": 0})
        item = update_provider(provider_id, request.get_json(force=True, silent=True))
        return jsonify({"code": 0, "item": {
            **item, "secret_configured": bool(get_provider_secret(item["id"]))
        }})
    except KeyError as error:
        return jsonify({"code": -1, "message": str(error)}), 404
    except (ValueError, TypeError) as error:
        return jsonify({"code": -1, "message": str(error)}), 400


@provider_bp.route("/api/providers/<provider_id>/models", methods=["POST"])
def api_provider_models(provider_id):
    try:
        models = fetch_provider_models(provider_id)
        return jsonify({"code": 0, "models": models})
    except KeyError as error:
        return jsonify({"code": -1, "message": str(error)}), 404
    except Exception as error:
        return jsonify({"code": -1, "message": str(error)[:300]}), 502


@provider_bp.route("/api/providers/<provider_id>/test", methods=["POST"])
def api_provider_test(provider_id):
    try:
        models = fetch_provider_models(provider_id)
        return jsonify({
            "code": 0, "ok": True, "message": "连接成功",
            "model_count": len(models),
        })
    except KeyError as error:
        return jsonify({"code": -1, "message": str(error)}), 404
    except Exception as error:
        return jsonify({"code": -1, "message": str(error)[:300]}), 502
