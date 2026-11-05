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
            if faved: _metric_inc("fav_added")
            return jsonify({"code": 0, "faved": faved})
        except Exception as e:
            return jsonify({"code": -500, "message": str(e)})
    return jsonify({"code": 0, "items": db_fav_list()})

@workspace_bp.route("/api/fav/check")
def api_fav_check():
    bvid = request.args.get("bvid", "").strip()
    if not bvid:
        return jsonify({"code": -1, "message": "缺少 bvid"})
    return jsonify({"code": 0, "faved": db_fav_check(bvid)})

@workspace_bp.route("/api/progress", methods=["GET", "POST"])
def api_progress():
    if request.method == "POST":
        try:
            body = request.get_json(force=True, silent=True) or {}
            bvid = (body.get("bvid") or "").strip()
            if not bvid:
                return jsonify({"code": -1, "message": "缺少 bvid"})
            db_progress_save(bvid, body.get("cid", 0),
                             body.get("position", 0), body.get("duration", 0))
            return jsonify({"code": 0})
        except Exception as e:
            return jsonify({"code": -500, "message": str(e)})
    bvid = request.args.get("bvid", "").strip()
    cid = request.args.get("cid", "0")
    try: cid = int(cid)
    except: cid = 0
    prog = db_progress_get(bvid, cid)
    if prog is None:
        return jsonify({"code": 0, "position": 0, "duration": 0})
    return jsonify({"code": 0, **prog})






@workspace_bp.route("/api/backup", methods=["POST"])
def api_backup():
    """手动触发一次 DB 备份，返回备份路径"""
    try:
        path = _db_backup_once()
        if path.startswith("ERR"):
            return jsonify({"code": -500, "message": path})
        # 顺便返回当前备份目录里有哪些
        import os
        files = []
        try:
            files = sorted(f for f in os.listdir(_BACKUP_DIR)
                           if f.startswith("bili_data_") and f.endswith(".db"))
        except Exception:
            pass
        return jsonify({"code": 0, "path": path, "files": files})
    except Exception as e:
        return jsonify({"code": -500, "message": str(e)})

@workspace_bp.route("/api/backup", methods=["GET"])
def api_backup_list():
    import os
    files = []
    try:
        files = sorted(f for f in os.listdir(_BACKUP_DIR)
                       if f.startswith("bili_data_") and f.endswith(".db"))
    except Exception:
        pass
    return jsonify({"code": 0, "dir": _BACKUP_DIR, "files": files, "keep": _BACKUP_KEEP})



















# ==================== 工作区权限规则层 ====================
_WORKSPACE_ROOT = "/workspace/"
_AUTO_BLOCK_STREAK = 0
_AUTO_DOWNGRADED = False
_AUTO_BLOCK_THRESHOLD = 3


def _ws_scope_check(file_name):
    """作用域检查：文件名拼成虚拟路径，是否在 project_root 内"""
    full_path = _WORKSPACE_ROOT + (file_name or "")
    return full_path.startswith(_WORKSPACE_ROOT) and ".." not in full_path

def _ws_rule_lookup(file_name, operation):
    """规则层：deny > ask > allow，返回 action 或 None"""
    with _DB_LOCK:
        c = _db_conn()
        rows = c.execute(
            "SELECT file_pattern, operation, action FROM workspace_rules "
            "ORDER BY CASE action WHEN 'deny' THEN 0 WHEN 'ask' THEN 1 ELSE 2 END",
        ).fetchall()
        c.close()
    for r in rows:
        fp = r["file_pattern"]
        op = r["operation"]
        # 操作匹配：* 或精确
        if op != "*" and op != operation:
            continue
        # 文件匹配：* / 精确名 / 前缀 glob（简单实现）
        if fp == "*" or fp == file_name:
            return r["action"]
        if fp.endswith("*") and file_name.startswith(fp[:-1]):
            return r["action"]
    return None

def _ws_auto_guard():
    """断路器：连续被拦达阈值则降级"""
    global _AUTO_BLOCK_STREAK, _AUTO_DOWNGRADED
    return _AUTO_DOWNGRADED or _AUTO_BLOCK_STREAK >= _AUTO_BLOCK_THRESHOLD

def _ws_auto_on_block():
    global _AUTO_BLOCK_STREAK, _AUTO_DOWNGRADED
    _AUTO_BLOCK_STREAK += 1
    if _AUTO_BLOCK_STREAK >= _AUTO_BLOCK_THRESHOLD:
        _AUTO_DOWNGRADED = True

def _ws_auto_on_success():
    global _AUTO_BLOCK_STREAK
    _AUTO_BLOCK_STREAK = 0

# ==================== 工作区 API ====================

# ==================== 应用 AI 编辑 ====================

@workspace_bp.route("/api/workspace/rules", methods=["GET", "POST", "DELETE"])
def api_ws_rules():
    if request.method == "GET":
        with _DB_LOCK:
            c = _db_conn()
            rows = c.execute("SELECT id, file_pattern, operation, action, created_at "
                             "FROM workspace_rules ORDER BY created_at DESC").fetchall()
            c.close()
        return jsonify({"code": 0, "items": [dict(r) for r in rows]})
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
        fp = (body.get("file_pattern") or "").strip()
        op = (body.get("operation") or "edit").strip()
        action = (body.get("action") or "ask").strip()
        if not fp or action not in ("allow", "ask", "deny"):
            return jsonify({"code": -1, "message": "参数错误"})
        with _DB_LOCK:
            c = _db_conn()
            c.execute("INSERT INTO workspace_rules(file_pattern, operation, action, created_at) "
                      "VALUES(?,?,?,?)", (fp, op, action, int(time.time())))
            c.commit(); c.close()
        return jsonify({"code": 0})
    # DELETE 按 id
    rid = request.args.get("id")
    if not rid:
        return jsonify({"code": -1, "message": "缺少 id"})
    with _DB_LOCK:
        c = _db_conn()
        c.execute("DELETE FROM workspace_rules WHERE id=?", (int(rid),))
        c.commit(); c.close()
    return jsonify({"code": 0})

@workspace_bp.route("/api/workspace/auto_status")
def api_ws_auto_status():
    return jsonify({"code": 0,
                    "streak": _AUTO_BLOCK_STREAK,
                    "downgraded": _AUTO_DOWNGRADED,
                    "threshold": _AUTO_BLOCK_THRESHOLD})

@workspace_bp.route("/api/workspace/apply_edit", methods=["POST"])
def api_ws_apply_edit():
    body = request.get_json(force=True, silent=True) or {}
    file_id = body.get("file_id")
    old_str = body.get("old_str", "")
    new_str = body.get("new_str", "")
    base_version = body.get("base_version")
    mode = (body.get("mode") or "ask").strip()
    if file_id is None or base_version is None:
        return jsonify({"code": -1, "message": "缺少 file_id 或 base_version"})

    # 先拿文件名做作用域 + 规则检查
    with _DB_LOCK:
        c = _db_conn()
        row = c.execute("SELECT name, content, version FROM workspace_files "
                        "WHERE id=? AND deleted_at IS NULL", (file_id,)).fetchone()
        if not row:
            c.close()
            return jsonify({"code": -1, "message": "文件不存在"})
        file_name = row["name"]
        current_v = row["version"]
        current_content = row["content"]
        c.close()

    # ── 第 1 层：作用域检查 ──
    if not _ws_scope_check(file_name):
        _ws_auto_on_block()
        return jsonify({"code": 409, "action": "ask",
                        "reason": "scope_violation",
                        "message": "操作越出项目作用域，需要确认"})

    # ── 第 2 层：规则层（deny > ask > allow）──
    rule = _ws_rule_lookup(file_name, "edit")
    if rule == "deny":
        return jsonify({"code": 403, "action": "deny",
                        "message": "规则禁止修改该文件"})
    if rule == "ask":
        _ws_auto_on_block()
        return jsonify({"code": 409, "action": "ask",
                        "reason": "rule_ask",
                        "message": "规则要求确认此文件修改"})

    # ── 第 3 层：权限模式 ──
    if mode == "suggest":
        _ws_auto_on_block()
        return jsonify({"code": 409, "action": "ask",
                        "reason": "mode_suggest",
                        "message": "仅建议模式，不自动应用"})
    if mode == "ask":
        _ws_auto_on_block()
        return jsonify({"code": 409, "action": "ask",
                        "reason": "mode_ask",
                        "message": "询问模式，需确认"})

    # mode == auto
    # ── 第 4 层：断路器 ──
    if _ws_auto_guard():
        _ws_auto_on_block()
        return jsonify({"code": 409, "action": "ask",
                        "reason": "auto_downgraded",
                        "message": "连续拦截过多，已降级为询问模式"})

    # ── 第 5 层：真的应用 ──
    with _DB_LOCK:
        c = _db_conn()
        row2 = c.execute("SELECT version, content FROM workspace_files "
                         "WHERE id=? AND deleted_at IS NULL", (file_id,)).fetchone()
        if not row2:
            c.close()
            return jsonify({"code": -1, "message": "文件不存在"})
        current_v = row2["version"]
        current_content = row2["content"]
        if current_v != base_version:
            c.close()
            _ws_auto_on_block()
            return jsonify({"code": 409, "action": "ask",
                            "reason": "version_conflict",
                            "message": "文件已被修改，请重新打开",
                            "current_version": current_v})
        if old_str == "":
            new_content = new_str
        else:
            if old_str not in current_content:
                c.close()
                return jsonify({"code": 409, "action": "ask",
                                "reason": "old_str_not_found",
                                "message": "old_str 在文件中找不到（可能已被手改）"})
            cnt = current_content.count(old_str)
            if cnt > 1:
                c.close()
                return jsonify({"code": 409, "action": "ask",
                                "reason": "old_str_not_unique",
                                "message": "old_str 出现 %d 次，不唯一" % cnt})
            new_content = current_content.replace(old_str, new_str, 1)
        now = int(time.time())
        new_v = current_v + 1
        # Aider 教训：AI 应用前先记一条 ai_pre_edit 快照
        _snapshot_file(c, file_id, current_content, "ai_pre_edit", current_v)
        c.execute("UPDATE workspace_files SET content=?, version=?, updated_at=? WHERE id=?",
                  (new_content, new_v, now, file_id))
        _snapshot_file(c, file_id, new_content, "ai", current_v)
        c.commit(); c.close()
    _ws_auto_on_success()
    return jsonify({"code": 0, "version": new_v, "content": new_content,
                    "auto_applied": True})

@workspace_bp.route("/api/workspace/files", methods=["GET", "POST"])
def api_ws_files():
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"code": -1, "message": "缺少文件名"})
        with _DB_LOCK:
            c = _db_conn()
            now = int(time.time())
            cur = c.execute("INSERT INTO workspace_files(name, content, version, updated_at) "
                            "VALUES(?,?,?,?)", (name, "", 1, now))
            file_id = cur.lastrowid
            _snapshot_file(c, file_id, "", "manual", 0)
            c.commit(); c.close()
        return jsonify({"code": 0, "id": file_id, "name": name, "version": 1})
    with _DB_LOCK:
        c = _db_conn()
        rows = c.execute("SELECT id, name, version, updated_at, "
                         "length(content) AS size FROM workspace_files "
                         "WHERE deleted_at IS NULL ORDER BY updated_at DESC").fetchall()
        c.close()
    return jsonify({"code": 0, "items": [dict(r) for r in rows]})

@workspace_bp.route("/api/workspace/files/<int:file_id>", methods=["GET", "PUT", "DELETE"])
def api_ws_file(file_id):
    if request.method == "GET":
        with _DB_LOCK:
            c = _db_conn()
            row = c.execute("SELECT id, name, content, version, updated_at FROM workspace_files "
                            "WHERE id=? AND deleted_at IS NULL", (file_id,)).fetchone()
            c.close()
        if not row:
            return jsonify({"code": -1, "message": "文件不存在"})
        return jsonify({"code": 0, **dict(row)})

    if request.method == "PUT":
        body = request.get_json(force=True, silent=True) or {}
        content = body.get("content", "")
        base_version = body.get("base_version")
        if base_version is None:
            return jsonify({"code": -1, "message": "缺少 base_version（乐观锁必需）"})
        with _DB_LOCK:
            c = _db_conn()
            row = c.execute("SELECT version FROM workspace_files "
                            "WHERE id=? AND deleted_at IS NULL", (file_id,)).fetchone()
            if not row:
                c.close()
                return jsonify({"code": -1, "message": "文件不存在"})
            current_v = row["version"]
            if current_v != base_version:
                c.close()
                return jsonify({"code": 409, "message": "文件已被修改，请刷新后重试",
                                "current_version": current_v})
            now = int(time.time())
            new_v = current_v + 1
            c.execute("UPDATE workspace_files SET content=?, version=?, updated_at=? WHERE id=?",
                      (content, new_v, now, file_id))
            _snapshot_file(c, file_id, content, "manual", current_v)
            c.commit(); c.close()
        return jsonify({"code": 0, "version": new_v})

    if request.method == "DELETE":
        with _DB_LOCK:
            c = _db_conn()
            c.execute("UPDATE workspace_files SET deleted_at=? WHERE id=?",
                      (int(time.time()), file_id))
            c.commit(); c.close()
        return jsonify({"code": 0})
