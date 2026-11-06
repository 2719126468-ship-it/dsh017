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
            f.write(body.get("content", ""))
        return jsonify({"code": 0, "name": name})
    except Exception as e:
        return jsonify({"code": -500, "message": str(e)})

@chat_bp.route("/api/preset/<name>")
def api_preset(name):
    import os
    if "/" in name or ".." in name:
        return jsonify({"code": -1, "message": "非法名称"})
    path = os.path.join(_PRESET_DIR, name + ".txt")
    if not os.path.exists(path):
        return jsonify({"code": -1, "message": "预设不存在"})
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return jsonify({"code": 0, "name": name, "content": content})
    except Exception as e:
        return jsonify({"code": -500, "message": str(e)})

# ==================== 聊天预设结束 ====================

@chat_bp.route("/api/x")
def api_x():
    """通过 FxTwitter 解析单条推文，无需登录"""
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"code": -1, "message": "请提供推文 URL"})
    from urllib.parse import urlsplit
    import re
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or (parsed.hostname or "").lower() not in
            ("x.com", "www.x.com", "twitter.com", "www.twitter.com") or
            not re.fullmatch(r"/[^/]+/status/\d+/?", parsed.path)):
        return jsonify({"code": -1, "message": "仅支持有效的 X/Twitter 推文链接"}), 400
    if parsed.query or parsed.fragment:
        return jsonify({"code": -1, "message": "推文链接不能包含额外参数"}), 400
    api_url = "https://api.fxtwitter.com" + parsed.path
    try:
        r = client.s.get(api_url, timeout=(5, 15), allow_redirects=False)
        data = r.json()
        if data.get("code") == 200:
            t = data.get("tweet", {})
            return jsonify({
                "code": 0,
                "author": t.get("author", {}).get("screen_name", "?"),
                "text": t.get("text", ""),
                "likes": t.get("likes", 0),
                "retweets": t.get("retweets", 0),
                "created_at": t.get("created_at", ""),
                "url": url
            })
        else:
            return jsonify({"code": -1, "message": f"FxTwitter 返回 code={data.get('code')}"})
    except Exception as e:
        return jsonify({"code": -500, "message": str(e)})


@chat_bp.route("/api/hn")
def api_hn():
    """拉取 Hacker News 头条，官方 Firebase API，无需认证"""
    try:
        limit = int(request.args.get("limit", 10))
        top_ids = client.s.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10).json()
        stories = []
        for sid in top_ids[:limit]:
            item = client.s.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5).json()
            if item and item.get("type") == "story":
                stories.append({
                    "id": sid,
                    "title": item.get("title", ""),
                    "url": item.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                    "score": item.get("score", 0),
                    "by": item.get("by", "?"),
                    "time": item.get("time", 0)
                })
        return jsonify({"code": 0, "stories": stories})
    except Exception as e:
        return jsonify({"code": -500, "message": str(e)})

# ==================== 预设管理 UI ====================
PRESETS_HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Presets</title><style>
body{background:#0a0a0a;color:#faf9f5;font-family:-apple-system,sans-serif;max-width:720px;margin:0 auto;padding:16px}
h1{font-size:16px;margin:0 0 12px}
.bar{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;align-items:center}
select,button{background:#141413;color:#faf9f5;border:1px solid hsla(0,0%,100%,.12);border-radius:8px;padding:8px 12px;font-size:13px;font-family:inherit}
button.primary{background:#d97757;color:#1a0f0a;border:0;font-weight:600}
button.danger{color:#E5484D}
textarea{width:100%;min-height:300px;background:#141413;color:#faf9f5;border:1px solid hsla(0,0%,100%,.12);border-radius:10px;padding:12px;font-family:monospace;font-size:13px;line-height:1.6;box-sizing:border-box;outline:none}
textarea:focus{border-color:rgba(217,119,87,.5)}
#nameIn{width:100%;background:#141413;color:#faf9f5;border:1px solid hsla(0,0%,100%,.12);border-radius:8px;padding:10px 12px;font-size:13px;box-sizing:border-box;margin-bottom:10px;outline:none}
.status{font-family:monospace;font-size:11px;color:#6b6a63;margin-top:8px;min-height:16px}
a{color:#d97757;text-decoration:none;font-family:monospace;font-size:11px}
</style></head><body>
<h1>预设管理</h1>
<div class="bar">
  <select id="sel"><option value="">— 选择 —</option></select>
  <button class="primary" id="newBtn">+ 新建</button>
  <button id="saveBtn">保存</button>
  <button class="danger" id="delBtn">删除</button>
  <a href="/chat">← 聊天</a>
</div>
<input id="nameIn" placeholder="预设名（英文或中文，不用 .txt）">
<textarea id="ta" placeholder="系统提示词内容…"></textarea>
<div class="status" id="st"></div>
<script>
var sel=document.getElementById('sel'),ta=document.getElementById('ta'),
    nameIn=document.getElementById('nameIn'),st=document.getElementById('st');
function loadList(){
  fetch('/api/presets').then(r=>r.json()).then(j=>{
    sel.innerHTML='<option value="">— 选择 —</option>';
    (j.items||[]).forEach(it=>{
      var o=document.createElement('option');o.value=it.name;o.textContent=it.name;sel.appendChild(o);
    });
  });
}
sel.addEventListener('change',()=>{
  var n=sel.value;
  if(!n){ta.value='';nameIn.value='';return;}
  fetch('/api/preset/'+encodeURIComponent(n)).then(r=>r.json()).then(j=>{
    if(j.code===0){ta.value=j.content;nameIn.value=j.name;st.textContent='已加载: '+j.name;}
  });
});
document.getElementById('newBtn').onclick=()=>{
  ta.value='';nameIn.value='';nameIn.focus();st.textContent='新建模式';
};
document.getElementById('saveBtn').onclick=()=>{
  var n=nameIn.value.trim();
  if(!n){st.textContent='请填预设名';return;}
  fetch('/api/preset/'+encodeURIComponent(n),{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({content:ta.value})})
    .then(r=>r.json()).then(j=>{
      if(j.code===0){st.textContent='✅ 已保存: '+n;loadList();}
      else st.textContent='❌ '+(j.message||j.code);
    });
};
document.getElementById('delBtn').onclick=()=>{
  var n=nameIn.value.trim();
  if(!n){st.textContent='请先选择或填预设名';return;}
  if(!confirm('确认删除 '+n+' ？'))return;
  fetch('/api/preset/'+encodeURIComponent(n),{method:'DELETE'})
    .then(r=>r.json()).then(j=>{
      if(j.code===0){st.textContent='✅ 已删除';ta.value='';nameIn.value='';loadList();}
      else st.textContent='❌ '+(j.message||j.code);
    });
};
loadList();
</script></body></html>"""


@chat_bp.route("/presets")
def presets_page(): return PRESETS_HTML

# ==================== AI 视频总结（视觉+文本双引擎） ====================
@chat_bp.route("/api/summarize", methods=["POST"])
def api_summarize():
    import base64
    body = request.get_json(force=True, silent=True) or {}
    bvid = (body.get("bvid") or "").strip()
    vision = bool(body.get("vision", True))
    if not bvid.startswith("BV"):
        return jsonify({"code": -1, "message": "无效 bvid"})

    try:
        info = client.s.get("https://api.bilibili.com/x/web-interface/view",
                            params={"bvid": bvid}, timeout=15).json()
        if info.get("code") != 0:
            return jsonify({"code": -1, "message": "获取视频信息失败"})
        d = info["data"]
        title = d.get("title", "")
        desc = d.get("desc", "") or "（无简介）"
        cover = d.get("pic", "")
    except Exception as e:
        return jsonify({"code": -500, "message": str(e)})

    headers = {"Authorization": "Bearer " + ZHIPU_API_KEY,
               "Content-Type": "application/json"}

    visual = ""
    if vision and cover:
        try:
            img_r = client.s.get(cover, headers={"Referer": "https://www.bilibili.com/"}, timeout=20)
            img_b64 = base64.b64encode(img_r.content).decode()
            img_data = "data:image/jpeg;base64," + img_b64
            v_payload = {
                "model": "glm-4.6v-flash",
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": "请详细描述这张图片中的场景、人物和关键视觉信息，100字以内。"},
                    {"type": "image_url", "image_url": {"url": img_data}}
                ]}],
                "stream": False, "max_tokens": 300,
            }
            vr = client.s.post(ZHIPU_BASE, headers=headers, json=v_payload, timeout=60).json()
            if vr.get("choices"):
                visual = vr["choices"][0]["message"]["content"]
        except Exception:
            visual = ""

    system = "你是一个视频内容总结助手。根据提供的视频信息，生成简洁、结构化的总结。包含：核心主题、主要内容、适合人群。用中文，200字以内。"
    user = "视频标题：%s\n视频简介：%s\n%s\n请总结这个视频。" % (
        title, desc, ("画面分析：" + visual) if visual else "")
    t_payload = {
        "model": "glm-4.7-flash",
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False, "temperature": 0.5, "max_tokens": 1500,
    }
    import time as _t
    summary = None
    for attempt in range(3):
        try:
            tr = client.s.post(ZHIPU_BASE, headers=headers, json=t_payload, timeout=90).json()
            if tr.get("choices"):
                msg = tr["choices"][0]["message"]
                c = msg.get("content") or ""
                r = msg.get("reasoning_content") or ""
                summary = c if c.strip() else (r if r.strip() else "")
                if summary:
                    break
            err_str = str(tr)
            if "1305" in err_str or "overloaded" in err_str.lower():
                if attempt < 2:
                    _t.sleep(1.5 * (attempt + 1))
                    continue
            summary = "总结生成失败：" + err_str[:200]
            break
        except Exception as e:
            if attempt < 2:
                _t.sleep(1.5 * (attempt + 1))
                continue
            return jsonify({"code": -500, "message": "文本总结失败: " + str(e)})

    if not summary:
        summary = "（模型返回空内容，稍后重试或换模型）"
    return jsonify({"code": 0, "bvid": bvid, "title": title,
                    "visual_used": bool(visual), "visual": visual,
                    "summary": summary})
