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
                tags = result.get("tag") or result.get("suggest") or []
                for t in tags:
                    if isinstance(t, dict):
                        name = t.get("name") or t.get("value") or t.get("term")
                        name = _clean(name)
                        if name: items.append(name)
            elif isinstance(result, list):
                for t in result:
                    if isinstance(t, str):
                        name = _clean(t)
                        if name: items.append(name)
                    elif isinstance(t, dict):
                        name = t.get("name") or t.get("value") or t.get("term")
                        name = _clean(name)
                        if name: items.append(name)
        return jsonify({"code": 0, "items": items[:10]})
    except Exception as e:
        return jsonify({"code": -500, "message": str(e)})


@bili_bp.route("/api/search")
def api_search():
    q=request.args.get("q","").strip()
    if not q:
        return jsonify({"code":-1,"message":"空关键词"})
    try: page=int(request.args.get("page",1))
    except: page=1
    order = request.args.get("order", "totalrank")
    if order not in ("totalrank", "click", "pubdate", "dm", "stow"):
        order = "totalrank"
    search_type = request.args.get("type", "video")
    if search_type not in ("video", "media_bangumi", "media_ft"):
        search_type = "video"
    try: duration = int(request.args.get("duration", 0))
    except: duration = 0
    try:
        data = client.search(q, page, order, search_type, duration)
        if data.get("code") == 0:
            try: db_history_add(q)
            except Exception: pass
            _metric_inc("search_ok")
        if data.get("code") == -352:
            _metric_inc("search_352")
        if data.get("code") != 0:
            logger.warning("[SEARCH_FAIL] q=%s page=%d code=%s msg=%s",
                               q, page, data.get("code"), data.get("message"))
        return jsonify(data)
    except Exception as e:
        logger.exception("[SEARCH_EXC] q=%s page=%d", q, page)
        return jsonify({"code":-500,"message":str(e)})

@bili_bp.route("/api/pages")
def api_pages():
    """返回视频分P列表"""
    bvid = request.args.get("bvid", "").strip()
    if not bvid.startswith("BV"):
        return jsonify({"code": -1, "message": "无效 bvid"})
    try:
        info = client.s.get("https://api.bilibili.com/x/web-interface/view",
                            params={"bvid": bvid}, timeout=15).json()
        if info.get("code") != 0:
            return jsonify({"code": -1, "message": "详情失败: " + info.get("message", "")})
        d = info["data"]
        out = []
        for pg in (d.get("pages") or []):
            out.append({"cid": pg["cid"], "page": pg.get("page", 0),
                        "part": pg.get("part", ""), "duration": pg.get("duration", 0)})
        return jsonify({"code": 0, "bvid": bvid, "title": d["title"],
                        "author": d["owner"]["name"], "pages": out})
    except Exception as e:
        return jsonify({"code": -500, "message": str(e)})

@bili_bp.route("/api/playurl")
def api_playurl():
    bvid = request.args.get("bvid","").strip()
    if not bvid.startswith("BV"):
        return jsonify({"code":-1,"message":"无效 bvid"})
    try:
        cache_key = "%s_%s_%s" % (bvid, request.args.get("cid","0"),
                                   request.args.get("qn","80"))
        cached = _playurl_cache_get(cache_key)
        if cached:
            return jsonify(cached)
        info = client.s.get("https://api.bilibili.com/x/web-interface/view",
                            params={"bvid":bvid}, timeout=15).json()
        if info.get("code")!=0:
            return jsonify({"code":-1,"message":"详情失败: "+info.get("message","")})
        d = info["data"]
        try: cid = int(request.args.get("cid", 0)) or d["cid"]
        except: cid = d["cid"]
        try: qn = int(request.args.get("qn", 64))
        except: qn = 64
        if qn not in (16, 32, 64, 80):
            qn = 64
        sp = client.sign({"bvid":bvid,"cid":cid,"qn":qn,"fnval":1,"fourk":1})
        r = client.s.get("https://api.bilibili.com/x/player/wbi/playurl",
                         params=sp, timeout=20).json()
        if r.get("code")!=0:
            return jsonify({"code":-1,"message":"播放地址失败: "+r.get("message","")})
        durl = (r.get("data") or {}).get("durl") or []
        if not durl:
            return jsonify({"code":-1,"message":"无 durl，可能需要登录"})
        # 多段支持：每一段都是独立 MP4，前端顺序播放
        proxy_urls = []
        total_size = 0
        for seg in durl:
            raw = seg.get("url", "")
            if not raw: continue
            proxy_urls.append("/api/proxy?u=" + urllib.parse.quote(raw, safe=""))
            total_size += seg.get("size", 0) or 0
        if not proxy_urls:
            return jsonify({"code":-1,"message":"所有分段均无 url"})
        _metric_inc("playurl_ok")
        result = {"code":0,
            "url": proxy_urls[0],          # 兼容旧前端
            "urls": proxy_urls,            # 多段数组
            "segments": len(proxy_urls),
            "title": d["title"],
            "author": d["owner"]["name"],
            "cover": d["pic"],
            "cid": cid,
            "quality": r["data"].get("quality"),
            "size": total_size}
        _playurl_cache_set(cache_key, result)
        return jsonify(result)
    except Exception as e:
        return jsonify({"code":-500,"message":str(e)})

@bili_bp.route("/api/audio")
def api_audio():
    """下载音频：fnval=16 拿 M4A → FFmpeg 转 MP3（兼容老设备）"""
    import subprocess, tempfile, os
    from urllib.parse import quote

    bvid = request.args.get("bvid", "").strip()
    if not bvid.startswith("BV"):
        return "无效 bvid", 400

    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5, check=True)
    except Exception:
        return "FFmpeg 不可用，无法转码", 500

    try:
        try: cid = int(request.args.get("cid", 0)) or None
        except: cid = None
        raw_url, quality, title = client.get_audio_url(bvid, cid)
    except Exception as e:
        return f"获取音频失败: {e}", 500

    headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}

    tmp_m4a = tempfile.NamedTemporaryFile(suffix=".m4a", delete=False)
    tmp_mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_m4a.close(); tmp_mp3.close()
    try:
        r = client.s.get(raw_url, headers=headers, stream=True, timeout=60)
        if r.status_code != 200:
            return f"下载音频失败 HTTP {r.status_code}", 500
        with open(tmp_m4a.name, "wb") as f:
            for chunk in r.iter_content(64 * 1024):
                if chunk: f.write(chunk)
        try: r.close()
        except Exception: pass

        cmd = ["ffmpeg", "-y", "-i", tmp_m4a.name,
               "-vn", "-acodec", "libmp3lame", "-ab", "192k",
               "-ac", "2", "-ar", "44100", tmp_mp3.name]
        proc = subprocess.run(cmd, capture_output=True, timeout=180)
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", "ignore")[-500:]
            return f"FFmpeg 转码失败: {err}", 500

        safe_title = "".join(c for c in title if c not in r'\\/:*?"<>|').strip()[:80]
        if not safe_title: safe_title = bvid
        filename = safe_title + ".mp3"
        disp = f"attachment; filename*=UTF-8''{quote(filename)}"

        from flask import send_file
        response = send_file(tmp_mp3.name, mimetype="audio/mpeg",
                             as_attachment=True, download_name=filename,
                             conditional=True)
        response.call_on_close(lambda: _safe_unlink(tmp_mp3.name))
        return response

    finally:
        _safe_unlink(tmp_m4a.name)

@bili_bp.route("/api/img")
def api_img():
    """代理 B 站封面图，带 Referer，避免 403"""
    u = request.args.get("u", "")
    if not validate_remote_url(u, allowed_suffixes=("hdslb.com", "bilibili.com")):
        return "", 400
    try:
        r = client.s.get(u, headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/"},
                         timeout=(5, 15), stream=True, allow_redirects=False)
        def gen():
            try:
                for chunk in r.iter_content(chunk_size=32*1024):
                    if chunk:
                        yield chunk
            finally:
                r.close()
        resp = Response(gen(), status=r.status_code,
                        content_type=r.headers.get("Content-Type", "image/jpeg"))
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp
    except Exception:
        return "", 500


@bili_bp.route("/api/video")
def api_video():
    """下载 fnval=1 单文件 MP4"""
    bvid = request.args.get("bvid", "").strip()
    if not bvid.startswith("BV"):
        return "无效 bvid", 400
    try:
        info = client.s.get("https://api.bilibili.com/x/web-interface/view",
                            params={"bvid": bvid}, timeout=15).json()
        if info.get("code") != 0:
            return "详情失败: " + info.get("message", ""), 500
        d = info["data"]
        try: cid = int(request.args.get("cid", 0)) or d["cid"]
        except: cid = d["cid"]
        sp = client.sign({"bvid": bvid, "cid": cid, "qn": 80, "fnval": 1, "fourk": 1})
        r = client.s.get("https://api.bilibili.com/x/player/wbi/playurl",
                         params=sp, timeout=20).json()
        if r.get("code") != 0:
            return "播放地址失败: " + r.get("message", ""), 500
        durl = (r.get("data") or {}).get("durl") or []
        if not durl:
            return "无 durl", 500
        raw = durl[0]["url"]
        headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
        r2 = client.s.get(raw, headers=headers, stream=True, timeout=30)
        safe_title = "".join(c for c in d["title"] if c not in r'\\/:*?"<>|').strip()[:80] or bvid
        from urllib.parse import quote
        disp = f"attachment; filename*=UTF-8''{quote(safe_title + '.mp4')}"
        def gen():
            for chunk in r2.iter_content(chunk_size=64*1024):
                if chunk: yield chunk
        resp = Response(gen(), status=r2.status_code,
                        content_type=r2.headers.get("Content-Type", "video/mp4"))
        resp.headers["Content-Disposition"] = disp
        for h in ("Content-Length", "Accept-Ranges"):
            if h in r2.headers: resp.headers[h] = r2.headers[h]
        return resp
    except Exception as e:
        return "下载失败: " + str(e), 500

@bili_bp.route("/api/proxy")
def api_proxy():
    u = request.args.get("u", "")
    if not validate_remote_url(u, allowed_suffixes=("bilivideo.com", "bilivideo.cn", "hdslb.com", "bilibili.com")):
        return "bad url", 400
    headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
    rng = request.headers.get("Range")
    if rng:
        headers["Range"] = rng
    try:
        r = client.s.get(u, headers=headers, stream=True, timeout=(5, 30), allow_redirects=False)
    except Exception:
        logger.exception("video proxy request failed")
        return "upstream unavailable", 502
    def gen():
        try:
            for chunk in r.iter_content(chunk_size=64*1024):
                if chunk:
                    yield chunk
        finally:
            r.close()
    resp = Response(gen(), status=r.status_code,
                    content_type=r.headers.get("Content-Type", "video/mp4"))
    for h in ("Content-Range","Accept-Ranges","Content-Length"):
        if h in r.headers: resp.headers[h] = r.headers[h]
    resp.headers["Accept-Ranges"] = "bytes"
    resp.headers["Access-Control-Expose-Headers"] = "Content-Length, Content-Range, Accept-Ranges"
    return resp
