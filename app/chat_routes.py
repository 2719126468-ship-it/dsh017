#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chat 基础设施路由：预设管理 + X/HN 代理"""
import os
import json
import time
import urllib.parse
import base64
from flask import Blueprint, request, jsonify, Response
from app.llm_config import _PRESET_DIR, ZHIPU_API_KEY, ZHIPU_BASE, ZHIPU_MODEL
from app.bili_client import client, UA

chat_bp = Blueprint('chat', __name__)

@chat_bp.route("/api/presets")
def api_presets():
    import os
    items = []
    try:
        for fn in sorted(os.listdir(_PRESET_DIR)):
            if fn.endswith(".txt"):
                name = fn[:-4]
                path = os.path.join(_PRESET_DIR, fn)
                size = os.path.getsize(path)
                items.append({"name": name, "size": size})
    except Exception:
        pass
    return jsonify({"code": 0, "items": items, "dir": _PRESET_DIR})


@chat_bp.route("/api/preset/<name>", methods=["POST", "DELETE"])
def api_preset_write(name):
    import os
    if "/" in name or ".." in name:
        return jsonify({"code": -1, "message": "非法名称"})
    path = os.path.join(_PRESET_DIR, name + ".txt")
    if request.method == "DELETE":
        try:
            if os.path.exists(path): os.remove(path)
            return jsonify({"code": 0})
        except Exception as e:
            return jsonify({"code": -500, "message": str(e)})
    body = request.get_json(force=True, silent=True) or {}
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(body.get("���q�^