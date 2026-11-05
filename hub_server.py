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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一控制台 · 端口 8080 · 聚合 B站/番茄/塔罗 健康状态"""
from flask import Flask, jsonify
app = Flask(__name__)

SERVICES = [
    {"name": "Bilibili", "sub": "wbi console", "port": 8092,
     "url": "http://{host}:8092/", "health": "http://{host}:8092/health",
     "metrics": "http://{host}:8092/metrics",
     "color": "#d97757"},
    {"name": "番茄小说", "sub": "novel console", "port": 8091,
     "url": "http://{host}:8091/", "health": "http://{host}:8091/health",
     "color": "#E5484D"},
    {"name": "Chat", "sub": "glm-4.7-flash", "port": 8092,
     "url": "http://{host}:8092/chat", "health": "http://{host}:8092/health",
     "color": "#4d6bfe"},
    {"name": "塔罗", "sub": "tarot 3d", "port": 8084,
     "url": "http://{host}:8084/", "health": "http://{host}:8084/health",
     "color": "#9b8ec4"},
    {"name": "统一控制台", "sub": "hub itself", "port": 8080,
     "url": "http://{host}:8080/", "health": "http://{host}:8080/health",
     "color": "#6b8e6b"},
]

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "hub", "port": 8080})

HTML = r'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hub · 控制台</title>
<style>
:root{--bg:#0a0a0a;--surface:#141413;--text:#faf9f5;--text-2:#b0aea5;
  --muted:#6b6a63;--line:hsla(0,0%,100%,.08);--line-2:hsla(0,0%,100%,.12);
  --glass:hsla(0,0%,100%,.045);--ease:cubic-bezier(.16,1,.3,1)}
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{background:var(--bg);color:var(--text);
  font-family:-apple-system,"Noto Sans SC",sans-serif;
  letter-spacing:-.02em;-webkit-font-smoothing:antialiased;min-height:100vh}
body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:radial-gradient(ellipse 60% 45% at 50% 0%, rgba(217,119,87,.05), transparent 70%);}
.wrap{max-width:720px;margin:0 auto;padding:40px 16px 80px}
h1{font-family:Georgia,"Noto Serif SC",serif;font-size:22px;font-weight:600;
  letter-spacing:-.04em;text-align:center;margin-bottom:4px}
.sub{text-align:center;font-family:monospace;font-size:10px;
  letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-bottom:32px}
.grid{display:grid;grid-template-columns:1fr;gap:10px}
@media(min-width:520px){.grid{grid-template-columns:1fr 1fr 1fr}}
.svc{display:flex;align-items:center;padding:16px;border-radius:16px;
  background:var(--glass);border:1px solid var(--line);text-decoration:none;
  color:inherit;position:relative;overflow:hidden;
  transition:background .18s var(--ease),border-color .18s var(--ease),
             transform .18s var(--ease)}
.svc:hover{background:hsla(0,0%,100%,.08);border-color:var(--line-2)}
.svc:active{transform:scale(.98)}
.svc::before{content:"";position:absolute;left:0;top:14px;bottom:14px;
  width:2px;border-radius:2px;background:var(--accent,#d97757);opacity:.7}
.dot{width:8px;height:8px;border-radius:50%;background:#444;flex-shrink:0;
  margin-right:14px;transition:background .3s var(--ease);
  box-shadow:0 0 0 0 rgba(0,0,0,0)}
.dot.ok{background:#5ec269;box-shadow:0 0 8px rgba(94,194,105,.5)}
.dot.fail{background:#E5484D;box-shadow:0 0 8px rgba(229,72,77,.5)}
.dot.checking{background:var(--clay);animation:pulse 1.2s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:.3}50%{opacity:1}}
.info{flex:1;min-width:0}
.name{font-size:15px;font-weight:500;letter-spacing:-.02em;margin-bottom:3px}
.meta{font-family:monospace;font-size:10px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--muted)}
.stats{font-family:monospace;font-size:9px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--muted);margin-top:4px;opacity:.8}
.arrow{color:var(--muted);font-family:monospace;font-size:14px;margin-left:8px}
.foot{text-align:center;margin-top:32px;font-family:monospace;font-size:10px;
  letter-spacing:.12em;text-transform:uppercase;color:var(--muted);opacity:.6}
</style></head><body>
<div class="wrap">
  <h1>Hub</h1>
  <div class="sub">personal console</div>
  <div class="grid" id="grid"></div>
  <div class="foot" id="foot">checking services…</div>
</div>
<script>
(function(){
  var SERVICES = __SERVICES__;
  var HOST = location.hostname || "127.0.0.1";
  var grid=document.getElementById("grid"),foot=document.getElementById("foot");
  var okCount=0,failCount=0;
  SERVICES.forEach(function(s){
    var a=document.createElement("a");
    a.className="svc"; a.href=s.url.replace("{host}",HOST);
    a.style.setProperty("--accent",s.color);
    a.innerHTML='<span class="dot checking" data-idx="'+s.port+'"></span>'+
      '<div class="info"><div class="name">'+esc(s.name)+'</div>'+
      '<div class="meta">'+esc(s.sub)+' · :'+s.port+'</div>'+
      '<div class="stats" id="stats-'+s.port+'"></div></div>'+
      '<span class="arrow">↗</span>';
    grid.appendChild(a);
  });
  function esc(s){return(s||"").replace(/[&<>"]/g,function(c){
    return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
  function checkAll(){
    okCount=0;failCount=0;
    var promises=SERVICES.map(function(s){
      var dot=document.querySelector('.dot[data-idx="'+s.port+'"]');
      if(dot){dot.className="dot checking";}
      return fetch(s.health.replace("{host}",HOST),{cache:"no-store",mode:"cors"})
        .then(function(r){return r.ok?r.json():Promise.reject(r.status)})
        .then(function(j){
          if(dot){dot.className="dot "+(j.status==="ok"?"ok":"fail");}
          if(j.status==="ok")okCount++;else failCount++;
          // 如果服务有 metrics 字段，并行拉一次
          if(s.metrics){
            fetch(s.metrics.replace("{host}",HOST),{cache:"no-store",mode:"cors"})
              .then(function(r){return r.json()})
              .then(function(m){
                var st=document.getElementById("stats-"+s.port);
                if(!st)return;
                var d=m.daily||{}, c=m.counters||{};
                var parts=[];
                if(d.history_total)parts.push("搜 "+d.history_total);
                if(d.fav_total)parts.push("藏 "+d.fav_total);
                if(c.search_ok)parts.push("ok "+c.search_ok);
                if(c.search_352)parts.push("352×"+c.search_352);
                st.textContent=parts.join(" · ")||"";
              }).catch(function(){});
          }
        })
        .catch(function(){
          if(dot){dot.className="dot fail";}
          failCount++;
        });
    });
    Promise.allSettled(promises).then(function(){
      foot.textContent=okCount+" online · "+failCount+" offline";
    });
  }
  checkAll();
  setInterval(checkAll,30000);
})();
</script></body></html>'''

@app.route("/")
def index():
    import json
    svc_js = json.dumps(SERVICES, ensure_ascii=False)
    return HTML.replace("__SERVICES__", svc_js)

if __name__ == "__main__":
    print(f"🎛  控制台: http://{_lan_ip()}:8080/")
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=8080, threads=4)
    except ImportError:
        app.run(host="0.0.0.0", port=8080, threaded=True)
