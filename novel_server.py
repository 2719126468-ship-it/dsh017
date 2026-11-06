#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
.bash_history .bashrc .cache .config .dsh .dsh-tui .gitconfig .local .npm .npmrc .profile .wget-hsts .zshrc __pycache__ a-stock-observer adult-anime-dl bili.log bili_console.py bili_server.py bili_wbi.py cache curl_cffi-0.13.0-cp39-abi3-manylinux_2_17_armv7l.manylinux2014_armv7l.whl diag.py downloader_native.py dsh-017-arm32 dsh-arm32-extras dsh-home dsh-patches-backup dsh-pojia-mode dsh-run.log dsh-tui-export-1791592633837.md fanqie.log fanqie_server.py fix_preset_registry.yml install_skills.mjs pojia.zip preview_ui.py restore-tmp run_bili.sh selftest.py test_bili.py test_multip.py test_search.py ubuntu-base-22.04.5-base-arm64.tar.gz 人物卡_RP写作模板.md 多人性爱实录.md 电子阅读器.py     Web v1 —— 暗色工业风 · 端口 8091
                                                  novel.snssdk.com 免签名端点，章节字体 PUA 密文用 charset.json 解密
"""
import os, re, json, time, urllib.parse, threading

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

from flask import Flask, request, jsonify, Response, render_template_string

try:
    from curl_cffi import requests as http_requests
    USE_CFFI = True
except ImportError:
    import requests as http_requests
    USE_CFFI = False

app = Flask(__name__)
from app.auth import install_auth
_auth_info = install_auth(app)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
BASE_HEADERS = {"User-Agent": UA, "Accept": "application/json, text/plain, */*",
                "Referer": "https://fanqienovel.com/"}

# ==================== HTTP 会话 ====================
class NovelClient:
    def __init__(self):
        self.s = http_requests.Session(impersonate="chrome120") if USE_CFFI else http_requests.Session()
        self.s.headers.update(BASE_HEADERS)
        self._charset = None
        self._charset_lock = threading.Lock()

    # ---------- 字体解密 ----------
    def load_charset(self):
        if self._charset is not None:
            return self._charset
        with self._charset_lock:
            if self._charset is not None:
                return self._charset
            local = "/root/novel_charset.json"
            candidates = [
                local,
                "https://raw.githubusercontent.com/ckenkuo/fanqie-cdp-downloader/main/charset.json",
                "https://raw.githubusercontent.com/zhoulianglen/fanqiexiaoshuo-Download/master/charset.json",
                "https://raw.githubusercontent.com/romcere/fanqienovel-decryptor/main/charset.json",
            ]
            for url in candidates:
                try:
                    if url.startswith("http"):
                        r = self.s.get(url, timeout=15)
                        if r.status_code != 200:
                            continue
                        data = r.json()
                    else:
                        if not os.path.exists(url):
                            continue
                        with open(url, "r", encoding="utf-8") as f:
                            data = json.load(f)
                    # 兼容不同格式：有的直接是 dict，有的包了一层
                    if isinstance(data, dict) and "charset" in data:
                        data = data["charset"]
                    if isinstance(data, dict) and data:
                        self._charset = data
                        if url.startswith("http"):
                            try:
                                with open(local, "w", encoding="utf-8") as f:
                                    json.dump(data, f, ensure_ascii=False)
                            except Exception:
                                pass
                        print(f"✅ charset.json 已加载（{len(data)} 条映射）")
                        return self._charset
                except Exception:
                    continue
            print("⚠️ charset.json 加载失败，章节将显示原始 PUA 密文")
            self._charset = {}
            return self._charset

    def decrypt(self, text):
        if not text:
            return text
        cs = self.load_charset()
        if not cs:
            return text
        # 番茄 PUA 密文通常是单个私用区字符，直接逐字替换
        out = []
        for ch in text:
            out.append(cs.get(ch, ch))
        return "".join(out)

    # ---------- 搜索 ----------
    def search(self, keyword, page=1, tab_type=3):
        import json
        offset = (page - 1) * 10

        # ========== 策略 1：第三方代理 IP（社区可用） ==========
        proxies = [
            ("proxy-101", "http://101.35.133.34:5000/api/search",
             {"query": keyword, "offset": offset}),
            ("proxy-112", "http://112.126.27.62:6889/api/search",
             {"query": keyword, "offset": offset, "platform": "fanqie"}),
        ]
        for name, url, params in proxies:
            try:
                r = self.s.get(url, params=params, timeout=15)
                if r.status_code == 200 and r.text.strip():
                    data = r.json()
                    books = self._extract_books(data)
                    if books:
                        print(f"✅ {name} 命中 {len(books)} 本")
                        return books
                    print(f"⚠️ {name} 结构不识别，前 300 字符: {r.text[:300]}")
                else:
                    print(f"⚠️ {name} HTTP {r.status_code}")
            except Exception as e:
                print(f"⚠️ {name} 异常: {type(e).__name__}: {str(e)[:80]}")

        # ========== 策略 2：novel.snssdk.com 免签名 tab/v ==========
        try:
            url = "https://novel.snssdk.com/reading/bookapi/search/tab/v"
            params = {
                "query": keyword, "tab_type": "3", "offset": offset,
                "aid": "2329", "device_platform": "android",
            }
            r = self.s.get(url, params=params, timeout=15)
            if r.status_code == 200 and r.text.strip():
                data = r.json()
                books = self._extract_tab_books(data)
                if books:
                    print(f"✅ snssdk-tab 命中 {len(books)} 本")
                    return books
                print(f"⚠️ snssdk-tab 结构不识别，前 300 字符: {r.text[:300]}")
            else:
                print(f"⚠️ snssdk-tab HTTP {r.status_code}, 响应 {len(r.text)}B")
        except Exception as e:
            print(f"⚠️ snssdk-tab 异常: {type(e).__name__}: {str(e)[:80]}")

        raise RuntimeError("所有搜索策略均失败（代理 + snssdk）")

    def _extract_books(self, data):
        """通用书籍列表提取"""
        if not isinstance(data, dict):
            if isinstance(data, list): return data
            return None
        for path in [["data","book_data"],["data","book_list"],["data","books"],
                     ["data","result"],["data","item_data"],["book_data"],
                     ["books"],["result"],["data","data"]]:
            cur = data
            for key in path:
                if isinstance(cur, dict): cur = cur.get(key)
                else: cur = None; break
            if isinstance(cur, list) and cur and isinstance(cur[0], dict):
                if any(k in cur[0] for k in ("book_id","bookId","id","book_name","title")):
                    return cur
        def deep(d, depth=0):
            if depth > 6: return None
            if isinstance(d, list) and d and isinstance(d[0], dict):
                if any(k in d[0] for k in ("book_id","bookId","id","book_name","title")):
                    return d
            if isinstance(d, dict):
                for v in d.values():
                    rr = deep(v, depth+1)
                    if rr: return rr
            return None
        return deep(data)

    def _extract_tab_books(self, data):
        """专门解析 tab/v 的 search_tabs 结构"""
        if not isinstance(data, dict): return None
        tabs = (data.get("data") or {}).get("search_tabs") or []
        for tab in tabs:
            if not isinstance(tab, dict): continue
            for key in ("search_book_data", "book_data", "data", "list"):
                v = tab.get(key)
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    if any(k in v[0] for k in ("book_id","bookId","id","book_name","title")):
                        return v
                if isinstance(v, dict):
                    for k2 in ("book_data", "list", "books"):
                        arr = v.get(k2)
                        if isinstance(arr, list) and arr:
                            return arr
        return self._extract_books(data)


    def _extract_books(self, data):
        if not isinstance(data, dict):
            if isinstance(data, list): return data
            return None

        # 番茄常见结构：data.book_data 或 data[0].content[*]
        candidates = []
        d = data.get("data")
        if isinstance(d, list) and d:
            candidates.append(d)
        if isinstance(d, dict):
            for k in ("book_data", "book_list", "books", "result", "item_data", "content"):
                v = d.get(k)
                if isinstance(v, list) and v:
                    candidates.append(v)

        # 顶层直接
        for k in ("book_data", "book_list", "books", "result"):
            v = data.get(k)
            if isinstance(v, list) and v:
                candidates.append(v)

        for arr in candidates:
            if arr and isinstance(arr[0], dict):
                if any(k in arr[0] for k in ("book_id","bookId","id","book_name","title")):
                    return arr

        # 深度递归兜底
        def deep(d, depth=0):
            if depth > 6: return None
            if isinstance(d, list) and d and isinstance(d[0], dict):
                if any(k in d[0] for k in ("book_id","bookId","id","book_name","title")):
                    return d
            if isinstance(d, dict):
                for v in d.values():
                    rr = deep(v, depth+1)
                    if rr: return rr
            return None
        return deep(data)


    def _extract_books(self, data):
        if not isinstance(data, dict):
            if isinstance(data, list): return data
            return None
        for path in [["data","book_data"],["data","book_list"],["data","books"],
                     ["data","result"],["data","item_data"],["book_data"],
                     ["books"],["result"]]:
            cur = data
            for key in path:
                if isinstance(cur, dict): cur = cur.get(key)
                else: cur = None; break
            if isinstance(cur, list) and cur and isinstance(cur[0], dict):
                if any(k in cur[0] for k in ("book_id","bookId","id","book_name","title")):
                    return cur
        def deep(d, depth=0):
            if depth > 5: return None
            if isinstance(d, list) and d and isinstance(d[0], dict):
                if any(k in d[0] for k in ("book_id","bookId","id","book_name","title")):
                    return d
            if isinstance(d, dict):
                for v in d.values():
                    rr = deep(v, depth+1)
                    if rr: return rr
            return None
        return deep(data)


    def _extract_books(self, data):
        if not isinstance(data, dict):
            if isinstance(data, list): return data
            return None
        for path in [["data","book_data"],["data","book_list"],["data","books"],
                     ["data","result"],["book_data"],["books"],["result"]]:
            cur = data
            for key in path:
                if isinstance(cur, dict): cur = cur.get(key)
                else: cur = None; break
            if isinstance(cur, list) and cur and isinstance(cur[0], dict):
                if any(k in cur[0] for k in ("book_id","bookId","id","book_name","title")):
                    return cur
        def deep(d, depth=0):
            if depth > 5: return None
            if isinstance(d, list) and d and isinstance(d[0], dict):
                if any(k in d[0] for k in ("book_id","bookId","id","book_name","title")):
                    return d
            if isinstance(d, dict):
                for v in d.values():
                    rr = deep(v, depth+1)
                    if rr: return rr
            return None
        return deep(data)


    def _extract_books(self, data):
        if not isinstance(data, dict):
            if isinstance(data, list): return data
            return None
        for path in [["data","book_data"],["data","book_list"],["data","books"],
                     ["data","result"],["book_data"],["books"],["result"]]:
            cur = data
            for key in path:
                if isinstance(cur, dict):
                    cur = cur.get(key)
                else:
                    cur = None; break
            if isinstance(cur, list) and cur and isinstance(cur[0], dict):
                if any(k in cur[0] for k in ("book_id","bookId","id","book_name","title")):
                    return cur
        def deep(d, depth=0):
            if depth > 5: return None
            if isinstance(d, list) and d and isinstance(d[0], dict):
                if any(k in d[0] for k in ("book_id","bookId","id","book_name","title")):
                    return d
            if isinstance(d, dict):
                for v in d.values():
                    rr = deep(v, depth+1)
                    if rr: return rr
            return None
        return deep(data)


    def _extract_books(self, data):
        """从各种响应结构中提取书籍列表"""
        if not isinstance(data, dict):
            if isinstance(data, list): return data
            return None
        
        # 尝试常见路径
        paths = [
            ["data", "book_data"],
            ["data", "book_list"],
            ["data", "books"],
            ["data", "result"],
            ["data", "item_data"],
            ["book_data"],
            ["books"],
            ["result"],
        ]
        for path in paths:
            cur = data
            for key in path:
                if isinstance(cur, dict):
                    cur = cur.get(key)
                else:
                    cur = None
                    break
            if isinstance(cur, list) and cur and isinstance(cur[0], dict):
                if any(k in cur[0] for k in ("book_id", "bookId", "id", "book_name", "title")):
                    return cur
        
        # 深度递归找第一个书籍列表
        def deep(d, depth=0):
            if depth > 5: return None
            if isinstance(d, list) and d and isinstance(d[0], dict):
                if any(k in d[0] for k in ("book_id", "bookId", "id", "book_name", "title")):
                    return d
            if isinstance(d, dict):
                for v in d.values():
                    r = deep(v, depth+1)
                    if r: return r
            return None
        return deep(data)


    def book_info(self, book_id):
        url = "https://novel.snssdk.com/api/novel/book/detail/v1/"
        try:
            r = self.s.get(url, params={"book_id": book_id,
                "device_platform": "android", "aid": "2329"}, timeout=15)
            data = r.json()
            return data.get("data") or data
        except Exception:
            return {}

    def catalog(self, book_id):
        url = "https://novel.snssdk.com/api/novel/book/directory/list/v1/"
        r = self.s.get(url, params={"book_id": book_id,
            "device_platform": "android", "aid": "2329"}, timeout=15)
        data = r.json()
        # 兼容多种结构
        chapters = []
        d = data.get("data") or data
        for key in ("chapter_list", "chapters", "list", "catalog"):
            v = d.get(key) if isinstance(d, dict) else None
            if isinstance(v, list):
                chapters = v
                break
        if not chapters and isinstance(d, list):
            chapters = d
        out = []
        for i, ch in enumerate(chapters):
            out.append({
                "item_id": str(ch.get("item_id") or ch.get("chapter_id") or ch.get("id") or ""),
                "title": ch.get("title") or ch.get("chapter_title") or f"第{i+1}章",
                "index": i + 1,
            })
        return out

    def content(self, item_id):
        url = "https://novel.snssdk.com/api/novel/book/reader/full/v1/"
        r = self.s.get(url, params={"item_id": item_id,
            "device_platform": "android", "aid": "2329",
            "parent_enterfrom": "novel_channel_search.tab."}, timeout=20)
        data = r.json()
        raw = ""
        d = data.get("data") or data
        for key in ("content", "chapter_content", "text"):
            v = d.get(key) if isinstance(d, dict) else None
            if isinstance(v, str) and v:
                raw = v
                break
        if not raw and isinstance(d, dict):
            for v in d.values():
                if isinstance(v, str) and len(v) > 50:
                    raw = v
                    break
        # 去掉 HTML 标签
        raw = re.sub(r"<[^>]+>", "", raw or "")
        raw = raw.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
        return self.decrypt(raw).strip()

client = NovelClient()

# ==================== API ====================
@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"code": -1, "message": "请输入关键词"})
    try:
        page = int(request.args.get("page", 1))
    except Exception:
        page = 1
    try:
        books = client.search(q, page)
        out = []
        for b in books:
            out.append({
                "book_id": str(b.get("book_id") or b.get("id") or ""),
                "title": b.get("book_name") or b.get("title") or "未知书名",
                "author": b.get("author") or b.get("author_name") or "未知作者",
                "cover": (b.get("thumb_url") or b.get("cover_url") or b.get("cover") or "").replace("http://", "https://"),
                "abstract": b.get("abstract") or b.get("description") or "",
            })
        return jsonify({"code": 0, "books": out, "page": page})
    except Exception as e:
        return jsonify({"code": -500, "message": str(e)})

@app.route("/api/book")
def api_book():
    book_id = request.args.get("book_id", "").strip()
    if not book_id:
        return jsonify({"code": -1, "message": "缺少 book_id"})
    try:
        info = client.book_info(book_id)
        chapters = client.catalog(book_id)
        return jsonify({
            "code": 0,
            "book_id": book_id,
            "title": info.get("book_name") or info.get("title") or "",
            "author": info.get("author") or info.get("author_name") or "",
            "cover": (info.get("thumb_url") or info.get("cover_url") or "").replace("http://", "https://"),
            "abstract": info.get("abstract") or "",
            "chapters": chapters,
        })
    except Exception as e:
        return jsonify({"code": -500, "message": str(e)})

@app.route("/api/content")
def api_content():
    item_id = request.args.get("item_id", "").strip()
    if not item_id:
        return jsonify({"code": -1, "message": "缺少 item_id"})
    try:
        text = client.content(item_id)
        return jsonify({"code": 0, "item_id": item_id, "content": text})
    except Exception as e:
        return jsonify({"code": -500, "message": str(e)})

@app.route("/api/img")
def api_img():
    u = request.args.get("u", "")
    if not u.startswith("http"):
        return "", 400
    try:
        r = client.s.get(u, headers={"User-Agent": UA, "Referer": "https://fanqienovel.com/"},
                         timeout=15, stream=True)
        def gen():
            for chunk in r.iter_content(chunk_size=32 * 1024):
                if chunk:
                    yield chunk
        resp = Response(gen(), status=r.status_code,
                        content_type=r.headers.get("Content-Type", "image/jpeg"))
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp
    except Exception:
        return "", 500

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "novel", "port": 8091})

# ==================== 前端 ====================
HTML = r'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>番茄小说 · Novel</title>
<style>
:root{
  --bg:#0a0a0a; --surface:#141413;
  --text:#faf9f5; --text-2:#b0aea5; --muted:#6b6a63;
  --line:hsla(0,0%,100%,.08); --line-2:hsla(0,0%,100%,.12);
  --glass-bg:hsla(0,0%,100%,.045);
  --glass-border:hsla(0,0%,100%,.09);
  --accent:#E5484D;
  --ease:cubic-bezier(.16,1,.3,1);
}
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{background:var(--bg);color:var(--text);
  font-family:-apple-system,"Noto Sans SC",sans-serif;
  letter-spacing:-.02em;-webkit-font-smoothing:antialiased;overflow-x:hidden}
body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:radial-gradient(ellipse 55% 45% at 15% 0%, rgba(229,72,77,.06), transparent 65%),
             radial-gradient(ellipse 50% 40% at 85% 100%, rgba(217,119,87,.05), transparent 65%);}
.wrap{max-width:860px;margin:0 auto;padding:0 16px 80px}
header{position:sticky;top:0;z-index:20;padding:14px 0 12px;
  background:rgba(10,10,10,.72);border-bottom:1px solid var(--line);
  transition:padding .28s var(--ease),background .28s var(--ease)}
@supports ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){
  header{backdrop-filter:blur(16px) saturate(1.5);-webkit-backdrop-filter:blur(16px) saturate(1.5)}}
header.compact{padding:8px 0 7px;background:rgba(0,0,0,.85)}
.brand{margin-bottom:12px;transition:margin .28s var(--ease)}
header.compact .brand{margin-bottom:8px}
.brand h1{font-size:18px;font-weight:600;letter-spacing:-.04em;
  font-family:Georgia,"Noto Serif SC",serif;display:inline}
.brand span{font-family:monospace;font-size:9px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--muted);margin-left:10px}
.bar{display:flex}
.bar input{flex:1;min-width:0;background:var(--surface);border:1px solid var(--line-2);
  border-radius:11px;padding:11px 14px;color:var(--text);font-size:14px;outline:none;
  margin-right:8px;transition:border-color .22s var(--ease),box-shadow .22s var(--ease)}
.bar input::placeholder{color:var(--muted)}
.bar input:focus{border-color:rgba(229,72,77,.55);box-shadow:0 0 0 4px rgba(229,72,77,.10)}
.bar button{flex-shrink:0;background:var(--accent);color:#1a0f0a;border:0;
  border-radius:11px;padding:0 20px;font-size:13px;font-weight:600;cursor:pointer;
  transition:filter .15s var(--ease)}
.status{display:flex;align-items:center;gap:8px;font-family:monospace;
  font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);
  margin:22px 2px 14px;min-height:16px;transition:color .2s var(--ease)}
.status.active{color:var(--accent)}
.book{display:flex;padding:11px;border-radius:16px;background:var(--glass-bg);
  border:1px solid var(--glass-border);margin-bottom:9px;text-decoration:none;
  color:inherit;box-shadow:inset 0 1px 0 hsla(0,0%,100%,.06);position:relative;
  overflow:hidden;opacity:0;transform:translateY(14px);
  animation:cardIn .5s var(--ease) forwards;
  transition:background .18s var(--ease),border-color .18s var(--ease)}
@supports ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){
  .book{backdrop-filter:blur(14px) saturate(1.3);-webkit-backdrop-filter:blur(14px) saturate(1.3)}}
.book:active{background:hsla(0,0%,100%,.085);border-color:rgba(229,72,77,.45)}
.book::before{content:"";position:absolute;left:0;top:14px;bottom:14px;width:2px;
  border-radius:2px;background:var(--accent);opacity:0;transform:scaleY(.3);
  transition:opacity .2s var(--ease),transform .2s var(--ease)}
.book:active::before{opacity:1;transform:scaleY(1)}
@keyframes cardIn{to{opacity:1;transform:translateY(0)}}
.cover{width:72px;height:96px;border-radius:10px;flex-shrink:0;background:#22221f;
  overflow:hidden;margin-right:13px}
.cover img{width:100%;height:100%;object-fit:cover;display:block}
.meta{flex:1;min-width:0;display:flex;flex-direction:column;justify-content:center;gap:5px}
.title{font-size:14px;line-height:1.35;font-weight:500;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.author{font-family:monospace;font-size:10px;letter-spacing:.06em;color:var(--muted);
  text-transform:uppercase}
.abstract{font-size:12px;line-height:1.45;color:var(--text-2);
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.empty{text-align:center;padding:64px 0;color:var(--muted);font-family:monospace;
  font-size:11px;letter-spacing:.12em}
.more-wrap{display:flex;justify-content:center;margin-top:18px}
.more{background:hsla(0,0%,100%,.03);border:1px solid var(--line-2);border-radius:13px;
  padding:12px 26px;color:var(--text-2);font-family:monospace;font-size:11px;
  letter-spacing:.12em;text-transform:uppercase;cursor:pointer;
  transition:border-color .22s var(--ease),color .22s var(--ease)}
.more:hover{border-color:rgba(229,72,77,.55);color:var(--accent)}
@media(prefers-reduced-motion:reduce){
  *{animation-duration:.01ms!important;transition-duration:.01ms!important}
  .book{opacity:1;transform:none}}
</style></head><body>
<div class="wrap">
  <header id="hdr">
    <div class="brand"><h1>番茄小说</h1><span>novel · console</span></div>
    <div class="bar">
      <input id="q" placeholder="搜索书名、作者…" autocomplete="off">
      <button id="go">搜索</button>
    </div>
  </header>
  <div class="status" id="status">ready · 输入关键词开始搜索</div>
  <div id="list"></div>
  <div class="more-wrap" id="moreWrap"></div>
</div>
<script>
(function(){
  var list=document.getElementById("list"),status=document.getElementById("status"),
      q=document.getElementById("q"),hdr=document.getElementById("hdr"),
      go=document.getElementById("go"),moreWrap=document.getElementById("moreWrap");
  var ST={q:"",page:0,loading:false};
  var lastY=0;
  window.addEventListener("scroll",function(){
    var y=window.pageYOffset;
    if(y>lastY&&y>40)hdr.classList.add("compact");
    else if(y<lastY-10)hdr.classList.remove("compact");
    lastY=y;
  },{passive:true});
  function esc(s){return(s||"").replace(/[&<>"]/g,function(c){
    return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
  function readQ(){var m=location.search.match(/[?&]q=([^&]*)/);
    if(!m)return null;try{return decodeURIComponent(m[1].replace(/\+/g," "))}catch(e){return null}}
  function writeQ(kw){try{if(history.replaceState)
    history.replaceState(null,"","?q="+encodeURIComponent(kw))}catch(e){}}
  function setMore(mode){
    moreWrap.innerHTML="";
    if(mode==="more"){
      var b=document.createElement("button");b.className="more";b.textContent="load more";
      b.addEventListener("click",function(){ if(!ST.loading) fetchPage(ST.page+1,true); });
      moreWrap.appendChild(b);
    }else if(mode==="loading"){
      var b2=document.createElement("button");b2.className="more";b2.textContent="loading…";
      moreWrap.appendChild(b2);
    }
  }
  function fetchPage(page, append){
    if(ST.loading)return; ST.loading=true;
    if(!append){ list.innerHTML=""; status.className="status active";
      status.textContent="searching…"; moreWrap.innerHTML=""; }
    else setMore("loading");
    fetch("/api/search?q="+encodeURIComponent(ST.q)+"&page="+page)
      .then(function(r){return r.json()})
      .then(function(j){
        ST.loading=false;
        if(j.code!==0)throw new Error(j.message||("code "+j.code));
        var books=j.books||[];
        ST.page=page; writeQ(ST.q);
        render(books,append);
        var loaded=list.children.length;
        if(books.length>=10) setMore("more"); else setMore("end");
        status.className="status";
        status.textContent=loaded+" 本 · p"+ST.page;
      })
      .catch(function(e){
        ST.loading=false; status.className="status";
        status.textContent="error · "+e.message;
        if(!append) list.innerHTML='<div class="empty">搜索失败</div>';
      });
  }
  function render(books,append){
    if(!append) list.innerHTML="";
    if(!books.length&&!append){ list.innerHTML='<div class="empty">NO RESULT</div>'; return; }
    var base=list.children.length;
    books.forEach(function(b,i){
      var a=document.createElement("a"); a.className="book";
      a.href="/book/"+b.book_id;
      a.style.animationDelay=(i*35)+"ms";
      var pic=b.cover||"";
      a.innerHTML=
        '<div class="cover">'+(pic?'<img src="/api/img?u='+encodeURIComponent(pic)+'" loading="lazy" onerror="this.style.display=\'none\'">':"")+'</div>'+
        '<div class="meta"><div class="title">'+esc(b.title)+'</div>'+
        '<div class="author">'+esc(b.author)+'</div>'+
        '<div class="abstract">'+esc(b.abstract||"")+'</div></div>';
      list.appendChild(a);
    });
  }
  function newSearch(){
    var kw=q.value.trim();
    if(!kw){ status.className="status"; status.textContent="请输入关键词"; return; }
    ST.q=kw; ST.page=0; fetchPage(1,false);
  }
  go.addEventListener("click",function(e){e.preventDefault();newSearch()});
  q.addEventListener("keydown",function(e){if(e.key==="Enter"){e.preventDefault();newSearch()}});
  var urlQ=readQ(); if(urlQ){q.value=urlQ; ST.q=urlQ; fetchPage(1,false);}
})();
</script></body></html>'''

@app.route("/")
def index(): return HTML

# 书籍详情页（目录）
BOOK_HTML = r'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>书籍</title>
<style>
:root{--bg:#0a0a0a;--surface:#141413;--text:#faf9f5;--text-2:#b0aea5;
  --muted:#6b6a63;--line:hsla(0,0%,100%,.08);--line-2:hsla(0,0%,100%,.12);
  --accent:#E5484D;--ease:cubic-bezier(.16,1,.3,1)}
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:var(--bg);color:var(--text);
  font-family:-apple-system,"Noto Sans SC",sans-serif;letter-spacing:-.02em}
.wrap{max-width:720px;margin:0 auto;padding:0 16px 80px}
.hero{display:flex;gap:16px;padding:24px 0 18px;border-bottom:1px solid var(--line)}
.hero .cover{width:96px;height:128px;border-radius:12px;flex-shrink:0;background:#22221f;overflow:hidden}
.hero .cover img{width:100%;height:100%;object-fit:cover;display:block}
.hero .info{flex:1;min-width:0;display:flex;flex-direction:column;justify-content:center;gap:6px}
.hero h1{font-size:18px;font-weight:600;line-height:1.3;letter-spacing:-.03em}
.hero .author{font-family:monospace;font-size:10px;letter-spacing:.08em;
  color:var(--muted);text-transform:uppercase}
.hero .abstract{font-size:12px;line-height:1.5;color:var(--text-2);
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.chapters{margin-top:8px}
.ch{display:flex;align-items:center;padding:13px 4px;border-bottom:1px solid var(--line);
  text-decoration:none;color:var(--text-2);font-size:13px;
  transition:color .18s var(--ease),background .18s var(--ease)}
.ch:active{color:var(--accent);background:hsla(229,72,77,.04)}
.ch .idx{font-family:monospace;font-size:10px;color:var(--muted);
  min-width:36px;letter-spacing:.04em}
.back{display:inline-block;padding:18px 0 8px;color:var(--accent);
  font-family:monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase;
  text-decoration:none}
.empty{text-align:center;padding:40px 0;color:var(--muted);font-family:monospace;font-size:11px}
</style></head><body>
<div class="wrap" id="app"><div class="empty">loading…</div></div>
<script>
(function(){
  var bookId=location.pathname.split("/").pop();
  var app=document.getElementById("app");
  function esc(s){return(s||"").replace(/[&<>"]/g,function(c){
    return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
  fetch("/api/book?book_id="+encodeURIComponent(bookId))
    .then(function(r){return r.json()})
    .then(function(j){
      if(j.code!==0)throw new Error(j.message||"code "+j.code);
      var pic=j.cover||"";
      var h='<a class="back" href="javascript:history.back()">← back</a>'+
        '<div class="hero"><div class="cover">'+(pic?'<img src="/api/img?u='+encodeURIComponent(pic)+'" onerror="this.style.display=\'none\'">':"")+'</div>'+
        '<div class="info"><h1>'+esc(j.title)+'</h1><div class="author">'+esc(j.author)+'</div>'+
        '<div class="abstract">'+esc(j.abstract||"")+'</div></div></div>'+
        '<div class="chapters">';
      if(!j.chapters||!j.chapters.length){ h+='<div class="empty">暂无目录</div>'; }
      else j.chapters.forEach(function(ch){
        h+='<a class="ch" href="/read/'+encodeURIComponent(ch.item_id)+'?book='+encodeURIComponent(bookId)+'">'+
           '<span class="idx">'+ch.index+'</span><span>'+esc(ch.title)+'</span></a>';
      });
      h+='</div>'; app.innerHTML=h;
      document.title=j.title;
    })
    .catch(function(e){ app.innerHTML='<div class="empty">加载失败: '+esc(e.message)+'</div>'; });
})();
</script></body></html>'''

@app.route("/book/<book_id>")
def book_page(book_id): return BOOK_HTML

# 阅读页
READ_HTML = r'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>阅读</title>
<style>
:root{--bg:#0a0a0a;--surface:#141413;--text:#faf9f5;--text-2:#b0aea5;
  --muted:#6b6a63;--line:hsla(0,0%,100%,.08);--accent:#E5484D;
  --ease:cubic-bezier(.16,1,.3,1)}
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:var(--bg);color:var(--text);
  font-family:"Noto Serif SC",Georgia,-apple-system,serif;
  letter-spacing:.01em;-webkit-font-smoothing:antialiased}
.wrap{max-width:720px;margin:0 auto;padding:0 20px 100px}
.topbar{position:sticky;top:0;z-index:10;display:flex;align-items:center;
  padding:12px 0;background:rgba(10,10,10,.85);border-bottom:1px solid var(--line);
  gap:10px;font-family:-apple-system,sans-serif}
.topbar a{color:var(--accent);text-decoration:none;font-family:monospace;
  font-size:11px;letter-spacing:.1em;text-transform:uppercase}
.topbar .title{flex:1;font-size:12px;color:var(--muted);overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap;text-align:center}
.topbar .size{font-family:monospace;font-size:10px;color:var(--muted);cursor:pointer}
#content{font-size:17px;line-height:1.85;color:var(--text);padding-top:24px;
  white-space:pre-wrap;word-break:break-word}
#content.loading{color:var(--muted);font-family:monospace;font-size:12px;text-align:center;padding-top:60px}
.err{color:var(--accent);font-family:monospace;font-size:12px;padding-top:40px;text-align:center}
.nav{display:flex;justify-content:space-between;margin-top:40px;
  font-family:-apple-system,sans-serif}
.nav a{color:var(--accent);text-decoration:none;font-family:monospace;font-size:11px;
  letter-spacing:.08em;text-transform:uppercase;padding:10px 0}
</style></head><body>
<div class="wrap">
  <div class="topbar">
    <a href="javascript:history.back()">← 目录</a>
    <span class="title" id="ttl"></span>
    <span class="size" id="size">Aa</span>
  </div>
  <div id="content" class="loading">loading…</div>
  <div class="nav" id="nav"></div>
</div>
<script>
(function(){
  var itemId=location.pathname.split("/").pop();
  var qs=location.search, bookId="";
  var m=qs.match(/[?&]book=([^&]*)/); if(m) bookId=decodeURIComponent(m[1]);
  var content=document.getElementById("content"),ttl=document.getElementById("ttl"),
      sizeEl=document.getElementById("size"),nav=document.getElementById("nav");
  var sizes=[15,17,19,21,23], si=1;
  try{ var s=localStorage.getItem("novel_size"); if(s){ si=parseInt(s,10)||1; } }catch(e){}
  function applySize(){ content.style.fontSize=sizes[si]+"px"; }
  applySize();
  sizeEl.addEventListener("click",function(){
    si=(si+1)%sizes.length; applySize();
    try{ localStorage.setItem("novel_size",String(si)); }catch(e){}
  });
  function esc(s){return(s||"").replace(/[&<>"]/g,function(c){
    return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
  fetch("/api/content?item_id="+encodeURIComponent(itemId))
    .then(function(r){return r.json()})
    .then(function(j){
      if(j.code!==0)throw new Error(j.message||"code "+j.code);
      content.classList.remove("loading");
      content.textContent=j.content||"（本章为空或需要登录）";
      document.title="阅读 · "+itemId;
      if(bookId){
        nav.innerHTML='<a href="/book/'+encodeURIComponent(bookId)+'">← 返回目录</a>';
      }
    })
    .catch(function(e){
      content.classList.remove("loading");
      content.innerHTML='<div class="err">加载失败: '+esc(e.message)+'</div>';
    });
})();
</script></body></html>'''

@app.route("/read/<item_id>")
def read_page(item_id): return READ_HTML

if __name__ == "__main__":
    print(f"📖 番茄小说 Web: http://{_lan_ip()}:8091/")
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=8091, threads=6, channel_timeout=120)
    except ImportError:
        app.run(host="0.0.0.0", port=8091, threaded=True)
