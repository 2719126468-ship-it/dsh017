#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B站路由：搜索/分页/播放地址/音频/视频/封面/代理"""
import os
import json
import time
import subprocess
import tempfile
import urllib.parse
import logging
from flask import Blueprint, request, jsonify, Response
from app.bili_client import client, UA
from app.metrics import _metric_inc, _playurl_cache_get, _playurl_cache_set
from app.db import db_history_add
from app.security import validate_remote_url

logger = logging.getLogger(__name__)

bili_bp = Blueprint('bili', __name__)

def _safe_unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass


@bili_bp.route("/api/suggest")
def api_suggest():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"code": 0, "items": []})
    try:
        r = client.s.get("https://s.search.bilibili.com/main/suggest",
                         params={"term": q, "main_ver": "v1"},
                         headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/"},
                         timeout=8)
        data = r.json()
        # 兼容多种结构：result.tag 或直接是 list
        import re as _re
        def _clean(x):
            if not isinstance(x, str): return ""
            return _re.sub(r"<[^>]+>", "", x).strip()
        items = []
        if isinstance(data, dict):
            result = data.get("result") or data
            if isinstance(result, dict):
                tags = result.get("tag") or result.���q�^