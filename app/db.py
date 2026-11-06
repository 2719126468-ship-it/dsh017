#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DB 层：连接、建表、快照、备份、规则表"""
import os
import json
import time
import sqlite3
import threading

# ==================== SQLite 持久化 ====================
_DATA_DIR = os.path.abspath(os.environ.get(
    "DSH017_DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
))
_DB_PATH = os.path.abspath(os.environ.get("DSH017_DB_PATH", os.path.join(_DATA_DIR, "bili_data.db")))
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
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
                      (q, int(time.time())���q�^