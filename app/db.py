#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DB 层：连接、建表、快照、备份、规则表"""
import os
import json
import time
import sqlite3
import threading
import shutil

# ==================== SQLite 持久化 ====================
_DATA_DIR = os.path.abspath(os.environ.get(
    "DSH017_DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
))
_DB_PATH = os.path.abspath(os.environ.get("DSH017_DB_PATH", os.path.join(_DATA_DIR, "bili_data.db")))
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
# One-time migration from the previous fixed container path; never overwrite new data.
_LEGACY_DB_PATH = "/root/bili_data.db"
if not os.environ.get("DSH017_DB_PATH") and not os.path.exists(_DB_PATH) and os.path.isfile(_LEGACY_DB_PATH):
    try:
        shutil.copy2(_LEGACY_DB_PATH, _DB_PATH)
    except OSError:
        pass
_DB_LOCK = threading.RLock()

def _db_conn():
    c = sqlite3.connect(_DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c

def _db_init():
    with _DB_LOCK:
        c = _db_conn()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS search_history (
            q TEXT PRIMARY KEY, ts INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS favorites (
            bvid TEXT PRIMARY KEY, title TEXT, cover TEXT, author TEXT,
            ts INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS watch_progress (
            bvid TEXT NOT NULL, cid INTEGER NOT NULL,
            position REAL DEFAULT 0, duration REAL DEFAULT 0,
            ts INTEGER NOT NULL, PRIMARY KEY (bvid, cid));
        """)
        c.commit(); c.close()

_db_init()

def db_history_add(q):
    try:
        with _DB_LOCK:
            c = _db_conn()
            c.execute("INSERT OR REPLACE INTO search_history(q, ts) VALUES(?, ?)",
                      (q, int(time.time())))
            c.execute("DELETE FROM search_history WHERE q NOT IN "
                      "(SELECT q FROM search_history ORDER BY ts DESC LIMIT 20)")
            c.commit(); c.close()
    except Exception: pass

def db_history_list(limit=10):
    try:
        with _DB_LOCK:
            c = _db_conn()
            rows = c.execute("SELECT q FROM search_history ORDER BY ts DESC LIMIT ?",
                             (limit,)).fetchall()
            c.close()
            return [r["q"] for r in rows]
    except Exception: return []

def db_history_clear():
    try:
        with _DB_LOCK:
            c = _db_conn()
            c.execute("DELETE FROM search_history")
            c.commit(); c.close()
    except Exception: pass

def db_fav_toggle(bvid, title, cover, author):
    try:
        with _DB_LOCK:
            c = _db_conn()
            row = c.execute("SELECT bvid FROM favorites WHERE bvid=?", (bvid,)).fetchone()
            if row:
                c.execute("DELETE FROM favorites WHERE bvid=?", (bvid,))
                faved = False
            else:
                c.execute("INSERT INTO favorites(bvid, title, cover, author, ts) "
                          "VALUES(?,?,?,?,?)",
                          (bvid, title or "", cover or "", author or "", int(time.time())))
                faved = True
            c.commit(); c.close()
            return faved
    except Exception: return None

def db_fav_check(bvid):
    try:
        with _DB_LOCK:
            c = _db_conn()
            row = c.execute("SELECT bvid FROM favorites WHERE bvid=?", (bvid,)).fetchone()
            c.close()
            return bool(row)
    except Exception: return False

def db_fav_list():
    try:
        with _DB_LOCK:
            c = _db_conn()
            rows = c.execute("SELECT bvid, title, cover, author, ts FROM favorites "
                             "ORDER BY ts DESC").fetchall()
            c.close()
            return [dict(r) for r in rows]
    except Exception: return []

def db_progress_save(bvid, cid, position, duration):
    try:
        with _DB_LOCK:
            c = _db_conn()
            c.execute("INSERT OR REPLACE INTO watch_progress(bvid, cid, position, duration, ts) "
                      "VALUES(?,?,?,?,?)",
                      (bvid, int(cid or 0), float(position or 0),
                       float(duration or 0), int(time.time())))
            c.commit(); c.close()
    except Exception: pass

def db_progress_get(bvid, cid):
    try:
        with _DB_LOCK:
            c = _db_conn()
            row = c.execute("SELECT position, duration FROM watch_progress "
                            "WHERE bvid=? AND cid=?",
                            (bvid, int(cid or 0))).fetchone()
            c.close()
            if row: return {"position": row["position"], "duration": row["duration"]}
            return None
    except Exception: return None

# ==================== SQLite 持久化结束 ====================

# ==================== 工作区（文件空间） ====================
def _db_init_workspace():
    with _DB_LOCK:
        c = _db_conn()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS workspace_files (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            parent_id INTEGER DEFAULT NULL,
            content TEXT NOT NULL DEFAULT '',
            version INTEGER NOT NULL DEFAULT 1,
            deleted_at INTEGER DEFAULT NULL,
            updated_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS workspace_file_versions (
            id INTEGER PRIMARY KEY,
            file_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            source TEXT NOT NULL,
            base_version INTEGER,
            created_at INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_ws_ver_file ON workspace_file_versions(file_id, created_at DESC);
        """)
        c.commit(); c.close()

def _snapshot_file(c, file_id, content, source, base_version):
    now = int(time.time())
    c.execute("INSERT INTO workspace_file_versions(file_id, content, source, base_version, created_at) "
              "VALUES(?,?,?,?,?)", (file_id, content, source, base_version, now))
    # 只保留最近 50 个版本
    c.execute("""DELETE FROM workspace_file_versions
                 WHERE file_id=? AND id NOT IN (
                     SELECT id FROM workspace_file_versions
                     WHERE file_id=? ORDER BY created_at DESC LIMIT 50
                 )""", (file_id, file_id))

_db_init_workspace()

# ==================== SQLite 每日备份 ====================
_BACKUP_DIR = os.path.abspath(os.environ.get("DSH017_BACKUP_DIR", os.path.join(_DATA_DIR, "backup")))
_BACKUP_KEEP = 7

def _db_backup_once():
    import os, shutil
    try:
        os.makedirs(_BACKUP_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(_BACKUP_DIR, "bili_data_%s.db" % ts)
        with _DB_LOCK:
            c = _db_conn()
            bc = sqlite3.connect(dst)
            c.backup(bc)
            bc.close()
            c.close()
        files = sorted(f for f in os.listdir(_BACKUP_DIR)
                       if f.startswith("bili_data_") and f.endswith(".db"))
        for old in files[:-_BACKUP_KEEP]:
            try: os.remove(os.path.join(_BACKUP_DIR, old))
            except Exception: pass
        return dst
    except Exception as e:
        return "ERR: %s" % e

def _db_backup_loop():
    # 启动后等 60s 做首次备份，避免和 init 抢锁
    time.sleep(60)
    while True:
        _db_backup_once()
        time.sleep(86400)

try:
    threading.Thread(target=_db_backup_loop, daemon=True).start()
except Exception:
    pass

def _db_init_rules():
    with _DB_LOCK:
        c = _db_conn()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS workspace_rules (
            id INTEGER PRIMARY KEY,
            file_pattern TEXT NOT NULL,
            operation TEXT NOT NULL,
            action TEXT NOT NULL,
            created_at INTEGER
        );
        """)
        c.commit(); c.close()

_db_init_rules()


# ==================== Chat conversations ====================
def _db_init_chat_conversations():
    with _DB_LOCK:
        c = _db_conn()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS chat_conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '新对话',
            messages TEXT NOT NULL DEFAULT '[]',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_chat_conversations_updated
            ON chat_conversations(updated_at DESC);
        """)
        c.commit()
        c.close()


_db_init_chat_conversations()


def db_chat_conversation_create(title, messages):
    """Create a persisted conversation and return its public record."""
    import uuid
    now = int(time.time())
    conversation_id = uuid.uuid4().hex
    safe_title = str(title or "新对话").strip()[:80] or "新对话"
    encoded = json.dumps(messages, ensure_ascii=False, separators=(",", ":"))
    with _DB_LOCK:
        c = _db_conn()
        c.execute(
            "INSERT INTO chat_conversations(id, title, messages, created_at, updated_at) "
            "VALUES(?,?,?,?,?)",
            (conversation_id, safe_title, encoded, now, now),
        )
        # Keep local storage bounded: retain the 200 most recently updated chats.
        c.execute(
            "DELETE FROM chat_conversations WHERE id NOT IN "
            "(SELECT id FROM chat_conversations ORDER BY updated_at DESC LIMIT 200)"
        )
        c.commit()
        c.close()
    return {
        "id": conversation_id,
        "title": safe_title,
        "messages": messages,
        "created_at": now,
        "updated_at": now,
    }


def db_chat_conversations_list(limit=50):
    limit = max(1, min(200, int(limit)))
    with _DB_LOCK:
        c = _db_conn()
        rows = c.execute(
            "SELECT id, title, created_at, updated_at, messages "
            "FROM chat_conversations ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        c.close()
    items = []
    for row in rows:
        try:
            messages = json.loads(row["messages"])
        except (TypeError, ValueError):
            messages = []
        items.append({
            "id": row["id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "message_count": len(messages) if isinstance(messages, list) else 0,
        })
    return items


def db_chat_conversation_get(conversation_id):
    with _DB_LOCK:
        c = _db_conn()
        row = c.execute(
            "SELECT id, title, messages, created_at, updated_at "
            "FROM chat_conversations WHERE id=?",
            (conversation_id,),
        ).fetchone()
        c.close()
    if row is None:
        return None
    try:
        messages = json.loads(row["messages"])
    except (TypeError, ValueError):
        messages = []
    if not isinstance(messages, list):
        messages = []
    return {
        "id": row["id"],
        "title": row["title"],
        "messages": messages,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def db_chat_conversation_update(conversation_id, title, messages):
    now = int(time.time())
    safe_title = str(title or "新对话").strip()[:80] or "新对话"
    encoded = json.dumps(messages, ensure_ascii=False, separators=(",", ":"))
    with _DB_LOCK:
        c = _db_conn()
        cursor = c.execute(
            "UPDATE chat_conversations SET title=?, messages=?, updated_at=? WHERE id=?",
            (safe_title, encoded, now, conversation_id),
        )
        c.commit()
        updated = cursor.rowcount > 0
        c.close()
    if not updated:
        return None
    return db_chat_conversation_get(conversation_id)


def db_chat_conversation_delete(conversation_id):
    with _DB_LOCK:
        c = _db_conn()
        cursor = c.execute(
            "DELETE FROM chat_conversations WHERE id=?",
            (conversation_id,),
        )
        c.commit()
        deleted = cursor.rowcount > 0
        c.close()
    return deleted
