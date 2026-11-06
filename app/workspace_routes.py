#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Workspace 路由：历史/收藏/进度/备份 + 文件 CRUD + 权限规则"""
import os
import json
import time
import threading
import re
import uuid
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
_AUTO_GUARD_LOCK = threading.Lock()


def _ws_scope_check(file_name):
    """Validate a virtual workspace filename; no filesystem path is accepted."""
    if not isinstance(file_name, str) or not file_name or len(file_name) > 180:
        return False
    if file_name in (".", "..") or any(ch in file_name for ch in ("/", "\\", "\x00")):
        return False
    return all(ord(ch) >= 32 for ch in file_name)

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
    # No matching rule must never silently grant automatic write permission.
    return "ask"

def _ws_auto_guard():
    """线程安全的自动编辑断路器。"""
    with _AUTO_GUARD_LOCK:
        return _AUTO_DOWNGRADED or _AUTO_BLOCK_STREAK >= _AUTO_BLOCK_THRESHOLD

def _ws_auto_on_block():
    global _AUTO_BLOCK_STREAK, _AUTO_DOWNGRADED
    with _AUTO_GUARD_LOCK:
        _AUTO_BLOCK_STREAK += 1
        if _AUTO_BLOCK_STREAK >= _AUTO_BLOCK_THRESHOLD:
            _AUTO_DOWNGRADED = True

def _ws_auto_on_success():
    global _AUTO_BLOCK_STREAK
    with _AUTO_GUARD_LOCK:
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

@workspace_bp.route("/api/workspace/confirm_edit", methods=["POST"])
def api_ws_confirm_edit():
    """Apply one AI suggestion only after an explicit user confirmation.

    This is a one-shot manual approval path: deny rules still win, current
    versions and unique old_str are checked, and each change is snapshotted.
    It does not grant standing automatic-write permission.
    """
    body = request.get_json(force=True, silent=True)
    if not isinstance(body, dict):
        return jsonify({"code": -1, "message": "请求参数必须是 JSON 对象"}), 400
    file_id = body.get("file_id")
    base_version = body.get("base_version")
    old_str = body.get("old_str", "")
    new_str = body.get("new_str", "")
    if (
        isinstance(file_id, bool) or not isinstance(file_id, int) or file_id <= 0
        or isinstance(base_version, bool) or not isinstance(base_version, int) or base_version < 1
        or not isinstance(old_str, str) or not isinstance(new_str, str)
        or len(new_str) > 1_000_000
    ):
        return jsonify({"code": -1, "message": "文件 ID、版本或编辑内容格式无效"}), 400

    with _DB_LOCK:
        c = _db_conn()
        row = c.execute(
            "SELECT name,content,version,kind FROM workspace_files "
            "WHERE id=? AND deleted_at IS NULL",
            (file_id,),
        ).fetchone()
        if row is None or row["kind"] != "file":
            c.close()
            return jsonify({"code": -1, "message": "文件不存在"}), 404
        if row["version"] != base_version:
            current_version = row["version"]
            c.close()
            return jsonify({
                "code": 409, "action": "ask", "reason": "version_conflict",
                "message": "文件已被修改，请重新打开后再确认",
                "current_version": current_version,
            }), 409
        if not _ws_scope_check(row["name"]):
            c.close()
            return jsonify({"code": 403, "message": "文件名不在允许的工作区范围内"}), 403
        rule = _ws_rule_lookup(row["name"], "edit")
        if rule == "deny":
            c.close()
            return jsonify({"code": 403, "message": "规则禁止修改该文件"}), 403

        current_content = row["content"]
        if old_str == "":
            updated_content = new_str
        else:
            occurrences = current_content.count(old_str)
            if occurrences != 1:
                c.close()
                return jsonify({
                    "code": 409, "reason": "old_str_not_unique",
                    "message": "待替换内容必须恰好出现一次；请刷新文件后重新生成建议",
                }), 409
            updated_content = current_content.replace(old_str, new_str, 1)

        new_version = row["version"] + 1
        now = int(time.time())
        _snapshot_file(c, file_id, current_content, "ai_confirmed_before", row["version"])
        c.execute(
            "UPDATE workspace_files SET content=?,version=?,updated_at=? WHERE id=?",
            (updated_content, new_version, now, file_id),
        )
        _snapshot_file(c, file_id, updated_content, "ai_confirmed", row["version"])
        c.commit()
        c.close()

    return jsonify({
        "code": 0, "version": new_version, "content": updated_content,
        "confirmed_by_user": True,
    })


@workspace_bp.route("/api/workspace/apply_edit", methods=["POST"])
def api_ws_apply_edit():
    body = request.get_json(force=True, silent=True)
    if not isinstance(body, dict):
        return jsonify({"code": -1, "message": "请求参数必须是 JSON 对象"}), 400
    file_id = body.get("file_id")
    old_str = body.get("old_str", "")
    new_str = body.get("new_str", "")
    base_version = body.get("base_version")
    if (
        isinstance(file_id, bool) or not isinstance(file_id, int) or file_id <= 0
        or isinstance(base_version, bool) or not isinstance(base_version, int) or base_version < 1
        or not isinstance(old_str, str) or not isinstance(new_str, str)
    ):
        return jsonify({"code": -1, "message": "文件 ID、版本或编辑内容格式无效"}), 400
    raw_mode = body.get("mode", "ask")
    if not isinstance(raw_mode, str):
        return jsonify({"code": -1, "message": "mode 必须是 ask、suggest 或 auto"}), 400
    mode = raw_mode
    if mode not in ("ask", "suggest", "auto"):
        return jsonify({"code": -1, "message": "mode 必须是 ask、suggest 或 auto"}), 400
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

_WS_PROJECT_ID_RE = re.compile(r"^(?:default|[0-9a-f]{32})$")

@workspace_bp.route("/api/workspace/projects", methods=["GET", "POST"])
def api_ws_projects():
    if request.method == "GET":
        with _DB_LOCK:
            c = _db_conn()
            rows = c.execute(
                "SELECT p.id,p.name,p.description,p.created_at,p.updated_at,"
                "(SELECT COUNT(*) FROM workspace_files f WHERE f.workspace_id=p.id "
                "AND f.deleted_at IS NULL AND f.kind='file') AS file_count "
                "FROM workspace_projects p ORDER BY p.updated_at DESC"
            ).fetchall()
            c.close()
        return jsonify({"code": 0, "items": [dict(row) for row in rows]})

    body = request.get_json(force=True, silent=True) or {}
    name = body.get("name")
    description = body.get("description", "")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        return jsonify({"code": -1, "message": "项目名称必填，最多80字符"}), 400
    if not isinstance(description, str) or len(description) > 300:
        return jsonify({"code": -1, "message": "项目描述最多300字符"}), 400
    project_id = uuid.uuid4().hex
    now = int(time.time())
    with _DB_LOCK:
        c = _db_conn()
        c.execute(
            "INSERT INTO workspace_projects(id,name,description,created_at,updated_at) "
            "VALUES(?,?,?,?,?)",
            (project_id, name.strip(), description.strip(), now, now),
        )
        c.commit()
        c.close()
    return jsonify({"code": 0, "item": {
        "id": project_id, "name": name.strip(), "description": description.strip(),
        "created_at": now, "updated_at": now, "file_count": 0,
    }}), 201


@workspace_bp.route("/api/workspace/projects/<project_id>", methods=["GET", "PUT", "DELETE"])
def api_ws_project(project_id):
    if not _WS_PROJECT_ID_RE.fullmatch(project_id or ""):
        return jsonify({"code": -1, "message": "项目 ID 无效"}), 400
    if request.method == "GET":
        with _DB_LOCK:
            c = _db_conn()
            row = c.execute(
                "SELECT id,name,description,created_at,updated_at "
                "FROM workspace_projects WHERE id=?",
                (project_id,),
            ).fetchone()
            c.close()
        if row is None:
            return jsonify({"code": -1, "message": "项目不存在"}), 404
        return jsonify({"code": 0, "item": dict(row)})

    if request.method == "DELETE":
        if project_id == "default":
            return jsonify({"code": -1, "message": "默认工作区不能删除"}), 400
        now = int(time.time())
        with _DB_LOCK:
            c = _db_conn()
            exists = c.execute("SELECT id FROM workspace_projects WHERE id=?", (project_id,)).fetchone()
            if exists is None:
                c.close()
                return jsonify({"code": -1, "message": "项目不存在"}), 404
            c.execute(
                "UPDATE workspace_files SET deleted_at=? "
                "WHERE workspace_id=? AND deleted_at IS NULL",
                (now, project_id),
            )
            c.execute("DELETE FROM workspace_projects WHERE id=?", (project_id,))
            c.commit()
            c.close()
        return jsonify({"code": 0})

    body = request.get_json(force=True, silent=True) or {}
    name = body.get("name")
    description = body.get("description", "")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        return jsonify({"code": -1, "message": "项目名称必填，最多80字符"}), 400
    if not isinstance(description, str) or len(description) > 300:
        return jsonify({"code": -1, "message": "项目描述最多300字符"}), 400
    now = int(time.time())
    with _DB_LOCK:
        c = _db_conn()
        cur = c.execute(
            "UPDATE workspace_projects SET name=?,description=?,updated_at=? WHERE id=?",
            (name.strip(), description.strip(), now, project_id),
        )
        c.commit()
        changed = cur.rowcount > 0
        c.close()
    if not changed:
        return jsonify({"code": -1, "message": "项目不存在"}), 404
    return jsonify({"code": 0, "item": {
        "id": project_id, "name": name.strip(), "description": description.strip(),
        "updated_at": now,
    }})


@workspace_bp.route("/api/workspace/files", methods=["GET", "POST"])
def api_ws_files():
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
        name = body.get("name")
        project_id = body.get("workspace_id", body.get("project_id", "default"))
        parent_id = body.get("parent_id")
        kind = body.get("kind", "file")
        if not isinstance(name, str) or not _ws_scope_check(name.strip()):
            return jsonify({"code": -1, "message": "文件名无效，不能包含路径分隔符"}), 400
        name = name.strip()
        if not isinstance(project_id, str) or not _WS_PROJECT_ID_RE.fullmatch(project_id):
            return jsonify({"code": -1, "message": "项目 ID 无效"}), 400
        if kind not in ("file", "directory"):
            return jsonify({"code": -1, "message": "kind 必须是 file 或 directory"}), 400
        if parent_id is not None and (
            isinstance(parent_id, bool) or not isinstance(parent_id, int) or parent_id <= 0
        ):
            return jsonify({"code": -1, "message": "父目录 ID 无效"}), 400
        with _DB_LOCK:
            c = _db_conn()
            project = c.execute("SELECT id FROM workspace_projects WHERE id=?", (project_id,)).fetchone()
            if project is None:
                c.close()
                return jsonify({"code": -1, "message": "项目不存在"}), 404
            if parent_id is not None:
                parent = c.execute(
                    "SELECT workspace_id,kind FROM workspace_files "
                    "WHERE id=? AND deleted_at IS NULL",
                    (parent_id,),
                ).fetchone()
                if parent is None or parent["workspace_id"] != project_id or parent["kind"] != "directory":
                    c.close()
                    return jsonify({"code": -1, "message": "父目录不存在或不属于当前项目"}), 400
            duplicate = c.execute(
                "SELECT id FROM workspace_files WHERE workspace_id=? AND parent_id IS ? "
                "AND name=? AND deleted_at IS NULL",
                (project_id, parent_id, name),
            ).fetchone()
            if duplicate:
                c.close()
                return jsonify({"code": -1, "message": "同一目录下已存在同名文件"}), 409
            now = int(time.time())
            cur = c.execute(
                "INSERT INTO workspace_files(name,parent_id,workspace_id,kind,content,version,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (name, parent_id, project_id, kind, "", 1, now),
            )
            file_id = cur.lastrowid
            if kind == "file":
                _snapshot_file(c, file_id, "", "manual", 0)
            c.execute("UPDATE workspace_projects SET updated_at=? WHERE id=?", (now, project_id))
            c.commit()
            c.close()
        return jsonify({
            "code": 0, "id": file_id, "name": name, "version": 1,
            "workspace_id": project_id, "parent_id": parent_id, "kind": kind,
        }), 201

    project_id = request.args.get("project_id", request.args.get("workspace_id"))
    if project_id is not None and (
        not isinstance(project_id, str) or not _WS_PROJECT_ID_RE.fullmatch(project_id)
    ):
        return jsonify({"code": -1, "message": "项目 ID 无效"}), 400
    with _DB_LOCK:
        c = _db_conn()
        query = (
            "SELECT id,name,parent_id,workspace_id,kind,version,updated_at,"
            "length(content) AS size FROM workspace_files WHERE deleted_at IS NULL"
        )
        params = []
        if project_id is not None:
            query += " AND workspace_id=?"
            params.append(project_id)
        query += " ORDER BY kind DESC,updated_at DESC"
        rows = c.execute(query, params).fetchall()
        c.close()
    return jsonify({"code": 0, "items": [dict(row) for row in rows]})


@workspace_bp.route("/api/workspace/files/<int:file_id>/versions", methods=["GET"])
def api_ws_file_versions(file_id):
    with _DB_LOCK:
        c = _db_conn()
        exists = c.execute(
            "SELECT id FROM workspace_files WHERE id=? AND deleted_at IS NULL",
            (file_id,),
        ).fetchone()
        if exists is None:
            c.close()
            return jsonify({"code": -1, "message": "文件不存在"}), 404
        rows = c.execute(
            "SELECT id,source,base_version,created_at,length(content) AS size "
            "FROM workspace_file_versions WHERE file_id=? ORDER BY created_at DESC LIMIT 50",
            (file_id,),
        ).fetchall()
        c.close()
    return jsonify({"code": 0, "items": [dict(row) for row in rows]})


@workspace_bp.route("/api/workspace/files/<int:file_id>/restore", methods=["POST"])
def api_ws_file_restore(file_id):
    body = request.get_json(force=True, silent=True) or {}
    version_id = body.get("version_id")
    base_version = body.get("base_version")
    if (
        isinstance(version_id, bool) or not isinstance(version_id, int) or version_id <= 0
        or isinstance(base_version, bool) or not isinstance(base_version, int) or base_version < 1
    ):
        return jsonify({"code": -1, "message": "版本 ID 或当前版本无效"}), 400
    with _DB_LOCK:
        c = _db_conn()
        file_row = c.execute(
            "SELECT version FROM workspace_files WHERE id=? AND deleted_at IS NULL",
            (file_id,),
        ).fetchone()
        version_row = c.execute(
            "SELECT content FROM workspace_file_versions WHERE id=? AND file_id=?",
            (version_id, file_id),
        ).fetchone()
        if file_row is None or version_row is None:
            c.close()
            return jsonify({"code": -1, "message": "文件或历史版本不存在"}), 404
        if file_row["version"] != base_version:
            c.close()
            return jsonify({"code": 409, "message": "文件已被其他位置修改，请刷新后重试",
                            "current_version": file_row["version"]}), 409
        current_version = file_row["version"]
        content = version_row["content"]
        new_version = current_version + 1
        _snapshot_file(c, file_id, content, "restore", current_version)
        now = int(time.time())
        c.execute(
            "UPDATE workspace_files SET content=?,version=?,updated_at=? WHERE id=?",
            (content, new_version, now, file_id),
        )
        c.commit()
        c.close()
    return jsonify({"code": 0, "version": new_version, "content": content})


@workspace_bp.route("/api/workspace/files/<int:file_id>", methods=["GET", "PUT", "PATCH", "DELETE"])
def api_ws_file(file_id):
    if request.method == "GET":
        with _DB_LOCK:
            c = _db_conn()
            row = c.execute(
                "SELECT id,name,parent_id,workspace_id,kind,content,version,updated_at "
                "FROM workspace_files WHERE id=? AND deleted_at IS NULL",
                (file_id,),
            ).fetchone()
            c.close()
        if not row:
            return jsonify({"code": -1, "message": "文件不存在"}), 404
        if row["kind"] != "file":
            return jsonify({"code": -1, "message": "所选项目是目录，不是文件"}), 400
        return jsonify({"code": 0, **dict(row)})

    if request.method == "PATCH":
        body = request.get_json(force=True, silent=True) or {}
        name = body.get("name")
        if not isinstance(name, str) or not _ws_scope_check(name.strip()):
            return jsonify({"code": -1, "message": "新名称无效"}), 400
        name = name.strip()
        with _DB_LOCK:
            c = _db_conn()
            row = c.execute(
                "SELECT workspace_id,parent_id,kind FROM workspace_files "
                "WHERE id=? AND deleted_at IS NULL",
                (file_id,),
            ).fetchone()
            if row is None:
                c.close()
                return jsonify({"code": -1, "message": "文件不存在"}), 404
            duplicate = c.execute(
                "SELECT id FROM workspace_files WHERE workspace_id=? AND parent_id IS ? "
                "AND name=? AND id<>? AND deleted_at IS NULL",
                (row["workspace_id"], row["parent_id"], name, file_id),
            ).fetchone()
            if duplicate:
                c.close()
                return jsonify({"code": -1, "message": "同一目录下已存在同名文件"}), 409
            c.execute("UPDATE workspace_files SET name=?,updated_at=? WHERE id=?",
                      (name, int(time.time()), file_id))
            c.commit()
            c.close()
        return jsonify({"code": 0, "name": name})

    if request.method == "PUT":
        body = request.get_json(force=True, silent=True) or {}
        content = body.get("content", "")
        base_version = body.get("base_version")
        if not isinstance(content, str) or len(content) > 1_000_000:
            return jsonify({"code": -1, "message": "文件内容必须是字符串且不能超过1MB"}), 400
        if isinstance(base_version, bool) or not isinstance(base_version, int) or base_version < 1:
            return jsonify({"code": -1, "message": "缺少有效 base_version（乐观锁必需）"}), 400
        with _DB_LOCK:
            c = _db_conn()
            row = c.execute(
                "SELECT version,workspace_id,kind FROM workspace_files "
                "WHERE id=? AND deleted_at IS NULL",
                (file_id,),
            ).fetchone()
            if not row or row["kind"] != "file":
                c.close()
                return jsonify({"code": -1, "message": "文件不存在"}), 404
            current_v = row["version"]
            if current_v != base_version:
                c.close()
                return jsonify({"code": -1, "message": "文件已被修改，请刷新后重试",
                                "current_version": current_v}), 409
            now = int(time.time())
            new_v = current_v + 1
            c.execute("UPDATE workspace_files SET content=?, version=?, updated_at=? WHERE id=?",
                      (content, new_v, now, file_id))
            _snapshot_file(c, file_id, content, "manual", current_v)
            c.execute(
                "UPDATE workspace_projects SET updated_at=? WHERE id=?",
                (now, row["workspace_id"]),
            )
            c.commit()
            c.close()
        return jsonify({"code": 0, "version": new_v})

    if request.method == "DELETE":
        now = int(time.time())
        with _DB_LOCK:
            c = _db_conn()
            row = c.execute(
                "SELECT parent_id FROM workspace_files WHERE id=? AND deleted_at IS NULL",
                (file_id,),
            ).fetchone()
            if row is None:
                c.close()
                return jsonify({"code": -1, "message": "文件不存在"}), 404
            pending = [file_id]
            descendants = []
            while pending:
                current = pending.pop()
                descendants.append(current)
                children = c.execute(
                    "SELECT id FROM workspace_files WHERE parent_id=? AND deleted_at IS NULL",
                    (current,),
                ).fetchall()
                pending.extend(child["id"] for child in children)
            placeholders = ",".join("?" for _ in descendants)
            c.execute(
                "UPDATE workspace_files SET deleted_at=? WHERE id IN (%s)" % placeholders,
                [now] + descendants,
            )
            c.commit()
            c.close()
        return jsonify({"code": 0})
