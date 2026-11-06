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
from app.auth import install_auth
_auth_info = install_auth(app)
from app.ui_theme import install_theme_support
install_theme_support(app)

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
    {"name": "统一控制台", "sub": "service overview", "port": 8080,
     "url": "http://{host}:8080/", "health": "http://{host}:8080/health",
     "color": "#6b8e6b"},
    {"name": "统计控制台", "sub": "live metrics dashboard", "port": 8080,
     "url": "http://{host}:8080/stats", "health": "http://{host}:8080/health",
     "color": "#6D7CFF"},
]

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "hub", "port": 8080})

@app.route("/api/status")
def api_status():
    """Fetch backend health from loopback so the browser needs only hub auth."""
    import json
    from urllib.request import urlopen

    statuses = {"8080": {"online": True}}
    ports = sorted({int(item["port"]) for item in SERVICES if int(item["port"]) != 8080})
    for port in ports:
        entry = {"online": False}
        try:
            with urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                health_data = json.loads(response.read().decode("utf-8"))
                entry["online"] = 200 <= response.status < 300 and health_data.get("status") == "ok"
        except Exception:
            pass

        if port == 8092 and entry["online"]:
            try:
                with urlopen("http://127.0.0.1:8092/metrics", timeout=2) as response:
                    entry["metrics"] = json.loads(response.read().decode("utf-8"))
            except Exception:
                pass
        statuses[str(port)] = entry

    return jsonify({"services": statuses})

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
  var okCount=0,failCount=0,uniquePorts=Object.create(null);
  SERVICES.forEach(function(service){uniquePorts[service.port]=true;});
  var uniqueCount=Object.keys(uniquePorts).length;
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
    SERVICES.forEach(function(s){
      document.querySelectorAll('.dot[data-idx="'+s.port+'"]').forEach(function(dot){
        dot.className="dot checking";
      });
    });
    fetch("/api/status",{cache:"no-store"})
      .then(function(r){return r.ok?r.json():Promise.reject(r.status)})
      .then(function(j){
        var states=j.services||{},countedPorts=Object.create(null);
        SERVICES.forEach(function(s){
          var data=states[String(s.port)]||{};
          var online=data.online===true;
          document.querySelectorAll('.dot[data-idx="'+s.port+'"]').forEach(function(dot){
            dot.className="dot "+(online?"ok":"fail");
          });
          if(!countedPorts[s.port]){
            countedPorts[s.port]=true;
            if(online)okCount++;else failCount++;
          }
          if(s.metrics&&data.metrics){
            var m=data.metrics, d=m.daily||{}, c=m.counters||{};
            var st=document.getElementById("stats-"+s.port);
            if(st){
              var parts=[];
              if(d.history_total)parts.push("搜 "+d.history_total);
              if(d.fav_total)parts.push("藏 "+d.fav_total);
              if(c.search_ok)parts.push("ok "+c.search_ok);
              if(c.search_352)parts.push("352×"+c.search_352);
              st.textContent=parts.join(" · ")||"";
            }
          }
        });
        foot.textContent=okCount+" online · "+failCount+" offline";
      })
      .catch(function(){
        SERVICES.forEach(function(s){
          document.querySelectorAll('.dot[data-idx="'+s.port+'"]').forEach(function(dot){
            dot.className="dot fail";
          });
        });
        foot.textContent="0 online · "+uniqueCount+" offline";
      });
  }
  checkAll();
  setInterval(checkAll,30000);
})();
</script></body></html>'''


STATS_HTML = r'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>统计控制台 · DSH-017</title>
<style>
:root{--bg:#0b0e16;--surface:#141a28;--text:#eef2ff;--text-2:#adb8d2;
 --muted:#71809f;--line:rgba(160,180,230,.12);--line-2:rgba(160,180,230,.2);
 --accent:#8797ff;--ok:#54c991;--warn:#e5ac66;--bad:#ec777d}
*{box-sizing:border-box}
html,body{min-height:100%;margin:0;background:var(--bg);color:var(--text);
 font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif}
body{padding:0 16px 48px;letter-spacing:-.015em}
.page{width:100%;max-width:1040px;margin:0 auto}
header{position:sticky;top:0;z-index:10;display:flex;align-items:center;gap:14px;
 padding:15px 0;background:var(--bg);
 border-bottom:1px solid var(--line);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px)}
.back{color:var(--text-2);text-decoration:none;font-size:13px;padding:8px 10px;
 border:1px solid var(--line);border-radius:10px}
.brand{flex:1;min-width:0}.brand h1{font-size:20px;line-height:1.2;margin:0;font-weight:650;letter-spacing:-.04em}
.brand p{margin:4px 0 0;color:var(--muted);font-size:10px;letter-spacing:.13em;text-transform:uppercase}
.refresh{border:1px solid var(--line-2);background:var(--surface);color:var(--text);
 padding:9px 12px;border-radius:10px;font:inherit;font-size:12px;cursor:pointer}
.refresh:active{transform:scale(.96)}
.hero{padding:24px 0 18px;display:flex;justify-content:space-between;align-items:end;gap:14px}
.hero h2{font-size:25px;letter-spacing:-.05em;margin:0 0 5px}
.hero p{font-size:12px;color:var(--muted);margin:0}
.live{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--line);
 padding:7px 10px;border-radius:999px;font:10px/1.2 ui-monospace,monospace;color:var(--text-2)}
.live i{width:7px;height:7px;border-radius:50%;background:var(--ok);box-shadow:0 0 10px var(--ok)}
.live.stale i{background:var(--warn);box-shadow:0 0 10px var(--warn)}
.kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.card{min-width:0;padding:16px;border:1px solid var(--line);border-radius:16px;
 background:var(--surface);box-shadow:0 8px 28px rgba(0,0,0,.08)}
.kpi-label{font-size:11px;color:var(--muted);margin-bottom:9px}
.kpi-value{font-size:27px;font-weight:650;letter-spacing:-.055em;line-height:1.1;overflow-wrap:anywhere}
.kpi-note{font-size:10px;color:var(--muted);margin-top:8px}
.section{margin-top:25px}
.section-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:11px}
.section-head h3{font-size:14px;margin:0;font-weight:620}
.section-head span{font:10px ui-monospace,monospace;color:var(--muted)}
.services{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px}
.service{padding:13px;border:1px solid var(--line);border-radius:13px;background:var(--surface);min-width:0}
.svc-top{display:flex;align-items:center;gap:8px;font-size:12px;font-weight:580}
.dot{width:8px;height:8px;border-radius:50%;background:var(--muted);flex:none}
.dot.online{background:var(--ok);box-shadow:0 0 9px rgba(84,201,145,.55)}
.dot.offline{background:var(--bad);box-shadow:0 0 9px rgba(236,119,125,.4)}
.svc-meta{margin-top:7px;color:var(--muted);font:10px ui-monospace,monospace}
.detail-grid{display:grid;grid-template-columns:1.15fr .85fr;gap:10px}
.metric-row{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;padding:11px 0;border-bottom:1px solid var(--line)}
.metric-row:last-child{border-bottom:0;padding-bottom:0}
.metric-name{font-size:12px;color:var(--text-2)}
.metric-value{font:600 13px ui-monospace,monospace;color:var(--text)}
.track{height:5px;margin-top:7px;border-radius:8px;background:var(--line);overflow:hidden}
.fill{height:100%;border-radius:8px;background:linear-gradient(90deg,#687fff,#aa78f1);width:0;transition:width .5s ease}
.summary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
.summary .card{padding:13px}
.summary .kpi-value{font-size:20px}
.note{margin-top:12px;padding:12px 14px;border:1px dashed var(--line-2);border-radius:12px;
 color:var(--muted);font-size:11px;line-height:1.6}
.error{color:var(--bad)}
footer{padding:22px 0 8px;text-align:center;color:var(--muted);font:10px ui-monospace,monospace}
@media(max-width:640px){
 body{padding-inline:12px}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
 .services{grid-template-columns:repeat(2,minmax(0,1fr))}
 .detail-grid{grid-template-columns:1fr}
 .hero{align-items:start;flex-direction:column}
 header{gap:8px}.brand h1{font-size:17px}
}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
</style></head><body>
<div class="page">
 <header>
  <a class="back" href="/">← 总览</a>
  <div class="brand"><h1>统计控制台</h1><p>DSH-017 / Live telemetry</p></div>
  <button class="refresh" id="refresh">↻ 刷新</button>
 </header>
 <section class="hero">
  <div><h2>运行数据</h2><p>服务健康状态、累计操作计数与本地数据库记录</p></div>
  <div class="live" id="live"><i></i><span id="liveText">正在连接</span></div>
 </section>
 <section class="kpis" aria-label="核心指标">
  <article class="card"><div class="kpi-label">已连接服务</div><div class="kpi-value" id="online">—</div><div class="kpi-note">按服务健康检查统计</div></article>
  <article class="card"><div class="kpi-label">搜索记录</div><div class="kpi-value" id="history">—</div><div class="kpi-note">SQLite 累计记录数</div></article>
  <article class="card"><div class="kpi-label">收藏条目</div><div class="kpi-value" id="favorites">—</div><div class="kpi-note">本地收藏数据库</div></article>
  <article class="card"><div class="kpi-label">播放进度记录</div><div class="kpi-value" id="progress">—</div><div class="kpi-note">已保存的视频进度</div></article>
  <article class="card"><div class="kpi-label">成功搜索</div><div class="kpi-value" id="searchOk">—</div><div class="kpi-note">当前进程累计计数</div></article>
  <article class="card"><div class="kpi-label">播放地址解析</div><div class="kpi-value" id="playurl">—</div><div class="kpi-note">当前进程累计计数</div></article>
 </section>
 <section class="section">
  <div class="section-head"><h3>服务状态</h3><span id="uptime">BILIBILI WORKER / —</span></div>
  <div class="services" id="services"><div class="service">正在读取服务状态…</div></div>
 </section>
 <section class="section detail-grid">
  <article class="card"><div class="section-head"><h3>操作计数</h3><span>PROCESS TOTAL</span></div><div id="counterRows"></div></article>
  <article>
   <div class="section-head"><h3>数据库记录</h3><span>SQLITE TOTAL</span></div>
   <div class="summary">
    <div class="card"><div class="kpi-label">搜索历史</div><div class="kpi-value" id="dbHistory">—</div></div>
    <div class="card"><div class="kpi-label">我的收藏</div><div class="kpi-value" id="dbFav">—</div></div>
    <div class="card"><div class="kpi-label">播放进度</div><div class="kpi-value" id="dbProgress">—</div></div>
    <div class="card"><div class="kpi-label">代理流量</div><div class="kpi-value" id="proxyBytes">—</div></div>
   </div>
   <div class="note">说明：操作计数会随服务进程重启归零；SQLite 记录数会保留。页面每 15 秒自动刷新一次。</div>
  </article>
 </section>
 <footer id="updated">等待首次数据同步</footer>
</div>
<script>
(function(){
 "use strict";
 var $=function(id){return document.getElementById(id)};
 var names=[["8080","统一控制台"],["8092","Bilibili / Chat"],["8091","番茄小说"],["8084","塔罗"]];
 var metricDefs=[["search_ok","成功搜索"],["search_fail","搜索失败"],["search_352","风控 352"],["playurl_ok","播放地址解析"],["fav_added","新增收藏"],["proxy_bytes","代理流量（字节）"]];
 function fmt(n){return Number(n||0).toLocaleString("zh-CN")}
 function bytes(n){n=Number(n||0);if(n<1024)return fmt(n)+" B";var u=["KB","MB","GB","TB"],i=-1;do{n/=1024;i++}while(n>=1024&&i<u.length-1);return n.toFixed(n>=10?1:2)+" "+u[i]}
 function safe(v){return String(v==null?"":v).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
 function renderRows(c){
  var values=metricDefs.map(function(item){return Number(c[item[0]]||0)}),max=Math.max(1,Math.max.apply(Math,values));
  $("counterRows").innerHTML=metricDefs.map(function(item,i){var value=values[i],shown=item[0]==="proxy_bytes"?bytes(value):fmt(value);return '<div class="metric-row"><div><div class="metric-name">'+safe(item[1])+'</div><div class="track"><div class="fill" style="width:'+Math.round(value/max*100)+'%"></div></div></div><div class="metric-value">'+safe(shown)+'</div></div>'}).join("");
 }
 function render(data){
  var state=data.services||{},bili=state["8092"]||{},m=bili.metrics||{},d=m.daily||{},c=m.counters||{};
  var online=names.filter(function(x){return !!(state[x[0]]||{}).online}).length;
  $("online").textContent=online+" / "+names.length;
  $("history").textContent=fmt(d.history_total);$("favorites").textContent=fmt(d.fav_total);
  $("progress").textContent=fmt(d.progress_total);$("searchOk").textContent=fmt(c.search_ok);
  $("playurl").textContent=fmt(c.playurl_ok);$("dbHistory").textContent=fmt(d.history_total);
  $("dbFav").textContent=fmt(d.fav_total);$("dbProgress").textContent=fmt(d.progress_total);
  $("proxyBytes").textContent=bytes(c.proxy_bytes);
  $("uptime").textContent="BILIBILI UPTIME / "+(m.uptime==null?"—":Math.floor(m.uptime/3600)+"H "+Math.floor(m.uptime%3600/60)+"M");
  $("services").innerHTML=names.map(function(item){var v=state[item[0]]||{},on=v.online===true;return '<div class="service"><div class="svc-top"><i class="dot '+(on?"online":"offline")+'"></i><span>'+safe(item[1])+'</span></div><div class="svc-meta">:'+item[0]+' · '+(on?"ONLINE":"OFFLINE")+'</div></div>'}).join("");
  renderRows(c);$("live").classList.remove("stale");$("liveText").textContent=online+" / "+names.length+" 服务在线";
  $("updated").textContent="最近更新："+new Date().toLocaleTimeString("zh-CN");
 }
 function load(){
  $("refresh").disabled=true;$("liveText").textContent="同步中";
  fetch("/api/status",{cache:"no-store"}).then(function(r){if(!r.ok)throw new Error("HTTP "+r.status);return r.json()}).then(render)
  .catch(function(err){$("live").classList.add("stale");$("liveText").textContent="暂时无法连接";$("updated").innerHTML='<span class="error">'+safe(err.message||"读取统计失败")+'</span>'})
  .finally(function(){$("refresh").disabled=false});
 }
 $("refresh").addEventListener("click",load);load();window.setInterval(load,15000);
})();
</script></body></html>'''

@app.route("/stats")
def stats_page():
    """Serve a real metrics dashboard instead of routing back to the service list."""
    return STATS_HTML

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
