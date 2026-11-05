# app/misc_routes.py - 3e 抽取（FAV_HTML + /fav + HTML + / + /health + /metrics + gzip）
import time
import gzip as _gzip
from flask import Blueprint, request, jsonify
from app.db import _db_conn, _DB_LOCK  # 修 bug：原文件没 import，daily 永远是 0
from app.metrics import _METRICS, _METRICS_LOCK

misc_bp = Blueprint("misc", __name__)

_START_TS = int(time.time())

@misc_bp.route("/health")
def health():
    import multiprocessing
    cpu = multiprocessing.cpu_count() or 4
    return jsonify({"status": "ok", "service": "bili", "port": 8092,
                    "cpu": cpu, "threads": max(4, cpu * 2)})

@misc_bp.route("/metrics")
def metrics():
    # 从 SQLite 读今日统计
    today_start = int(time.time()) - 86400
    daily = {"fav_total": 0, "progress_total": 0, "history_total": 0}
    try:
        with _DB_LOCK:
            c = _db_conn()
            daily["fav_total"] = c.execute(
                "SELECT COUNT(*) AS n FROM favorites").fetchone()["n"]
            daily["progress_total"] = c.execute(
                "SELECT COUNT(*) AS n FROM watch_progress").fetchone()["n"]
            daily["history_total"] = c.execute(
                "SELECT COUNT(*) AS n FROM search_history").fetchone()["n"]
            c.close()
    except Exception:
        pass
    with _METRICS_LOCK:
        counters = dict(_METRICS)
    return jsonify({"status": "ok", "service": "bili", "port": 8092,
                    "uptime": int(time.time()) - _START_TS,
                    "counters": counters, "daily": daily})

FAV_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>收藏</title>
<style>
:root{--bg:#0a0a0a;--surface:#141413;--text:#faf9f5;--text-2:#b0aea5;
  --muted:#6b6a63;--line:hsla(0,0%,100%,.08);--line-2:hsla(0,0%,100%,.12);
  --clay:#d97757;--ease:cubic-bezier(.16,1,.3,1)}
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:var(--bg);color:var(--text);
  font-family:-apple-system,"Noto Sans SC",sans-serif;letter-spacing:-.02em}
.wrap{max-width:860px;margin:0 auto;padding:20px 16px 80px}
h1{font-family:Georgia,"Noto Serif SC",serif;font-size:20px;font-weight:600;
  letter-spacing:-.04em;margin-bottom:4px}
.sub{font-family:monospace;font-size:10px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--muted);margin-bottom:24px}
.item{display:flex;padding:11px;border-radius:var(--radius-lg);background:#141413;
  border:1px solid var(--line);margin-bottom:9px;text-decoration:none;color:inherit;
  transition:background .18s var(--ease)}
.item:active{background:#1c1c1a}
.thumb{width:108px;height:66px;border-radius:9px;flex-shrink:0;background:#22221f;
  overflow:hidden;margin-right:13px}
.thumb img{width:100%;height:100%;object-fit:cover;display:block}
.meta{flex:1;min-width:0}
.t{font-size:13px;line-height:1.4;font-weight:500;margin-bottom:6px}
.a{font-family:monospace;font-size:10px;letter-spacing:.06em;color:var(--muted);text-transform:uppercase}
.empty{text-align:center;padding:64px 0;color:var(--muted);font-family:monospace;font-size:11px;letter-spacing:.12em}
.back{display:inline-block;padding:8px 0 16px;color:var(--clay);font-family:monospace;
  font-size:11px;letter-spacing:.1em;text-transform:uppercase;text-decoration:none}
</style></head><body>
<div class="wrap">
  <a class="back" href="/">← back</a>
  <h1>收藏</h1>
  <div class="sub" id="cnt">favorites</div>
  <div id="list"></div>
</div>
<script>
(function(){
  var list=document.getElementById('list'),cnt=document.getElementById('cnt');
  function esc(s){return(s||"").replace(/[&<>"]/g,function(c){
    return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
  fetch('/api/fav').then(function(r){return r.json()}).then(function(j){
    if(j.code!==0)throw new Error('code '+j.code);
    var items=j.items||[];
    if(!items.length){ list.innerHTML='<div class="empty">暂无收藏</div>'; return; }
    cnt.textContent=items.length+' favorites';
    var h='';
    items.forEach(function(it){
      var cover=it.cover||'';
      if(cover.indexOf('/api/img?u=')!==0&&cover.indexOf('http')===0) cover='/api/img?u='+encodeURIComponent(cover);
      h+='<a class="item" href="/play/'+esc(it.bvid)+'">'+
        '<div class="thumb">'+(cover?'<img src="'+esc(cover)+'" onerror="this.style.display=\'none\'">':'')+'</div>'+
        '<div class="meta"><div class="t">'+esc(it.title||it.bvid)+'</div>'+
        '<div class="a">'+esc(it.author||'')+'</div></div></a>';
    });
    list.innerHTML=h;
  }).catch(function(e){ list.innerHTML='<div class="empty">加载失败: '+esc(e.message)+'</div>'; });
})();
</script></body></html>"""

@misc_bp.route("/fav")
def fav_page(): return FAV_HTML

HTML = r'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bili Console v6</title>
<style>
:root{
  --bg:#0a0a0a; --surface:#141413;
  --text:#faf9f5; --text-2:#b0aea5; --muted:#6b6a63;
  --line:hsla(0,0%,100%,.08); --line-2:hsla(0,0%,100%,.12);
  --glass-bg:hsla(0,0%,100%,.045);
  --glass-border:hsla(0,0%,100%,.09);
  --clay:#d97757; --brand:#4d6bfe;
  --ease:cubic-bezier(.16,1,.3,1);
  --spring:cubic-bezier(.34,1.56,.64,1);
}
*{margin:0;padding:0;box-sizing:border-box;
  -webkit-tap-highlight-color:transparent}
html,body{background:var(--bg);color:var(--text);
  font-family:-apple-system,"Noto Sans SC",sans-serif;
  letter-spacing:-.02em;-webkit-font-smoothing:antialiased;
  overflow-x:hidden}

/* 背景光晕：让玻璃卡片有东西可 blur */
body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:
    radial-gradient(ellipse 55% 45% at 15% 0%, rgba(77,107,254,.07), transparent 65%),
    radial-gradient(ellipse 50% 40% at 85% 100%, rgba(217,119,87,.06), transparent 65%);}

.wrap{max-width:860px;margin:0 auto;padding:0 16px 80px}

/* 顶栏：玻璃 + 惯性内缩 */
header{position:sticky;top:0;z-index:20;padding:14px 0 12px;
  background:rgba(10,10,10,.72);
  border-bottom:1px solid var(--line);
  transition:padding .28s var(--ease),background .28s var(--ease);
  will-change:padding}
@supports ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){
  header{backdrop-filter:blur(16px) saturate(1.5);
    -webkit-backdrop-filter:blur(16px) saturate(1.5)}
}
header.compact{padding:8px 0 7px;background:rgba(0,0,0,.85)}
.brand{margin-bottom:12px;transition:margin .28s var(--ease)}
header.compact .brand{margin-bottom:8px}
.brand h1{font-size:18px;font-weight:600;letter-spacing:-.04em;
  font-family:Georgia,"Noto Serif SC",serif;display:inline}
.brand span{font-family:monospace;font-size:9px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--muted);margin-left:10px}

/* 搜索栏 */
.bar{display:flex}
.bar input{flex:1;min-width:0;background:var(--surface);
  border:1px solid var(--line-2);border-radius:11px;
  padding:11px 14px;color:var(--text);font-size:14px;outline:none;
  margin-right:8px;letter-spacing:-.01em;
  transition:border-color .22s var(--ease),box-shadow .22s var(--ease),
             background .22s var(--ease)}
.bar input::placeholder{color:var(--muted)}
.bar input:focus{border-color:rgba(217,119,87,.55);
  background:#1a1918;
  box-shadow:0 0 0 4px rgba(217,119,87,.10)}
.bar button{flex-shrink:0;background:var(--clay);color:#1a0f0a;border:0;
  border-radius:11px;padding:0 20px;font-size:13px;font-weight:600;
  letter-spacing:.02em;cursor:pointer;
  transform:translateZ(0);
  transition:filter .15s var(--ease)}

/* 状态行：DeepSeek 呼吸点 */
.status{display:flex;align-items:center;gap:8px;
  font-family:monospace;font-size:10px;letter-spacing:.12em;
  text-transform:uppercase;color:var(--muted);
  margin:22px 2px 14px;min-height:16px;transition:color .2s var(--ease)}
.status.active{color:var(--clay)}
.status .dot{width:5px;height:5px;border-radius:50%;background:currentColor;
  opacity:.3;animation:breathe 1.4s ease-in-out infinite}
.status .dot:nth-child(2){animation-delay:.18s}
.status .dot:nth-child(3){animation-delay:.36s}
.status:not(.active) .dot{display:none}
@keyframes breathe{0%,100%{opacity:.25;transform:scale(.75)}
  50%{opacity:1;transform:scale(1.15)}}

/* 卡片：玻璃 + 入场（JS 弹簧接管） */
.card{display:flex;padding:11px;border-radius:16px;
  background:var(--glass-bg);
  border:1px solid var(--glass-border);
  margin-bottom:9px;text-decoration:none;color:inherit;
  box-shadow:inset 0 1px 0 hsla(0,0%,100%,.06),
             0 1px 2px rgba(0,0,0,.3);
  position:relative;overflow:hidden;
  opacity:0;
  will-change:transform,opacity;
  transition:background .18s var(--ease),
             border-color .18s var(--ease),
             box-shadow .18s var(--ease)}
@supports ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){
  .card{backdrop-filter:blur(14px) saturate(1.3);
    -webkit-backdrop-filter:blur(14px) saturate(1.3)}
}
.card.pressed{background:hsla(0,0%,100%,.085);
  border-color:rgba(217,119,87,.45)}
.card::before{content:"";position:absolute;left:0;top:14px;bottom:14px;
  width:2px;border-radius:2px;background:var(--clay);
  opacity:0;transform:scaleY(.3);transform-origin:center;
  transition:opacity .2s var(--ease),transform .2s var(--ease)}
.card.pressed::before{opacity:1;transform:scaleY(1)}

.thumb{width:108px;height:66px;border-radius:10px;flex-shrink:0;
  background:#22221f;overflow:hidden;position:relative;margin-right:13px}
.thumb img{width:100%;height:100%;object-fit:cover;display:block}
.dur{position:absolute;right:4px;bottom:4px;font-family:monospace;
  font-size:9px;padding:1px 5px;border-radius:4px;background:rgba(0,0,0,.8);
  color:#e8e6df}
.meta{flex:1;min-width:0}
.title{font-size:13px;line-height:1.4;font-weight:500;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
  overflow:hidden;margin-bottom:6px;letter-spacing:-.01em}
.title em{color:var(--clay);font-style:normal}
.sub{font-family:monospace;font-size:10px;letter-spacing:.06em;
  color:var(--muted);text-transform:uppercase}
.sub b{color:var(--text-2);font-weight:500;margin-right:10px}

.empty{text-align:center;padding:64px 0;color:var(--muted);
  font-family:monospace;font-size:11px;letter-spacing:.12em}

/* 加载更多 */
.more-wrap{display:flex;justify-content:center;margin-top:18px}
.more{display:inline-flex;align-items:center;gap:8px;
  background:hsla(0,0%,100%,.03);
  border:1px solid var(--line-2);border-radius:13px;
  padding:12px 26px;color:var(--text-2);
  font-family:monospace;font-size:11px;letter-spacing:.12em;
  text-transform:uppercase;cursor:pointer;
  transform:translateZ(0);
  transition:border-color .22s var(--ease),
             color .22s var(--ease),
             background .22s var(--ease)}
.more:hover{border-color:rgba(217,119,87,.55);color:var(--clay);
  background:hsla(217,119,87,.04)}
.more.loading{border-color:rgba(217,119,87,.4);color:var(--clay)}
.more .dot{width:5px;height:5px;border-radius:50%;background:currentColor;
  display:none;animation:breathe 1.2s ease-in-out infinite}
.more.loading .dot{display:inline-block}
.more-end{text-align:center;padding:26px 0 8px;color:var(--muted);
  font-family:monospace;font-size:10px;letter-spacing:.16em;
  text-transform:uppercase;opacity:.7}

@media(prefers-reduced-motion:reduce){
  *{animation-duration:.01ms!important;transition-duration:.01ms!important}
  .card{opacity:1!important;transform:none!important}}
</style></head><body>

<div class="wrap">
  <header id="hdr">
    <div class="brand"><h1>Bilibili</h1><span>wbi · console · v6</span></div>
    <div class="bar">
      <input id="q" placeholder="搜索视频…" autocomplete="off">
      <button id="go">搜索</button>
      <button id="aiAskBtn" style="background:transparent;color:#4d6bfe;border:1px solid rgba(77,107,254,.4);border-radius:11px;padding:0 12px;font-size:13px;font-weight:600;cursor:pointer;margin-left:6px;flex-shrink:0">✦ AI</button>
    </div>
  </header>
  <style>
.sortbar{display:flex;overflow-x:auto;white-space:nowrap;margin:14px 0 0;
  padding-bottom:2px;-webkit-overflow-scrolling:touch}
.sortbar::-webkit-scrollbar{display:none}
.sort-chip{display:inline-block;padding:6px 14px;margin-right:7px;border-radius:20px;
  background:hsla(0,0%,100%,.03);border:1px solid hsla(0,0%,100%,.1);
  color:#b0aea5;font-size:12px;cursor:pointer;flex-shrink:0;
  transition:color .18s cubic-bezier(.16,1,.3,1),
             border-color .18s cubic-bezier(.16,1,.3,1),
             background .18s cubic-bezier(.16,1,.3,1)}
.sort-chip.active{color:#d97757;border-color:rgba(217,119,87,.5);
  background:rgba(217,119,87,.08)}
.sort-chip:active{opacity:.7}
</style>
<style>
.typebar,.durbar{display:flex;overflow-x:auto;white-space:nowrap;margin-top:8px;
  padding-bottom:2px;-webkit-overflow-scrolling:touch}
.typebar::-webkit-scrollbar,.durbar::-webkit-scrollbar{display:none}
.type-chip,.dur-chip{display:inline-block;padding:5px 12px;margin-right:6px;
  border-radius:18px;background:hsla(0,0%,100%,.03);
  border:1px solid hsla(0,0%,100%,.1);color:#b0aea5;font-size:11px;
  cursor:pointer;flex-shrink:0;
  transition:color .18s cubic-bezier(.16,1,.3,1),
             border-color .18s cubic-bezier(.16,1,.3,1),
             background .18s cubic-bezier(.16,1,.3,1)}
.type-chip.active,.dur-chip.active{color:#d97757;border-color:rgba(217,119,87,.5);
  background:rgba(217,119,87,.08)}
.type-chip:active,.dur-chip:active{opacity:.7}
</style>
<div class="typebar" id="typebar">
  <span class="type-chip active" data-type="video">视频</span>
  <span class="type-chip" data-type="media_bangumi">番剧</span>
  <span class="type-chip" data-type="media_ft">影视</span>
</div>
<div class="durbar" id="durbar">
  <span class="dur-chip active" data-dur="0">全部时长</span>
  <span class="dur-chip" data-dur="1">10分内</span>
  <span class="dur-chip" data-dur="2">10-30分</span>
  <span class="dur-chip" data-dur="3">30-60分</span>
  <span class="dur-chip" data-dur="4">60分以上</span>
</div>
<div class="sortbar" id="sortbar">
  <span class="sort-chip active" data-order="totalrank">综合</span>
  <span class="sort-chip" data-order="click">播放多</span>
  <span class="sort-chip" data-order="pubdate">最新</span>
  <span class="sort-chip" data-order="dm">弹幕多</span>
</div>
<div class="status" id="status">ready</div>
  <div id="list"></div>
  <div class="more-wrap" id="moreWrap"></div>
</div>

<script>
(function(){

var __LOWEND__ = (navigator.hardwareConcurrency||4) <= 2;

/* ============ 弹簧引擎 ============ */
function Spring(initial, k, c, m){
  this.x = initial; this.v = 0;
  this.k = k; this.c = c; this.m = m;
  this.goal = initial;
  this.onUpdate = null;
}
Spring.prototype.setGoal = function(g){ this.goal = g; };
Spring.prototype.step = function(dt){
  var a = (-this.k*(this.x-this.goal) - this.c*this.v) / this.m;
  this.v += a*dt;
  this.x += this.v*dt;
};
Spring.prototype.settled = function(){
  return Math.abs(this.v) < .01 && Math.abs(this.x-this.goal) < .01;
};

var activeSprings = [];
var rafId = null, lastTs = 0;

function pump(){
  rafId = null;
  var now = performance.now();
  var dt = Math.min((now - (lastTs||now))/1000, 1/30);
  lastTs = now;
  var alive = [];
  for(var i=0;i<activeSprings.length;i++){
    var s = activeSprings[i];
    s.step(dt);
    if(s.onUpdate) s.onUpdate(s.x);
    if(!s.settled()) alive.push(s);
  }
  activeSprings = alive;
  if(activeSprings.length) rafId = requestAnimationFrame(pump);
  else lastTs = 0;
}
function addSpring(s){
  if(activeSprings.indexOf(s) === -1) activeSprings.push(s);
  if(!rafId){ lastTs = 0; rafId = requestAnimationFrame(pump); }
}

/* ============ DOM ============ */
var list=document.getElementById("list"),
    status=document.getElementById("status"),
    q=document.getElementById("q"),
    hdr=document.getElementById("hdr"),
    go=document.getElementById("go"),
    moreWrap=document.getElementById("moreWrap");

var ST={ q:"", page:0, totalPage:0, total:0, loading:false, order:"totalrank",
  type:"video", duration:0 };
  window.ST_SET_ORDER = function(o){ ST.order=o; if(ST.q){ fetchPage(1,false); } };
  window.ST_SET_TYPE = function(t){ ST.type=t; if(ST.q){ fetchPage(1,false); } };
  window.ST_SET_DURATION = function(d){ ST.duration=d; if(ST.q){ fetchPage(1,false); } };

/* 顶栏惯性内缩 */
var lastY=0;
window.addEventListener("scroll", function(){
  var y = window.pageYOffset;
  if(y>lastY && y>40) hdr.classList.add("compact");
  else if(y<lastY-10) hdr.classList.remove("compact");
  lastY=y;
},{passive:true});

/* 按压：弹簧缩放 + 状态类 */
function bindPress(el){
  if(__LOWEND__){
    function onL(){ el.classList.add("pressed"); }
    function offL(){ el.classList.remove("pressed"); }
    el.addEventListener("touchstart", onL, {passive:true});
    el.addEventListener("touchend", offL);
    el.addEventListener("touchcancel", offL);
    el.addEventListener("mousedown", onL);
    el.addEventListener("mouseup", offL);
    el.addEventListener("mouseleave", offL);
    return;
  }
  var sc = new Spring(1, 420, 28, 1);
  sc.onUpdate = function(v){ el.style.transform = 'scale(' + v.toFixed(4) + ')'; };
  function on(){
    el.classList.add("pressed");
    sc.setGoal(.96); addSpring(sc);
  }
  function off(){
    el.classList.remove("pressed");
    sc.setGoal(1); addSpring(sc);
  }
  el.addEventListener("touchstart", on, {passive:true});
  el.addEventListener("touchend", off);
  el.addEventListener("touchcancel", off);
  el.addEventListener("mousedown", on);
  el.addEventListener("mouseup", off);
  el.addEventListener("mouseleave", off);
}
bindPress(go);

function esc(s){return(s||"").replace(/[&<>"]/g,function(c){
  return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function stripEm(s){return(s||"").replace(/<em class="keyword">|<\/em>/g,"")}

function readParams(){
  var p={};
  var m=location.search.match(/[?&]q=([^&]*)/);
  if(m)try{p.q=decodeURIComponent(m[1].replace(/\+/g," "))}catch(e){}
  var mp=location.search.match(/[?&]page=(\d+)/);
  if(mp)p.page=parseInt(mp[1],10)||1;
  return p;
}
function writeParams(){
  try{ if(history.replaceState)
    history.replaceState(null,"","?q="+encodeURIComponent(ST.q)+"&page="+ST.page);
  }catch(e){}
}

function setMore(mode){
  moreWrap.innerHTML="";
  if(mode==="loading"){
    var b=document.createElement("button");
    b.className="more loading";
    b.innerHTML='<span class="dot"></span>loading';
    moreWrap.appendChild(b);
  }else if(mode==="more"){
    var b2=document.createElement("button");
    b2.className="more";
    b2.textContent="load more";
    bindPress(b2);
    b2.addEventListener("click",function(e){
      e.preventDefault();
      if(ST.loading)return;
      fetchPage(ST.page+1,true);
    });
    moreWrap.appendChild(b2);
  }else if(mode==="end"){
    var d=document.createElement("div");
    d.className="more-end"; d.textContent="no more";
    moreWrap.appendChild(d);
  }else if(mode==="error"){
    var b3=document.createElement("button");
    b3.className="more"; b3.textContent="retry";
    bindPress(b3);
    b3.addEventListener("click",function(e){
      e.preventDefault();
      if(ST.loading)return;
      fetchPage(ST.page+1,true);
    });
    moreWrap.appendChild(b3);
  }
}

/* 卡片入场弹簧：从 y=14 落位，带过冲 */
function enterCard(el, delay){
  var ty = new Spring(14, 260, 24, 1);
  var op = new Spring(0, 260, 24, 1);
  ty.onUpdate = function(v){ el.style.transform = 'translateY(' + v.toFixed(2) + 'px)'; };
  op.onUpdate = function(v){ el.style.opacity = Math.min(1, v).toFixed(3); };
  el.style.opacity = "0";
  el.style.transform = "translateY(14px)";
  setTimeout(function(){
    ty.setGoal(0); op.setGoal(1);
    addSpring(ty); addSpring(op);
  }, delay);
}

function fetchPage(page, append){
  if(ST.loading)return;
  ST.loading=true;
  if(!append){
    list.innerHTML="";
    status.className="status active";
    status.innerHTML='<span class="dot"></span><span class="dot"></span><span class="dot"></span>searching';
    moreWrap.innerHTML="";
  }else{
    setMore("loading");
  }

  fetch("/api/search?q="+encodeURIComponent(ST.q)+"&page="+page+"&order="+ST.order
      +"&type="+ST.type+"&duration="+ST.duration)
    .then(function(r){return r.json()})
    .then(function(j){
      ST.loading=false;
      if(j.code!==0)throw new Error(j.message||("code "+j.code));
      var d=j.data||{};
      var items=d.result||[];
      var numPages=d.numPages||d.pages||0;
      var numResults=d.numResults||d.total||0;
      ST.page=page; ST.totalPage=numPages; ST.total=numResults;
      writeParams();

      render(items, append);

      var loaded=list.children.length;
      var hasMore;
      if(ST.totalPage>0) hasMore = ST.page < ST.totalPage;
      else if(ST.total>0) hasMore = loaded < ST.total;
      else hasMore = items.length>=20;

      if(hasMore) setMore("more");
      else setMore("end");

      status.className="status";
      if(ST.total>0) status.textContent = loaded+" / "+ST.total+" · p"+ST.page;
      else status.textContent = loaded+" results · p"+ST.page;
    })
    .catch(function(e){
      ST.loading=false;
      status.className="status";
      status.textContent="error · "+e.message;
      if(append) setMore("error");
      else list.innerHTML='<div class="empty">搜索失败</div>';
    });
}

function render(items, append){
  if(!append) list.innerHTML="";
  if(!items.length && !append){
      var emptyMsg = 'NO RESULT';
      if(ST.type === 'media_bangumi') emptyMsg = '该关键词在番剧区无结果 · 试试更短的名字';
      else if(ST.type === 'media_ft') emptyMsg = '该关键词在影视区无结果 · 试试更短的名字';
      else if(ST.duration) emptyMsg = '该时长范围内无结果 · 试试「全部时长」';
      list.innerHTML='<div class="empty">'+emptyMsg+'</div>';
      return;
  }
  var base = list.children.length;
  items.forEach(function(v,i){
    var a=document.createElement("a");
    a.className="card";
    a.href="/play/"+v.bvid;
    var pic=v.pic||""; if(pic.indexOf("//")===0)pic="https:"+pic;
    a.innerHTML=
      '<div class="thumb">'+
        (pic?'<img src="/api/img?u='+encodeURIComponent(pic)+'" loading="lazy" onerror="this.style.display=\'none\'">':"")+
        '<span class="dur">'+esc(v.duration||"")+'</span>'+
      '</div>'+
      '<div class="meta"><div class="title">'+esc(stripEm(v.title))+'</div>'+
      '<div class="sub"><b>'+esc(v.author||"?")+'</b>'+esc(String(v.play||0))+' 播放</div></div>';
    bindPress(a);
    list.appendChild(a);

    /* 弹簧入场：前 14 张做弹簧，其余直接显示（性能） */
    if(base+i < 14){
      enterCard(a, i*32);
    }else{
      a.style.opacity="1";
      a.style.transform="none";
    }
  });
}

function newSearch(){
  var kw=q.value.trim();
  if(!kw){
    status.className="status";
    status.textContent="请输入关键词";
    return;
  }
  ST.q=kw; ST.page=0; ST.totalPage=0; ST.total=0;
  fetchPage(1,false);
}

go.addEventListener("click",function(e){e.preventDefault();newSearch()});
q.addEventListener("keydown",function(e){
  if(e.key==="Enter"){e.preventDefault();newSearch()}
});

/* 初始：URL 有 q 才搜，否则停在欢迎态 */
var p=readParams();
if(p.q) q.value=p.q;
ST.q=p.q||"";
if(p.q && p.page && p.page>1){
  var target=p.page, loaded=0;
  (function step(){
    loaded++;
    if(loaded>target) return;
    ST.loading=false;
    fetchPage(loaded, loaded>1);
    if(loaded<target) setTimeout(step, 700);
  })();
}else if(p.q){
  fetchPage(1,false);
}else{
  status.className="status";
  status.textContent="ready · 输入关键词开始搜索";
  list.innerHTML='<div class="empty">TYPE TO SEARCH</div>';
}

})();
</script>
<script>
(function(){
  var bar = document.querySelector('.bar');
  if(!bar) return;
  var input = document.getElementById('q');
  if(input && input.parentNode === bar){
    var wrap = document.createElement('div');
    wrap.style.cssText = 'position:relative;flex:1;min-width:0';
    bar.insertBefore(wrap, input);
    wrap.appendChild(input);
    var drop = document.createElement('div');
    drop.style.cssText = 'position:absolute;left:0;right:8px;top:100%;margin-top:4px;background:#141413;border:1px solid hsla(0,0%,100%,.12);border-radius:10px;overflow:hidden;display:none;z-index:30;box-shadow:0 8px 24px rgba(0,0,0,.5)';
    wrap.appendChild(drop);
    function loadHistory(){
      fetch('/api/history').then(function(r){return r.json()}).then(function(j){
        if(j.code!==0) return;
        var items = j.items||[];
        if(!items.length){ drop.style.display='none'; return; }
        drop.innerHTML='';
        items.forEach(function(it){
          var d = document.createElement('div');
          d.style.cssText='padding:10px 14px;font-size:13px;color:#b0aea5;cursor:pointer;border-bottom:1px solid hsla(0,0%,100%,.04)';
          d.textContent=it.q;
          d.addEventListener('mousedown',function(e){
            e.preventDefault();
            input.value=it.q;
            drop.style.display='none';
            var go=document.getElementById('go');
            if(go) go.click();
          });
          d.addEventListener('mouseenter',function(){ d.style.background='hsla(0,0%,100%,.06)'; });
          d.addEventListener('mouseleave',function(){ d.style.background='transparent'; });
          drop.appendChild(d);
        });
        var clr=document.createElement('div');
        clr.style.cssText='padding:8px 14px;font-family:monospace;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:#6b6a63;cursor:pointer;text-align:center';
        clr.textContent='清空历史';
        clr.addEventListener('mousedown',function(e){
          e.preventDefault();
          fetch('/api/history',{method:'DELETE'}).then(function(){ drop.style.display='none'; });
        });
        drop.appendChild(clr);
        drop.style.display='block';
      }).catch(function(){});
    }
    input.addEventListener('focus',loadHistory);
    input.addEventListener('blur',function(){ setTimeout(function(){ drop.style.display='none'; },150); });
  }
  var list=document.getElementById('list');
  function decorateCards(){
    if(!list) return;
    var cards=list.querySelectorAll('.card');
    for(var i=0;i<cards.length;i++){
      (function(card){
        if(card.querySelector('.fav-star')) return;
        var href=card.getAttribute('href')||'';
        var m=href.match(/\/play\/(BV[0-9A-Za-z]+)/);
        if(!m) return;
        var bvid=m[1];
        var star=document.createElement('span');
        star.className='fav-star';
        star.textContent='☆';
        star.style.cssText='position:absolute;right:8px;top:8px;font-size:18px;color:#6b6a63;cursor:pointer;padding:4px 6px;z-index:2;line-height:1';
        star.addEventListener('click',function(e){
          e.preventDefault(); e.stopPropagation();
          var title=(card.querySelector('.title')||{}).textContent||'';
          var author=(card.querySelector('.sub b')||{}).textContent||'';
          var img=card.querySelector('.thumb img');
          var cover=img?img.getAttribute('src')||'':'';
          if(cover.indexOf('/api/img?u=')===0) cover=decodeURIComponent(cover.substring(11));
          fetch('/api/fav',{method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({bvid:bvid,title:title,cover:cover,author:author})
          }).then(function(r){return r.json()}).then(function(j){
            if(j.code===0){ star.textContent=j.faved?'★':'☆'; star.style.color=j.faved?'#d97757':'#6b6a63'; }
          }).catch(function(){});
        });
        card.style.position='relative';
        card.appendChild(star);
        fetch('/api/fav/check?bvid='+encodeURIComponent(bvid)).then(function(r){return r.json()}).then(function(j){
          if(j.code===0 && j.faved){ star.textContent='★'; star.style.color='#d97757'; }
        }).catch(function(){});
      })(cards[i]);
    }
  }
  if(list){
    new MutationObserver(function(){ setTimeout(decorateCards,50); }).observe(list,{childList:true});
    decorateCards();
  }
})();
</script>
<script>
(function(){
  var bar=document.getElementById('sortbar');
  if(!bar)return;
  var chips=bar.querySelectorAll('.sort-chip');
  function bind(){ 
    Array.prototype.forEach.call(chips,function(c){
      if(c._bound)return; c._bound=true;
      c.addEventListener('click',function(){
        Array.prototype.forEach.call(chips,function(x){x.classList.remove('active')});
        c.classList.add('active');
        var o=c.getAttribute('data-order');
        if(window.ST_SET_ORDER)window.ST_SET_ORDER(o);
      });
    });
  }
  bind();
  // 暴露给外部
  window.SORT_READY=true;
})();
</script>

<script>
(function(){
  // ===== 类型切换 =====
  var tbar = document.getElementById('typebar');
  if(tbar){
    tbar.querySelectorAll('.type-chip').forEach(function(c){
      c.addEventListener('click', function(){
        tbar.querySelectorAll('.type-chip').forEach(function(x){ x.classList.remove('active'); });
        c.classList.add('active');
        if(window.ST_SET_TYPE) window.ST_SET_TYPE(c.getAttribute('data-type'));
      });
    });
  }
  // ===== 时长筛选 =====
  var dbar = document.getElementById('durbar');
  if(dbar){
    dbar.querySelectorAll('.dur-chip').forEach(function(c){
      c.addEventListener('click', function(){
        dbar.querySelectorAll('.dur-chip').forEach(function(x){ x.classList.remove('active'); });
        c.classList.add('active');
        var d = parseInt(c.getAttribute('data-dur'), 10) || 0;
        if(window.ST_SET_DURATION) window.ST_SET_DURATION(d);
      });
    });
  }
  // ===== 搜索联想下拉 =====
  var input = document.getElementById('q');
  if(!input) return;
  var bar = input.parentNode;
  if(!bar) return;
  if(getComputedStyle(bar).position === 'static') bar.style.position = 'relative';

  var sug = document.createElement('div');
  sug.id = 'sugDrop';
  sug.style.cssText = 'position:absolute;left:0;right:0;top:100%;margin-top:4px;'+
    'background:#141413;border:1px solid hsla(0,0%,100%,.12);border-radius:10px;'+
    'overflow:hidden;display:none;z-index:40;box-shadow:0 8px 24px rgba(0,0,0,.5)';
  bar.appendChild(sug);

  var sugTimer = null;
  var lastSugQuery = '';

  input.addEventListener('input', function(){
    var val = input.value.trim();
    if(sugTimer) clearTimeout(sugTimer);
    if(!val || val === lastSugQuery){
      sug.style.display = 'none';
      return;
    }
    sugTimer = setTimeout(function(){
      lastSugQuery = val;
      fetch('/api/suggest?q=' + encodeURIComponent(val))
        .then(function(r){ return r.json(); })
        .then(function(j){
          if(j.code !== 0 || !j.items || !j.items.length){
            sug.style.display = 'none';
            return;
          }
          sug.innerHTML = '';
          j.items.forEach(function(item){
            var d = document.createElement('div');
            d.style.cssText = 'padding:10px 14px;font-size:13px;color:#b0aea5;'+
              'cursor:pointer;border-bottom:1px solid hsla(0,0%,100%,.04)';
            // 兜底清理 HTML 标签
            item = String(item).replace(/<[^>]+>/g, '').trim();
            if (!item) return;
            d.textContent = item;
            d.addEventListener('mousedown', function(e){
              e.preventDefault();
              input.value = item;
              sug.style.display = 'none';
              lastSugQuery = '';
              var go = document.getElementById('go');
              if(go) go.click();
            });
            d.addEventListener('mouseenter', function(){ d.style.background = 'hsla(0,0%,100%,.06)'; });
            d.addEventListener('mouseleave', function(){ d.style.background = 'transparent'; });
            sug.appendChild(d);
          });
          sug.style.display = 'block';
        })
        .catch(function(){ sug.style.display = 'none'; });
    }, 300);
  });

  input.addEventListener('blur', function(){
    setTimeout(function(){ sug.style.display = 'none'; }, 150);
  });
  input.addEventListener('focus', function(){
    if(input.value.trim() && lastSugQuery) {
      // 重新打开上一次的联想
    }
  });
})();
</script>

<script>
(function(){
  var btn = document.getElementById('aiAskBtn');
  if(!btn) return;
  btn.addEventListener('click', function(e){
    e.preventDefault();
    var q = (document.getElementById('q').value || '').trim() || '原神';
    var panel = document.getElementById('aiAskPanel');
    if(panel){ panel.remove(); return; }
    panel = document.createElement('div');
    panel.id = 'aiAskPanel';
    panel.style.cssText = 'position:fixed;left:16px;right:16px;bottom:80px;max-height:60vh;overflow-y:auto;background:#141413;border:1px solid rgba(77,107,254,.35);border-radius:16px;padding:16px;z-index:60;box-shadow:0 12px 40px rgba(0,0,0,.7);font-size:13px;line-height:1.7;color:#faf9f5';
    panel.innerHTML = '<div style="font-family:monospace;font-size:10px;letter-spacing:.1em;color:#6b6a63;text-transform:uppercase;margin-bottom:8px">AI 问答</div>'+
      '<div style="display:flex;gap:6px;margin-bottom:10px"><input id="aiAskInput" value="'+esc(q)+'" style="flex:1;background:#0a0a0a;border:1px solid hsla(0,0%,100%,.12);border-radius:8px;padding:8px 12px;color:#faf9f5;font-size:13px;outline:none" placeholder="问点什么…"><button id="aiAskSend" style="background:#4d6bfe;color:#fff;border:0;border-radius:8px;padding:0 14px;font-size:12px;font-weight:600;cursor:pointer">发送</button></div>'+
      '<div id="aiAskReply" style="white-space:pre-wrap;min-height:20px;color:#b0aea5"></div>';
    document.body.appendChild(panel);
    document.getElementById('aiAskInput').focus();
    document.getElementById('aiAskSend').addEventListener('click', send);
    document.getElementById('aiAskInput').addEventListener('keydown', function(ev){
      if(ev.key==='Enter'){ ev.preventDefault(); send(); }
    });
    async function send(){
      var input = document.getElementById('aiAskInput');
      var reply = document.getElementById('aiAskReply');
      var text = input.value.trim();
      if(!text) return;
      reply.textContent = '思考中…';
      reply.style.color = '#6b6a63';
      try{
        var resp = await fetch('/api/chat', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:text}]})});
        var reader = resp.body.getReader(); var decoder = new TextDecoder(); var buf = ''; var full = '';
        reply.textContent = ''; reply.style.color = '#faf9f5';
        while(true){
          var r = await reader.read(); if(r.done) break;
          buf += decoder.decode(r.value, {stream:true});
          var lines = buf.split('\n'); buf = lines.pop();
          for(var line of lines){
            line = line.trim();
            if(!line.startsWith('data: ')) continue;
            var payload = line.slice(6);
            if(payload === '[DONE]') continue;
            try{
              var j = JSON.parse(payload);
              var delta = j.choices && j.choices[0] && j.choices[0].delta;
              if(delta && delta.reasoning_content && !full){ reply.textContent = '思考中…'; }
              if(delta && delta.content){ full += delta.content; reply.textContent = full; }
            }catch(pe){}
          }
        }
      }catch(err){ reply.textContent = '失败: ' + err.message; }
    }
  });
  function esc(s){return String(s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
})();
</script>
</body></html>'''

import gzip as _gzip
@misc_bp.after_app_request
def _gzip_json(resp):
    """只压缩 JSON 响应，视频/音频/图片流一律跳过"""
    try:
        ct = resp.content_type or ""
        if "application/json" not in ct:
            return resp
        if "gzip" not in request.headers.get("Accept-Encoding", ""):
            return resp
        data = resp.get_data()
        if len(data) < 512:
            return resp
        resp.set_data(_gzip.compress(data, 6))
        resp.headers["Content-Encoding"] = "gzip"
        resp.headers["Content-Length"] = str(len(resp.get_data()))
    except Exception:
        pass
    return resp

@misc_bp.route("/")
def index(): return HTML
