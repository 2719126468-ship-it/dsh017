#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import time, urllib.parse, sqlite3, threading, sqlite3, threading, os as _os
from functools import reduce
from hashlib import md5
from flask import Flask, request, jsonify, Response

from app.bili_client import (
    USE_CFFI, http_requests, UA, MIXIN_KEY_ENC_TAB, BiliClient, client,
)

from app.metrics import (
    _METRICS, _METRICS_LOCK, _metric_inc,
    _PLAYURL_CACHE, _PLAYURL_LOCK, _PLAYURL_TTL,
    _playurl_cache_get, _playurl_cache_set,
)
from app.llm_config import ZHIPU_API_KEY, ZHIPU_BASE, ZHIPU_MODEL, _PRESET_DIR

from app.play_routes import play_bp
from app.misc_routes import misc_bp
app = Flask(__name__)


from app.bili_routes import bili_bp
app.register_blueprint(bili_bp)

from app.chat_routes import chat_bp
app.register_blueprint(chat_bp)

from app.chat_ui import chat_ui_bp
app.register_blueprint(chat_ui_bp)

from app.workspace_routes import workspace_bp
app.register_blueprint(workspace_bp)

from app.workspace_ui import workspace_ui_bp
app.register_blueprint(workspace_ui_bp)

from app.providers import provider_bp
app.register_blueprint(provider_bp)

from app.shorts_routes import shorts_bp

def _lan_ip():
    try:
        import socket as _s
        _sock = _s.socket(_s.AF_INET, _s.SOCK_DGRAM)
        _sock.connect(("8.8.8.8", 80))
        _ip = _sock.getsockname()[0]
        _sock.close()
        return _ip
    except Exception:
        return "0.0.0.0"

app.register_blueprint(shorts_bp)
app.register_blueprint(play_bp)
app.register_blueprint(misc_bp)


# Remote clients must authenticate; requests originating from this host are trusted.
from app.auth import install_auth
_auth_info = install_auth(app)
from app.ui_theme import install_theme_support
install_theme_support(app)


if __name__ == "__main__":
    print(f"🎬 Bili Console v6: http://{_lan_ip()}:8092/")
    normal_source = "环境变量 DSH017_AUTH_TOKEN" if os.environ.get("DSH017_AUTH_TOKEN") else _auth_info["token_files"][0]
    admin_source = "环境变量 DSH017_ADMIN_TOKEN" if os.environ.get("DSH017_ADMIN_TOKEN") else _auth_info["token_files"][1]
    print("🔐 远程普通 Token 来源：" + normal_source)
    print("🔐 远程管理员 Token 来源：" + admin_source)
    print("   主机本机访问免认证；远程浏览器用户名为 dsh017，密码填写对应 Token。")
    if not ZHIPU_API_KEY:
        print("⚠️ 警告：未设置 ZHIPU_API_KEY 环境变量，聊天/总结/AI编辑将不可用")
    try:
        from waitress import serve
        import multiprocessing
        _cpu = multiprocessing.cpu_count() or 4
        _threads = max(4, _cpu * 2)
        print(f"🚀 Waitress · CPU={_cpu}核 · threads={_threads} · 超时120s")
        serve(app, host="0.0.0.0", port=8092, threads=_threads,
              channel_timeout=120, connection_limit=100)
    except ImportError:
        print("⚠️ waitress 未加载，回退 Flask 开发服务器")
        app.run(host="0.0.0.0", port=8092, threaded=True)