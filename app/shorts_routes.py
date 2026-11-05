#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shorts 短视频流：/api/shorts + SHORTS_HTML + /shorts"""
import os
import json
import urllib.parse
from flask import Blueprint, request, jsonify
from app.bili_client import client, UA

shorts_bp = Blueprint('shorts', __name__)

@shorts_bp.route("/api/shorts")
def api_shorts():
    """短视频列表：复用 B 站搜索（按播放量排序），返回精简结构"""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"code": -1, "message": "请输入关键词"})
    try:
        page = int(request.args.get("page", 1))
    except Exception:
        page = 1
    try:
        data = client.search(q, page, order="click")
        if data.get("code") != 0:
            return jsonify({"code": data.get("code"),
                            "message": data.get("message", "")})
        items = (data.get("data") or {}).get("result") or []
        shorts = []
        for v in items:
            if v.get("type") != "video":
                continue
            if not v.get("bvid"):
                continue
            pic = v.get("pic") or ""
            if pic.startswith("//"): pic = "https:" + pic
            shorts.append({
                "bvid": v.get("bvid", ""),
                "title": (v.get("title") or "").replace('<em class="keyword">', '').replace('</em>', ''),
                "author": v.get("author", ""),
                "cover": pic,
                "duration": v.get("duration", ""),
                "play": v.get("play", 0),
            })
        return jsonify({"code": 0, "items": shorts, "page": page})
    except Exception as e:
        return jsonify({"code": -500, "message": str(e)})


SHORTS_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Shorts</title>
<style>
:root{--bg:#000;--text:#faf9f5;--clay:#d97757;--muted:#6b6a63}
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{background:var(--bg);color:var(--text);
  font-family:-apple-system,"Noto Sans SC",sans-serif;overflow:hidden}
.shorts-container{height:100vh;height:100dvh;overflow-y:scroll;overflow-x:hidden;
  scroll-snap-type:y mandatory;-webkit-overflow-scrolling:touch;
  scrollbar-width:none;touch-action:pan-y}
.shorts-container::-webkit-scrollbar{display:none}
.video-item{height:100vh;height:100dvh;flex:0 0 100vh;
  scroll-snap-align:start;scroll-snap-stop:always;
  position:relative;display:flex;align-items:center;justify-content:center;
  background:#000;overflow:hidden}
.video-item video{width:100%;height:100%;object-fit:contain;display:block;
  position:relative;z-index:1}
.video-item .bg-cover{position:absolute;inset:0;background-size:cover;
  background-position:center;filter:brightness(.25);z-index:0}
.overlay{position:absolute;inset:0;z-index:2;pointer-events:none;
  display:flex;flex-direction:column;justify-content:space-between;
  padding:16px;padding-top:calc(16px + env(safe-area-inset-top,0));
  padding-bottom:calc(16px + env(safe-area-inset-bottom,0))}
.overlay .info{margin-top:auto;margin-bottom:24px;max-width:80%}
.overlay .title{font-size:15px;font-weight:500;line-height:1.35;
  text-shadow:0 1px 4px rgba(0,0,0,.9);margin-bottom:6px;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.overlay .author{font-family:monospace;font-size:11px;letter-spacing:.06em;
  color:rgba(255,255,255,.75);text-transform:uppercase;
  text-shadow:0 1px 4px rgba(0,0,0,.9)}
.overlay .bottom{position:absolute;right:16px;bottom:100px;
  display:flex;flex-direction:column;gap:18px;align-items:center}
.action{width:46px;height:46px;border-radius:50%;background:rgba(0,0,0,.65);
  border:1px solid rgba(255,255,255,.2);display:flex;align-items:center;
  justify-content:center;color:#fff;font-size:18px;
  pointer-events:auto;cursor:pointer;
  transition:transform .12s ease}
.action:active{transform:scale(.9)}
.heart{position:absolute;pointer-events:none;font-size:90px;
  color:#E5484D;z-index:10;animation:heartPop .8s cubic-bezier(.2,.8,.3,1) forwards;
  text-shadow:0 0 24px rgba(229,72,77,.6)}
@keyframes heartPop{
  0%{opacity:0;transform:translate(-50%,-50%) scale(0)}
  30%{opacity:1;transform:translate(-50%,-50%) scale(1.3)}
  100%{opacity:0;transform:translate(-50%,-85%) scale(1.7)}
}
.loading{position:absolute;inset:0;display:flex;align-items:center;
  justify-content:center;color:#fff;font-family:monospace;font-size:12px;
  letter-spacing:.1em;z-index:3;pointer-events:none;flex-direction:column;gap:12px}
.spinner{width:36px;height:36px;border:2px solid rgba(255,255,255,.2);
  border-top-color:var(--clay);border-radius:50%;
  animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.back-btn{position:fixed;top:16px;left:16px;z-index:20;
  width:36px;height:36px;border-radius:50%;
  background:rgba(0,0,0,.75);border:1px solid rgba(255,255,255,.2);
  color:#fff;display:flex;align-items:center;justify-content:center;
  text-decoration:none;font-size:16px;transition:transform .12s ease}
.back-btn:active{transform:scale(.9)}
.search-bar{position:fixed;top:16px;left:64px;right:16px;z-index:20;
  display:flex;gap:8px}
.search-bar input{flex:1;background:rgba(0,0,0,.75);
  border:1px solid rgba(255,255,255,.2);border-radius:20px;
  padding:9px 16px;color:#fff;font-size:13px;outline:none}
.search-bar input::placeholder{color:rgba(255,255,255,.5)}
.search-bar input:focus{border-color:rgba(217,119,87,.6);
  box-shadow:0 0 0 3px rgba(217,119,87,.15)}
</style></head>
<body>
<a class="back-btn" href="/">←</a>
<div class="search-bar"><input id="q" placeholder="搜索短视频…" autocomplete="off"></div>
<div class="shorts-container" id="container"></div>
<script>
(function(){
  var container = document.getElementById('container');
  var qInput = document.getElementById('q');
  var ST = { q:'', page:1, loading:false, items:[], observer:null };

  function esc(s){return String(s||'').replace(/[&<>"]/g,function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
  function readQ(){var m=location.search.match(/[?&]q=([^&]*)/);if(!m)return null;
    try{return decodeURIComponent(m[1].replace(/\+/g,' '))}catch(e){return null}}
  function writeQ(q){try{if(history.replaceState)history.replaceState(null,'','?q='+encodeURIComponent(q))}catch(e){}}

  function fetchShorts(q, page){
    if(ST.loading) return;
    ST.loading = true;
    return fetch('/api/shorts?q='+encodeURIComponent(q)+'&page='+page)
      .then(function(r){return r.json()})
      .then(function(j){
        ST.loading = false;
        if(j.code !== 0) throw new Error(j.message || 'code '+j.code);
        var items = j.items || [];
        ST.items = ST.items.concat(items);
        renderNew(items);
        return items;
      })
      .catch(function(e){
        ST.loading = false;
        var slot = container.querySelector('.loading-slot');
        if(slot) slot.innerHTML = '<div class="loading"><div>'+esc(e.message)+'</div></div>';
      });
  }

  function renderNew(items){
    var slot = container.querySelector('.loading-slot');
    if(slot) slot.remove();

    items.forEach(function(v){
      var item = document.createElement('div');
      item.className = 'video-item';
      item.dataset.bvid = v.bvid;
      item.dataset.loaded = '0';
      var cover = v.cover ? '/api/img?u='+encodeURIComponent(v.cover) : '';
      item.innerHTML =
        (cover ? '<div class="bg-cover" style="background-image:url('+cover+')"></div>' : '') +
        '<video playsinline loop preload="none" muted></video>' +
        '<div class="loading"><div class="spinner"></div></div>' +
        '<div class="overlay">' +
          '<div class="info">' +
            '<div class="title">'+esc(v.title)+'</div>' +
            '<div class="author">'+esc(v.author)+'</div>' +
          '</div>' +
          '<div class="bottom">' +
            '<div class="action" data-action="like"><span>♥</span></div>' +
            '<div class="action" data-action="mute"><span>🔇</span></div>' +
          '</div>' +
        '</div>';
      container.appendChild(item);
      bindItem(item);
      ST.observer.observe(item);
    });

    var newSlot = document.createElement('div');
    newSlot.className = 'video-item loading-slot';
    newSlot.innerHTML = '<div class="loading"><div class="spinner"></div><div>more</div></div>';
    container.appendChild(newSlot);
    ST.observer.observe(newSlot);
  }

  function loadVideo(item){
    if(item.dataset.loaded === '1') return;
    item.dataset.loaded = '1';
    var video = item.querySelector('video');
    var loading = item.querySelector('.loading');
    fetch('/api/playurl?bvid='+encodeURIComponent(item.dataset.bvid)+'&qn=32')
      .then(function(r){return r.json()})
      .then(function(j){
        if(j.code !== 0) throw new Error(j.message || 'code '+j.code);
        video.src = j.url;
        video.muted = true;
        var p = video.play();
        if(p && p.catch) p.catch(function(){});
        if(loading) loading.style.display = 'none';
      })
      .catch(function(e){
        if(loading) loading.innerHTML = '<div>'+esc(e.message)+'</div>';
      });
  }

  function bindItem(item){
    var video = item.querySelector('video');
    var muteBtn = item.querySelector('[data-action="mute"]');
    var likeBtn = item.querySelector('[data-action="like"]');

    muteBtn.addEventListener('click', function(e){
      e.stopPropagation();
      video.muted = !video.muted;
      muteBtn.querySelector('span').textContent = video.muted ? '🔇' : '🔊';
    });

    likeBtn.addEventListener('click', function(e){
      e.stopPropagation();
      var rect = item.getBoundingClientRect();
      showHeart(item, rect.width/2, rect.height/2);
      fetch('/api/fav', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({bvid:item.dataset.bvid,
                              title: item.querySelector('.title').textContent})
      }).catch(function(){});
    });

    var lastTap = 0, tapTimer = null;
    var tx = 0, ty = 0, moved = false;
    item.addEventListener('touchstart', function(e){
      tx = e.touches[0].clientX; ty = e.touches[0].clientY; moved = false;
    }, {passive:true});
    item.addEventListener('touchmove', function(e){
      if(Math.abs(e.touches[0].clientX - tx) > 8 ||
         Math.abs(e.touches[0].clientY - ty) > 8) moved = true;
    }, {passive:true});

    item.addEventListener('click', function(e){
      if(moved) return;
      if(e.target.closest('[data-action]')) return;
      var now = Date.now();
      var rect = item.getBoundingClientRect();
      var x = e.clientX - rect.left;
      var y = e.clientY - rect.top;
      if(now - lastTap < 300){
        clearTimeout(tapTimer);
        lastTap = 0;
        showHeart(item, x, y);
        fetch('/api/fav', {method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({bvid:item.dataset.bvid,
                                title: item.querySelector('.title').textContent})
        }).catch(function(){});
      } else {
        lastTap = now;
        tapTimer = setTimeout(function(){
          if(video.paused) video.play().catch(function(){});
          else video.pause();
        }, 300);
      }
    });
  }

  function showHeart(parent, x, y){
    var h = document.createElement('div');
    h.className = 'heart';
    h.textContent = '♥';
    h.style.left = x + 'px';
    h.style.top = y + 'px';
    parent.appendChild(h);
    setTimeout(function(){ h.remove(); }, 800);
  }

  // 定期清理：只保留当前屏 ±1 的 video，更远的销毁 src 释放内存
  setInterval(function(){
    var items = container.querySelectorAll('.video-item:not(.loading-slot)');
    var cur = -1, curEl = null;
    for(var i = 0; i < items.length; i++){
      var r = items[i].getBoundingClientRect();
      if(r.top <= window.innerHeight/2 && r.bottom >= window.innerHeight/2){
        cur = i; curEl = items[i]; break;
      }
    }
    if(cur < 0) return;
    for(var i = 0; i < items.length; i++){
      var v = items[i].querySelector('video');
      if(!v) continue;
      if(Math.abs(i - cur) > 1){
        if(!v.paused) v.pause();
        if(v.src){ v.removeAttribute('src'); v.load(); }
        items[i].dataset.loaded = '0';
      }
    }
  }, 2000);

  ST.observer = new IntersectionObserver(function(entries){
    entries.forEach(function(entry){
      var item = entry.target;
      if(item.classList.contains('loading-slot')){
        if(entry.isIntersecting && ST.items.length > 0 && !ST.loading){
          ST.page += 1;
          fetchShorts(ST.q, ST.page);
        }
        return;
      }
      var video = item.querySelector('video');
      if(!video) return;
      if(entry.intersectionRatio > 0.6){
        if(item.dataset.loaded !== '1') loadVideo(item);
        if(video.src) video.play().catch(function(){});
      } else {
        if(!video.paused) video.pause();
      }
    });
  }, { threshold: [0, 0.6, 0.8], rootMargin: '100px 0px' });

  var initQ = readQ() || '原神短视频';
  qInput.value = initQ;
  ST.q = initQ;
  writeQ(initQ);
  fetchShorts(initQ, 1);

  qInput.addEventListener('keydown', function(e){
    if(e.key === 'Enter'){
      e.preventDefault();
      var q = qInput.value.trim();
      if(!q) return;
      ST.q = q; ST.page = 1; ST.items = [];
      container.innerHTML = '';
      writeQ(q);
      fetchShorts(q, 1);
    }
  });
})();
</script>
</body></html>"""

@shorts_bp.route("/shorts")
def shorts_page(): return SHORTS_HTML
