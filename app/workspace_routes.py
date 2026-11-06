#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Workspace 路由：历史/收藏/进度/备份 + 文件 CRUD + 权限规则"""
import os
import json
import time
import threading
from flask import Blueprint, request, jsonify
from app.db import (
    _DB_LOCK, _db_conn, _snapshot_file, _db_backup_once,
    _BACKUP_DIR, _BACKUP_KEEP,
    db_history_add, db_history_list, db_history_clear,
    db_fav_toggle, db_fav_check, db_fav_list,
    db_progress_save, db_progress_get,
)
from app.metrics import _metric_inc

workspace_bp = Blueprint('workspace', __name__)

# ==================== 权限规则层（本地） ====================
@workspace_bp.route("/api/history", methods=["GET", "DELETE"])
def api_history():
    if request.method == "DELETE":
        db_history_clear()
        return jsonify({"code": 0})
    return jsonify({"code": 0, "items": [{"q": q} for q in db_history_list(10)]})

@workspace_bp.route("/api/fav", methods=["GET", "POST"])
def api_fav():
    if request.method == "POST":
        try:
            body = request.get_json(force=True, silent=True) or {}
            bvid = (body.get("bvid") or "").strip()
            if not bvid.startswith("BV"):
                return jsonify({"code": -1, "message": "无效 bvid"})
            faved = db_fav_toggle(bvid, body.get("title", ""),
                                  body.get("cover", ""), body.get("author", ""))
            if faved is None:
                return jsonify({"code": -500, "message": "写入失败"})
    ���q�^