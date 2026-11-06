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
from app.auth im¶»§q«^