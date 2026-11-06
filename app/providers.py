#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenAI Chat Completions-compatible provider registry.

Provider metadata never contains credentials. On Termux credentials live in a
private 0600 file; the Android WebView bridge keeps them in Android Keystore.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import secrets
import threading
from urllib.parse import urlsplit, urlunsplit

from flask import Blueprint, jsonify, request, Response

from app.db import _DATA_DIR
from app.provider_transport import provider_request, validate_provider_url_syntax

provider_bp = Blueprint("providers", __name__)
_LOCK = threading.RLock()
_RUNTIME_SECRETS = {}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+@-]{0,159}$")
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
    normalized = urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path.rstrip("/"), "", ""))
    if not validate_provider_url_syntax(normalized):
        raise ValueError(
            "供应商地址不安全：远程服务必须使用解析到公网地址的 HTTPS；"
            "HTTP 仅允许本机 loopback 网关"
        )
    return normalized


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
    # The outbound transport resolves, classifies and pins the actual TCP target.
    response = provider_request(
        "GET",
        _models_url(provider["base_url"]),
        headers=headers,
        timeout=(5, 15),
    )
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



_MAGPIE_HOST = "127.0.0.1"
_MAGPIE_PORT = 3425
_MAGPIE_APP_KEY = "magpie-dsh017"
_MAGPIE_MAX_JSON_BYTES = 1024 * 1024


def _magpie_get_json(path, include_app_key=False):
    """Read one fixed local Magpie endpoint without proxies or redirects."""
    if path not in {"/api/hello", "/v1/models"}:
        raise ValueError("Magpie endpoint is not allowed")
    connection = http.client.HTTPConnection(
        _MAGPIE_HOST, _MAGPIE_PORT, timeout=3
    )
    headers = {
        "Accept": "application/json",
        "User-Agent": "DSH-017/0.1",
        "Connection": "close",
    }
    if include_app_key:
        headers["Authorization"] = "Bearer " + _MAGPIE_APP_KEY
    try:
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        if response.status != 200:
            response.read(512)
            raise RuntimeError(
                "本机 Magpie 接口 %s 返回 HTTP %d" % (path, response.status)
            )
        raw = response.read(_MAGPIE_MAX_JSON_BYTES + 1)
        if len(raw) > _MAGPIE_MAX_JSON_BYTES:
            raise RuntimeError("本机 Magpie 返回的数据超过 1 MiB 限制")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            raise RuntimeError("本机 Magpie 返回的 JSON 无效") from error
        if not isinstance(payload, dict):
            raise RuntimeError("本机 Magpie 返回了无效的数据结构")
        return payload
    finally:
        connection.close()


def discover_local_magpie():
    """Identify the local Magpie gateway and read its OpenAI model catalog."""
    hello = _magpie_get_json("/api/hello")
    if hello.get("name") != "magpie":
        raise RuntimeError("127.0.0.1:3425 上运行的服务不是 Magpie Gateway")
    catalog = _magpie_get_json("/v1/models", include_app_key=True)
    data = catalog.get("data")
    if not isinstance(data, list):
        raise RuntimeError("Magpie 没有返回 OpenAI 兼容的 models 列表")
    models = sorted({
        item["id"].strip()
        for item in data
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and _MODEL_RE.fullmatch(item["id"].strip())
    })[:100]
    if not models:
        raise RuntimeError("Magpie Gateway 已找到，但没有发现可用模型")
    return {
        "id": "magpie",
        "name": "Magpie Gateway",
        "base_url": "http://127.0.0.1:3425/v1",
        "models": models,
        "default_model": models[0],
        "gateway_version": str(hello.get("version") or "unknown")[:80],
    }

def resolve_provider(provider_id, model):
    provider = get_provider(provider_id or "zhipu")
    if provider is None or not provider["enabled"]:
        raise ValueError("供应商不存在或已停用")
    if not isinstance(model, str) or not _MODEL_RE.fullmatch(model):
        raise ValueError("模型 ID 无效")
    if model not in provider["models"]:
        raise ValueError("该模型未列入此供应商的允许模型列表")
    # DNS validation and IP pinning happen atomically at the outbound transport.
    key = get_provider_secret(provider["id"])
    host = (urlsplit(provider["base_url"]).hostname or "").lower()
    local_no_key = host in {"127.0.0.1", "localhost", "::1"}
    if not key and not local_no_key:
        raise ValueError("尚未配置该供应商的 API Key")
    endpoint = provider["base_url"]
    if endpoint.endswith("/chat/completions"):
        chat_url = endpoint
    else:
        chat_url = endpoint + "/chat/completions"
    return provider, key, chat_url



PROVIDERS_HTML = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>模型供应商 · DSH-017</title>
<style>
:root{--p-bg:#0b0c10;--p-panel:#15171d;--p-panel2:#1c1f27;--p-text:#f4f3ef;
 --p-muted:#9295a1;--p-line:rgba(255,255,255,.09);--p-accent:#d97757;--p-good:#59c995;
 --p-warn:#e4b56d;--p-bad:#ed8585}
*{box-sizing:border-box}
html,body{margin:0;min-height:100%;background:var(--p-bg);color:var(--p-text);
 font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif}
body{padding:0 16px 50px}
.wrap{max-width:1040px;margin:0 auto}
header{display:flex;align-items:center;gap:12px;padding:16px 0;border-bottom:1px solid var(--p-line)}
header h1{flex:1;margin:0;font-size:18px;letter-spacing:-.035em}
.back,.quiet-btn,.primary-btn,.danger-btn{border:1px solid var(--p-line);background:var(--p-panel2);
 color:var(--p-text);border-radius:10px;padding:9px 12px;font:inherit;font-size:12px;text-decoration:none;cursor:pointer}
.primary-btn{background:var(--p-accent);color:#fff;border-color:transparent;font-weight:650}
.danger-btn{color:var(--p-bad)}
main{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(300px,.9fr);gap:15px;padding-top:18px}
.panel{min-width:0;border:1px solid var(--p-line);border-radius:17px;background:var(--p-panel);padding:17px}
.panel h2{font-size:14px;margin:0 0 5px}
.desc{font-size:11px;color:var(--p-muted);line-height:1.6;margin:0 0 16px}
.provider-list{display:flex;flex-direction:column;gap:9px}
.provider{display:flex;align-items:center;gap:11px;border:1px solid var(--p-line);
 border-radius:13px;padding:12px;background:rgba(255,255,255,.018)}
.provider-main{flex:1;min-width:0}
.provider-name{font-size:13px;font-weight:620;overflow-wrap:anywhere}
.provider-meta{font:10px/1.5 ui-monospace,monospace;color:var(--p-muted);margin-top:4px;overflow-wrap:anywhere}
.provider-status{font-size:10px;margin-top:5px;color:var(--p-good)}
.provider-status.missing{color:var(--p-warn)}
.provider-actions{display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end}
.provider-actions button{padding:7px 9px;font-size:10px}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.field{display:flex;flex-direction:column;gap:6px;min-width:0}
.field.wide{grid-column:1/-1}
label{font-size:11px;color:var(--p-muted)}
input,textarea,select{width:100%;border:1px solid var(--p-line);border-radius:10px;
 background:var(--p-bg);color:var(--p-text);padding:10px 11px;font:12px/1.5 inherit;
 font-family:inherit;outline:none;min-width:0}
textarea{min-height:72px;resize:vertical}
input:focus,textarea:focus,select:focus{border-color:var(--p-accent)}
.hint{font-size:10px;color:var(--p-muted);line-height:1.55}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:13px}
.status{min-height:18px;margin-top:10px;font-size:11px;color:var(--p-muted);line-height:1.5}
.status.error{color:var(--p-bad)}.status.ok{color:var(--p-good)}
.preset-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin:12px 0}
.preset{border:1px solid var(--p-line);border-radius:11px;padding:9px;background:var(--p-panel2);
 text-align:left;color:var(--p-text);font-family:inherit;font-size:11px;line-height:1.4;cursor:pointer}
.preset small{display:block;color:var(--p-muted);font-size:9px;margin-top:3px}
.callout{padding:12px;border:1px dashed var(--p-line);border-radius:12px;color:var(--p-muted);
 font-size:10px;line-height:1.65;margin-top:13px}
.callout a{color:var(--p-accent);text-decoration:none}
@media(max-width:760px){body{padding:0 11px 36px}main{grid-template-columns:1fr}.panel{padding:14px}
 .provider{align-items:flex-start;flex-wrap:wrap}.provider-actions{width:100%;justify-content:flex-start}}
@media(max-width:420px){.form-grid{grid-template-columns:1fr}.field.wide{grid-column:auto}}
</style></head><body>
<div class="wrap">
<header class="topbar"><a class="back" href="/chat">← 聊天</a><h1>模型供应商</h1><a class="quiet-btn" href="/workspace">工作区</a></header>
<main>
<section class="panel">
 <h2>已连接供应商</h2>
 <p class="desc">统一管理 OpenAI Chat Completions 兼容接口。API Key 不会在列表或模型选择器中回显。</p>
 <div class="provider-list" id="providers"><div class="hint">正在加载供应商…</div></div>
 <div class="callout">供应商连接仅影响 AI 聊天。模型实际配额与计费仍由对应服务商账户决定。远程更改供应商配置需要管理员 Token。</div>
</section>
<section class="panel">
 <h2 id="formTitle">添加兼容供应商</h2>
 <p class="desc">粘贴服务商提供的 API 根地址（通常以 /v1 结尾），填写模型 ID；可以从 /models 自动发现。</p>
 <div class="preset-grid" id="presets">
  <button class="preset" data-preset="openai">OpenAI<small>api.openai.com/v1</small></button>
  <button class="preset" data-preset="deepseek">DeepSeek<small>api.deepseek.com/v1</small></button>
  <button class="preset" data-preset="zai">Z.ai / GLM<small>open.bigmodel.cn</small></button>
  <button class="preset" data-preset="kimi">Kimi<small>api.moonshot.cn/v1</small></button>
  <button class="preset" data-preset="qwen">Qwen / DashScope<small>compatible-mode/v1</small></button>
  <button class="preset" data-preset="minimax">MiniMax<small>api.minimax.io/v1</small></button>
  <button class="preset" data-preset="openrouter">OpenRouter<small>openrouter.ai/api/v1</small></button>
  <button class="preset" data-preset="siliconflow">SiliconFlow<small>api.siliconflow.cn/v1</small></button>
  <button class="preset" data-preset="ollama">Ollama 本地<small>127.0.0.1:11434/v1</small></button>
  <button class="preset" data-preset="lmstudio">LM Studio 本地<small>127.0.0.1:1234/v1</small></button>
  <button class="preset" data-preset="magpie">Magpie Gateway<small>127.0.0.1:3425/v1</small></button>
  <button class="preset" data-preset="custom">自定义地址<small>任何兼容接口</small></button>
 </div>
 <form id="providerForm">
  <div class="form-grid">
   <div class="field"><label for="pid">内部 ID</label><input id="pid" required maxlength="48" placeholder="my-provider"></div>
   <div class="field"><label for="pname">显示名称</label><input id="pname" required maxlength="80" placeholder="My Provider"></div>
   <div class="field wide"><label for="base">API Base URL</label><input id="base" required type="url" placeholder="https://api.example.com/v1"></div>
   <div class="field wide"><label for="models">模型 ID（每行一个）</label><textarea id="models" placeholder="model-id-1&#10;model-id-2"></textarea></div>
   <div class="field"><label for="defaultModel">默认模型</label><input id="defaultModel" placeholder="留空使用第一项"></div>
   <div class="field"><label for="apiKey">API Key</label><input id="apiKey" type="password" autocomplete="new-password" placeholder="新增时填写；编辑时留空表示不改"></div>
  </div>
  <div class="hint" style="margin-top:9px">协议：OpenAI Chat Completions（/chat/completions + /models）。只支持标准 Bearer Key；如服务商要求特殊签名或私有协议，暂不能直接接入。</div>
  <div class="actions">
   <button class="primary-btn" id="save" type="submit">保存供应商</button>
   <button class="quiet-btn" id="detectMagpie" type="button">检测本机 Magpie</button>
   <button class="quiet-btn" id="refreshModels" type="button">从 /models 发现模型</button>
   <button class="quiet-btn" id="reset" type="button">清空表单</button>
  </div>
  <div class="status" id="status" role="status"></div>
 </form>
 <div class="callout">
  <b>Magpie 本机网关</b><br>
  先在 Magpie 中登录并启动 Gateway。要使用 Qoder，可在 Magpie 的 Plugins 中安装 <code>@magpie-community/opencode-qoder-auth</code>，然后对 <code>qoder</code> provider 完成它提供的浏览器授权；登录与刷新由 Magpie 插件负责。随后点击「检测本机 Magpie」，DSH 会从网关模型目录同步 Qoder 模型（通常以 <code>qoder/</code> 开头），再保存供应商即可在聊天和工作区选择。<br>
  检测仅访问本机固定端点，不读取账号 Cookie、Magpie 配置文件或其他凭据；如果 Magpie 与 DSH 不在同一设备/网络命名空间，需要手动配置可访问的 Gateway 地址。<br>
  Android ARM64 终端版本可从 <a href="https://github.com/yetone/magpie-releases/releases/latest" target="_blank" rel="noopener noreferrer">Magpie 官方 Releases</a> 获取。<br>
  <a href="https://usemagpie.ai/docs/start" target="_blank" rel="noopener noreferrer">Magpie 官方说明 ↗</a> ·
  <a href="https://usemagpie.ai/docs/plugins" target="_blank" rel="noopener noreferrer">Magpie 插件与登录 ↗</a> ·
  <a href="https://github.com/yetone/magpie/blob/main/AGENTS.md" target="_blank" rel="noopener noreferrer">Qoder 插件包 ↗</a> ·
  <a href="https://docs.qoder.com/cli/authentication" target="_blank" rel="noopener noreferrer">Qoder CLI 登录文档 ↗</a>
 </div>
</section>
</main>
</div>
<script>
(function(){
 "use strict";
 var $=function(id){return document.getElementById(id)};
 var currentEditId=null,providerRows=[];
 var presets={
  openai:["openai","OpenAI","https://api.openai.com/v1",["gpt-4.1","gpt-4.1-mini"]],
  deepseek:["deepseek","DeepSeek","https://api.deepseek.com/v1",["deepseek-chat","deepseek-reasoner"]],
  zai:["zai","Z.ai / GLM","https://open.bigmodel.cn/api/paas/v4",["glm-4.7-flash","glm-4.6v-flash"]],
  kimi:["kimi","Kimi","https://api.moonshot.cn/v1",["kimi-k2.5"]],
  qwen:["qwen","Qwen / DashScope","https://dashscope.aliyuncs.com/compatible-mode/v1",["qwen-plus","qwen-max"]],
  minimax:["minimax","MiniMax","https://api.minimax.io/v1",["MiniMax-M2.5"]],
  openrouter:["openrouter","OpenRouter","https://openrouter.ai/api/v1",["openai/gpt-4.1-mini"]],
  siliconflow:["siliconflow","SiliconFlow","https://api.siliconflow.cn/v1",["deepseek-ai/DeepSeek-V3"]],
  ollama:["ollama","Ollama 本地","http://127.0.0.1:11434/v1",[]],
  lmstudio:["lmstudio","LM Studio 本地","http://127.0.0.1:1234/v1",[]],
  magpie:["magpie","Magpie Gateway","http://127.0.0.1:3425/v1",[]],
  custom:["custom","自定义 OpenAI Compatible","https://api.example.com/v1",[]]
 };
 function esc(v){return String(v==null?"":v).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
 function status(message,kind){$("status").textContent=message||"";$("status").className="status "+(kind||"")}
 function fillPreset(key){
  var p=presets[key];if(!p)return;
  if(!currentEditId)$("pid").value=p[0];
  $("pname").value=p[1];$("base").value=p[2];$("models").value=p[3].join("\n");
  $("defaultModel").value=p[3][0]||"";$("apiKey").value="";
  status(key==="magpie"?"填写你自己的 Magpie Gateway Key；请勿粘贴 Qoder 网站 Cookie。":"模板已填充，请补充模型列表和 API Key。","");
 }
 $("presets").addEventListener("click",function(e){
  var btn=e.target.closest("[data-preset]");if(btn)fillPreset(btn.getAttribute("data-preset"));
 });
 function resetForm(){
  currentEditId=null;$("providerForm").reset();$("pid").disabled=false;
  $("formTitle").textContent="添加兼容供应商";$("save").textContent="保存供应商";
  status("");
 }
 $("reset").onclick=resetForm;
 function load(){
  fetch("/api/providers",{cache:"no-store"}).then(function(r){if(!r.ok)throw new Error("HTTP "+r.status);return r.json()})
  .then(function(j){
   if(j.code!==0)throw new Error(j.message||"加载失败");
   providerRows=j.items||[];
   $("providers").innerHTML=providerRows.map(function(p){
    var models=(p.models||[]).slice(0,5).join(", ")+(p.models&&p.models.length>5?" …":"");
    var meta=esc(p.base_url)+"<br>"+esc(models||"尚未配置模型");
    var state=p.secret_configured?"密钥已配置":"尚未配置密钥";
    var actions='<button class="quiet-btn" data-test="'+esc(p.id)+'">测试 / 发现模型</button>';
    if(!p.builtin)actions+='<button class="quiet-btn" data-edit="'+esc(p.id)+'">编辑</button><button class="danger-btn" data-delete="'+esc(p.id)+'">删除</button>';
    return '<article class="provider"><div class="provider-main"><div class="provider-name">'+esc(p.name)+'</div><div class="provider-meta">'+meta+'</div><div class="provider-status '+(p.secret_configured?"":"missing")+'">'+state+'</div></div><div class="provider-actions">'+actions+'</div></article>';
   }).join("")||'<div class="hint">暂无供应商</div>';
  }).catch(function(e){$("providers").textContent="加载失败："+e.message;});
 }
 $("providers").addEventListener("click",function(e){
  var test=e.target.closest("[data-test]"),edit=e.target.closest("[data-edit]"),del=e.target.closest("[data-delete]");
  if(test)testProvider(test.getAttribute("data-test"));
  if(edit)editProvider(edit.getAttribute("data-edit"));
  if(del)deleteProvider(del.getAttribute("data-delete"));
 });
 function testProvider(id){
  status("正在测试连接并读取模型列表…");
  fetch("/api/providers/"+encodeURIComponent(id)+"/models",{method:"POST"})
   .then(function(r){return r.json().then(function(j){if(!r.ok||j.code!==0)throw new Error(j.message||"连接失败");return j;});})
   .then(function(j){
    var p=providerRows.find(function(x){return x.id===id;});
    if(p){$("pid").value=id;$("pname").value=p.name;$("base").value=p.base_url;$("models").value=j.models.join("\n");$("defaultModel").value=p.default_model||j.models[0]||"";currentEditId=id;$("pid").disabled=true;$("formTitle").textContent="更新供应商 · "+p.name;$("save").textContent="保存模型列表";}
    status("连接成功，发现 "+j.models.length+" 个模型。保存表单后生效。","ok");
   }).catch(function(e){status("连接失败："+e.message,"error");});
 }
 function editProvider(id){
  var p=providerRows.find(function(x){return x.id===id;});if(!p)return;
  currentEditId=id;$("pid").value=p.id;$("pid").disabled=true;$("pname").value=p.name;
  $("base").value=p.base_url;$("models").value=(p.models||[]).join("\n");
  $("defaultModel").value=p.default_model||"";$("apiKey").value="";
  $("formTitle").textContent="编辑供应商 · "+p.name;$("save").textContent="保存修改";
  status("密钥已保存；密钥框留空将保持现有密钥不变。");
 }
 function deleteProvider(id){
  if(!confirm("删除供应商 "+id+"？"))return;
  fetch("/api/providers/"+encodeURIComponent(id),{method:"DELETE"})
   .then(function(r){return r.json().then(function(j){if(!r.ok||j.code!==0)throw new Error(j.message||"删除失败");return j;});})
   .then(function(){status("供应商已删除。","ok");load();})
   .catch(function(e){status(e.message,"error");});
 }
 $("providerForm").addEventListener("submit",function(e){
  e.preventDefault();
  var models=$("models").value.split(/[\n,]/).map(function(x){return x.trim();}).filter(Boolean);
  var body={id:$("pid").value.trim(),name:$("pname").value.trim(),base_url:$("base").value.trim(),
   models:models,default_model:$("defaultModel").value.trim()};
  var secret=$("apiKey").value.trim();
  var nativeBridge=window.DSHProviderKeys&&typeof window.DSHProviderKeys.save==="function";
  if(secret && !nativeBridge)body.api_key=secret;
  if(!secret && currentEditId===null && !nativeBridge)body.api_key="";
  var url=currentEditId?"/api/providers/"+encodeURIComponent(currentEditId):"/api/providers";
  var method=currentEditId?"PUT":"POST";
  status("正在保存供应商配置…");
  fetch(url,{method:method,headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})
   .then(function(r){return r.json().then(function(j){if(!r.ok||j.code!==0)throw new Error(j.message||"保存失败");return j;});})
   .then(function(j){
    var id=j.item.id;
    if(secret&&nativeBridge){
     var saved=window.DSHProviderKeys.save(id,secret);
     if(!saved)throw new Error("Android Keystore 保存失败");
    }
    currentEditId=id;
    status("供应商已保存。密钥只会保存在本地，不会在列表中回显。","ok");
    load();
   }).catch(function(err){status(err.message,"error");});
 });
 $("refreshModels").onclick=function(){
  var id=$("pid").value.trim();if(!id){status("请先填写供应商 ID。","error");return;}
  if(!currentEditId){status("请先保存供应商和密钥，再发现模型。","error");return;}
  testProvider(currentEditId);
 };
 $("detectMagpie").onclick=function(){
  status("正在检测本机 Magpie Gateway（127.0.0.1:3425）…");
  fetch("/api/providers/detect-magpie",{method:"POST"})
   .then(function(r){return r.json().then(function(j){if(!r.ok||j.code!==0)throw new Error(j.message||"未发现 Magpie");return j;});})
   .then(function(j){
    var p=j.item;
    currentEditId=providerRows.some(function(x){return x.id==="magpie";})?"magpie":null;
    $("pid").value=p.id;$("pid").disabled=!!currentEditId;
    $("pname").value=p.name;$("base").value=p.base_url;
    $("models").value=p.models.join("\n");$("defaultModel").value=p.default_model;
    $("apiKey").value="magpie-dsh017";
    $("formTitle").textContent=currentEditId?"更新本机 Magpie":"添加本机 Magpie";
    $("save").textContent="保存 Magpie 接入";
    status("已识别 Magpie "+p.gateway_version+"，发现 "+p.models.length+" 个模型。检查模型列表后保存即可连接。","ok");
   })
   .catch(function(e){status("未能连接本机 Magpie："+e.message,"error");});
 };
 load();
})();
</script></body></html>'''


@provider_bp.route("/providers")
def providers_page():
    return Response(PROVIDERS_HTML, mimetype="text/html")


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


@provider_bp.route("/api/providers/detect-magpie", methods=["POST"])
def api_detect_magpie():
    try:
        item = discover_local_magpie()
        return jsonify({"code": 0, "item": item})
    except Exception as error:
        return jsonify({
            "code": -1,
            "message": str(error)[:300],
        }), 502


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
