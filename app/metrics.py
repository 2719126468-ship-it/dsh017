#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""指标计数器 + playurl 短时缓存"""
import time
import threading


# ==================== 指标计数器 ====================
_METRICS = {"search_ok": 0, "search_fail": 0, "search_352": 0,
            "playurl_ok": 0, "proxy_bytes": 0, "fav_added": 0}
_METRICS_LOCK = threading.Lock()

def _metric_inc(key, n=1):
    with _METRICS_LOCK:
        _METRICS[key] = _METRICS.get(key, 0) + n

# ==================== playurl 短时缓存（5分钟） ====================
_PLAYURL_CACHE = {}
_PLAYURL_LOCK = threading.Lock()
_PLAYURL_TTL = 300

def _playurl_cache_get(key):
    with _PLAYURL_LOCK:
        item = _PLAYURL_CACHE.get(key)
        if not item: return None
        if time.time() - item["ts"] > _PLAYURL_TTL:
            _PLAYURL_CACHE.pop(key, None)
            return None
        return item["data"]

def _playurl_cache_set(key, data):
    with _PLAYURL_LOCK:
        _PLAYURL_CACHE[key] = {"ts": time.time(), "data": data}
        if len(_PLAYURL_CACHE) > 100:
            oldest = sorted(_PLAYURL_CACHE.items(), key=lambda x: x[1]["ts"])[:20]
            for k, _ in oldest:
                _PLAYURL_CACHE.pop(k, None)
