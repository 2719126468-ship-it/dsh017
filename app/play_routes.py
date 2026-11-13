# app/play_routes.py - 3d 抽取（PLAY_HTML + /play）
from flask import Blueprint

PLAY_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Playing</title>
<style>
:root{--bg:#0a0a0a;--text:#faf9f5;--text-2:#b0aea5;--muted:#6b6a63;
  --line:hsla(0,0%,100%,.08);--line-2:hsla(0,0%,100%,.12);
  --clay:#d97757;--ease:cubic-bezier(.16,1,.3,1)}
.speedbar{display:flex;overflow-x:auto;white-space:nowrap;padding:10px 16px;
  -webkit-overflow-scrolling:touch;border-bottom:1px solid var(--line)}
.speedbar::-webkit-scrollbar{display:none}
.sp{display:inline-block;padding:6px 13px;margin-right:6px;border-radius:18px;
  background:hsla(0,0%,100%,.03);border:1px solid var(--line-2);
  color:var(--text-2);font-family:monospace;font-size:11px;cursor:pointer;
  flex-shrink:0;transition:color .18s var(--ease),border-color .18s var(--ease),
             background .18s var(--ease)}
.sp.active{color:var(--clay);border-color:rgba(217,119,87,.5);
  background:rgba(217,119,87,.08)}
.sp:active{opacity:.7}
.tap-hint{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
  background:rgba(0,0,0,.72);color:#fff;padding:10px 22px;border-radius:12px;
  font-size:16px;font-weight:600;pointer-events:none;opacity:0;
  transition:opacity .25s var(--ease);z-index:5;font-family:monospace;
  letter-spacing:.04em}
.tap-hint.show{opacity:1}
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:var(--bg);color:var(--text);
  font-family:-apple-system,"Noto Sans SC",sans-serif;letter-spacing:-.02em}
.player{position:relative;width:100%;background:#000;aspect-ratio:16/9}
.player video{width:100%;height:100%;display:block;background:#000}
.player:fullscreen,.player:-webkit-full-screen{
  width:100vw;height:100vh;max-width:none;aspect-ratio:auto;
  display:flex;align-items:center;justify-content:center;
}
.player:fullscreen video,.player:-webkit-full-screen video{
  width:100%;height:100%;max-height:100vh;object-fit:contain;
}
.fullscreen-note{color:var(--muted);font-size:11px;padding:0 16px 10px}

.loading{position:absolute;inset:0;display:flex;align-items:center;
  justify-content:center;font-family:monospace;font-size:11px;
  letter-spacing:.14em;text-transform:uppercase;color:var(--clay)}
.loading.hide{display:none}
.info{padding:16px;border-bottom:1px solid var(--line);
  background:rgba(20,20,19,.55)}
.info h2{font-size:15px;font-weight:500;line-height:1.4;margin-bottom:8px}
.info .sub{font-family:monospace;font-size:10px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--muted)}
.info .sub b{color:var(--text-2);font-weight:500;margin-right:12px}
#pages{display:none;padding:12px 16px;overflow-x:auto;
  white-space:nowrap;-webkit-overflow-scrolling:touch;
  border-bottom:1px solid var(--line)}
#pages.show{display:block}
#pages::-webkit-scrollbar{display:none}
.pg{display:inline-block;padding:7px 13px;margin-right:6px;
  border-radius:8px;background:hsla(0,0%,100%,.04);
  border:1px solid var(--line-2);color:var(--text-2);
  font-size:12px;cursor:pointer;text-decoration:none;
  transition:border-color .18s var(--ease),color .18s var(--ease),
             background .18s var(--ease);max-width:200px;
  overflow:hidden;text-overflow:ellipsis;vertical-align:middle}
.pg.active{border-color:rgba(217,119,87,.55);color:var(--clay);
  background:hsla(217,119,87,.08)}
.pg:active{opacity:.7}
.dlrow{padding:12px 16px 0;display:flex;flex-wrap:wrap}
.dlbtn{display:inline-block;padding:8px 14px;border-radius:9px;
  font-family:monospace;font-size:11px;letter-spacing:.08em;
  text-transform:uppercase;text-decoration:none;margin-right:8px;
  margin-bottom:8px;transition:opacity .15s var(--ease),
  background .18s var(--ease),border-color .18s var(--ease);
  background:rgba(20,20,19,.6)}
.dlbtn:active{opacity:.6}
.dlbtn.v{color:var(--clay);border:1px solid rgba(217,119,87,.4)}
.dlbtn.a{color:var(--text-2);border:1px solid var(--line-2)}
.back{display:inline-block;padding:8px 16px 16px;color:var(--clay);
  font-family:monospace;font-size:11px;letter-spacing:.1em;
  text-transform:uppercase;text-decoration:none}
.back:active{opacity:.6}
.err{padding:16px;color:var(--clay);font-family:monospace;font-size:12px}
</style></head><body>
<div class="player">
  <div class="loading" id="ld">loading…</div>
  <video id="v" controls playsinline preload="auto"></video>
  <div class="tap-hint" id="tapHint"></div>
</div>
<div class="speedbar" id="speedbar"></div>
<div id="pages"></div>
<div class="info" id="info"></div>
<div class="dlrow">
  <a class="dlbtn v" href="javascript:void(0)" id="fullscreenBtn" aria-label="横屏全屏观看">⛶ 横屏全屏</a>
  <a class="dlbtn v" href="#" id="aiSumBtn" style="color:#4d6bfe;border-color:rgba(77,107,254,.4)">✦ AI 总结</a>
  <a class="dlbtn v" href="#" id="dlVideo">⬇ 下载视频</a>
  <a class="dlbtn a" href="#" id="dlAudio">⬇ 下载音频</a>
</div>
<a class="back" href="javascript:history.back()">← back</a>
<script>
(function(){
  var bvid = decodeURIComponent(location.pathname.split("/").pop());
  var v = document.getElementById("v"), ld = document.getElementById("ld"),
      info = document.getElementById("info"), pagesEl = document.getElementById("pages"),
      dlVideo = document.getElementById("dlVideo"), dlAudio = document.getElementById("dlAudio");
  var currentCid = null, currentPageIdx = 0, pages = [];
  var _segments = null, _segIdx = 0;
  var _retry = 0;
  var fullscreenBtn = document.getElementById("fullscreenBtn");
  var playerElement = document.querySelector(".player");

  function enterPlayerFullscreen(){
    try{
      if(typeof v.webkitEnterFullscreen === "function"){
        v.webkitEnterFullscreen();
        return;
      }
      var target = playerElement || v;
      var request = target.requestFullscreen || target.webkitRequestFullscreen;
      if(!request){
        target = v;
        request = v.requestFullscreen || v.webkitRequestFullscreen;
      }
      if(request){
        var result = request.call(target);
        if(result && typeof result.catch === "function") result.catch(function(){});
        return;
      }
      info.innerHTML = '<div class="err">当前 WebView 不支持全屏播放，请使用视频控制栏的全屏按钮。</div>';
    }catch(error){
      info.innerHTML = '<div class="err">无法进入全屏：' + esc(error.message) + '</div>';
    }
  }

  if(fullscreenBtn){
    fullscreenBtn.addEventListener("click", function(event){
      event.preventDefault();
      enterPlayerFullscreen();
    });
  }
  function syncFullscreenButton(){
    if(!fullscreenBtn) return;
    var active = !!(document.fullscreenElement || document.webkitFullscreenElement);
    fullscreenBtn.textContent = active ? "⛶ 退出全屏" : "⛶ 横屏全屏";
  }
  document.addEventListener("fullscreenchange", syncFullscreenButton);
  document.addEventListener("webkitfullscreenchange", syncFullscreenButton);
  v.addEventListener("webkitbeginfullscreen", function(){
    if(fullscreenBtn) fullscreenBtn.textContent = "⛶ 退出全屏";
  });
  v.addEventListener("webkitendfullscreen", function(){
    if(fullscreenBtn) fullscreenBtn.textContent = "⛶ 横屏全屏";
  });

  function esc(s){return(s||"").replace(/[&<>"]/g,function(c){
    return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}

  function fmtDur(sec){
    if (!sec || sec < 60) return (sec||0) + "s";
    var m = Math.floor(sec/60), s = sec%60;
    return m + ":" + (s<10?"0":"") + s;
  }

  function setDlLinks(){
    if (!currentCid) return;
    dlVideo.href = "/api/video?bvid=" + encodeURIComponent(bvid) + "&cid=" + currentCid;
    dlAudio.href = "/api/audio?bvid=" + encodeURIComponent(bvid) + "&cid=" + currentCid;
  }

  function renderPages(){
    if (pages.length <= 1) { pagesEl.classList.remove("show"); return; }
    pagesEl.classList.add("show");
    var h = "";
    pages.forEach(function(p, i){
      var label = "P" + (i+1);
      if (p.part) label += " · " + p.part;
      label += " (" + fmtDur(p.duration) + ")";
      h += '<a class="pg' + (i===0?" active":"") + '" data-cid="' + p.cid + '" data-i="' + i + '" href="javascript:void(0)">' + esc(label) + '</a>';
    });
    pagesEl.innerHTML = h;
    var els = pagesEl.querySelectorAll(".pg");
    Array.prototype.forEach.call(els, function(el){
      el.addEventListener("click", function(){
        var cid = parseInt(el.getAttribute("data-cid"), 10);
        var i = parseInt(el.getAttribute("data-i"), 10);
        Array.prototype.forEach.call(els, function(x){ x.classList.remove("active"); });
        el.classList.add("active");
        _retry = 0;
        loadPlay(cid, i);
      });
    });
  }

  function loadPlay(cid, pageIdx){
    if (typeof pageIdx === "number") currentPageIdx = pageIdx;
    ld.classList.remove("hide");
    var u = "/api/playurl?bvid=" + encodeURIComponent(bvid);
    if (cid) u += "&cid=" + cid;
    return fetch(u)
      .then(function(r){return r.json()})
      .then(function(j){
        if(j.code!==0)throw new Error(j.message||("code "+j.code));
        currentCid = j.cid || cid || null;
        setDlLinks();
        // 多段支持：urls 是数组，顺序播放
        var segs = j.urls || (j.url ? [j.url] : []);
        if (segs.length > 1) {
          _segments = segs.slice();
          _segIdx = 0;
          v.src = segs[0];
          v.play().catch(function(){});
        } else {
          _segments = null;
          _segIdx = 0;
          v.src = j.url;
          v.play().catch(function(){});
        }
        ld.classList.add("hide");
        var pgLabel = pages.length > 1 ?
          '<b>P' + (currentPageIdx+1) + '/' + pages.length + '</b>' : '';
        info.innerHTML = '<h2>' + esc(j.title) + '</h2>' +
          '<div class="sub">' + pgLabel +
          '<b>' + esc(j.author) + '</b>Q' + (j.quality||"?") + ' · ' +
          (j.size ? (j.size/1048576).toFixed(1)+" MB" : "") + '</div>';
        document.title = j.title +
          (pages.length > 1 ? " · P" + (currentPageIdx+1) : "");
      })
      .catch(function(e){
        ld.classList.add("hide");
        info.innerHTML = '<div class="err">加载失败: ' + esc(e.message) + '</div>';
      });
  }

  v.addEventListener("ended", function(){
    if (_segments && _segIdx < _segments.length - 1) {
      _segIdx++;
      v.src = _segments[_segIdx];
      v.play().catch(function(){});
      info.innerHTML = '<div class="err" style="color:#b0aea5">分段视频 · 第 ' + (_segIdx+1) + '/' + _segments.length + ' 段</div>';
    }
  });

  v.addEventListener("error", function(){
    if (_retry < 2) {
      _retry++;
      info.innerHTML = '<div class="err">链接过期，自动刷新中…(' + _retry + '/2)</div>';
      loadPlay(currentCid, currentPageIdx);
    } else {
      info.innerHTML = '<div class="err">多次失败，请返回重进</div>';
    }
  });

  fetch("/api/pages?bvid=" + encodeURIComponent(bvid))
    .then(function(r){return r.json()})
    .then(function(j){
      if (j.code === 0) {
        pages = j.pages || [];
        renderPages();
        currentCid = pages.length ? pages[0].cid : null;
        setDlLinks();
        loadPlay(currentCid, 0);
      } else {
        loadPlay(null, 0);
      }
    })
    .catch(function(){ loadPlay(null, 0); });
})();
</script><script>
(function(){
  var bvid=decodeURIComponent(location.pathname.split("/").pop());
  var v=document.getElementById('v');
  var dlrow=document.querySelector('.dlrow');
  if(!dlrow||!v) return;
  var favBtn=document.createElement('a');
  favBtn.className='dlbtn';
  favBtn.href='javascript:void(0)';
  favBtn.style.cssText='color:#b0aea5;border:1px solid hsla(0,0%,100%,.12)';
  favBtn.textContent='☆ 收藏';
  dlrow.appendChild(favBtn);
  var faved=false;
  function refreshFav(){
    fetch('/api/fav/check?bvid='+encodeURIComponent(bvid)).then(function(r){return r.json()}).then(function(j){
      if(j.code===0){
        faved=j.faved;
        favBtn.textContent=faved?'★ 已收藏':'☆ 收藏';
        favBtn.style.color=faved?'#d97757':'#b0aea5';
        favBtn.style.borderColor=faved?'rgba(217,119,87,.4)':'hsla(0,0%,100%,.12)';
      }
    }).catch(function(){});
  }
  refreshFav();
  favBtn.addEventListener('click',function(){
    var title=(document.querySelector('.info h2')||{}).textContent||'';
    fetch('/api/fav',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({bvid:bvid,title:title,cover:'',author:''})
    }).then(function(r){return r.json()}).then(function(j){
      if(j.code===0) refreshFav();
    }).catch(function(){});
  });
  function getCurCid(){
    var pg=document.querySelector('.pg.active');
    if(pg) return parseInt(pg.getAttribute('data-cid'),10)||0;
    return 0;
  }
  var lastSave=0;
  v.addEventListener('timeupdate',function(){
    var now=Date.now();
    if(now-lastSave<5000) return;
    lastSave=now;
    if(!v.duration||v.duration<30) return;
    fetch('/api/progress',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({bvid:bvid,cid:getCurCid(),position:v.currentTime,duration:v.duration})
    }).catch(function(){});
  });
  setTimeout(function(){
    var cid=getCurCid();
    fetch('/api/progress?bvid='+encodeURIComponent(bvid)+'&cid='+cid)
      .then(function(r){return r.json()})
      .then(function(j){
        if(j.code!==0||!j.position||j.position<10) return;
        if(j.duration&&j.position>j.duration*0.95) return;
        var bar=document.createElement('div');
        bar.style.cssText='position:fixed;left:16px;right:16px;bottom:20px;background:#1c1c1a;border:1px solid rgba(217,119,87,.4);border-radius:var(--radius-lg);padding:12px 16px;display:flex;align-items:center;z-index:50;box-shadow:0 8px 24px rgba(0,0,0,.6)';
        var m=Math.floor(j.position/60),sec=Math.floor(j.position%60);
        var tstr=m+':'+(sec<10?'0':'')+sec;
        bar.innerHTML='<div style="flex:1;font-size:13px;color:#faf9f5">继续上次播放 · '+tstr+'</div>'+
          '<button id="resumeBtn" style="background:#d97757;color:#1a0f0a;border:0;border-radius:9px;padding:8px 16px;font-size:12px;font-weight:600;margin-right:8px;cursor:pointer">继续</button>'+
          '<button id="skipBtn" style="background:transparent;color:#6b6a63;border:1px solid hsla(0,0%,100%,.12);border-radius:9px;padding:8px 12px;font-size:12px;cursor:pointer">忽略</button>';
        document.body.appendChild(bar);
        document.getElementById('resumeBtn').addEventListener('click',function(){
          v.currentTime=j.position; v.play().catch(function(){}); bar.remove();
        });
        document.getElementById('skipBtn').addEventListener('click',function(){ bar.remove(); });
      }).catch(function(){});
  },2000);
})();
</script>

<script>
(function(){
  var v = document.getElementById('v');
  if(!v) return;
  var speedbar = document.getElementById('speedbar');
  var tapHint = document.getElementById('tapHint');
  if(!speedbar) return;

  // ===== 倍速 =====
  var SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2];
  var savedSpeed = parseFloat(localStorage.getItem('bili_speed') || '1');
  if (SPEEDS.indexOf(savedSpeed) === -1) savedSpeed = 1;
  v.playbackRate = savedSpeed;

  function renderSpeeds(){
    speedbar.innerHTML = '';
    SPEEDS.forEach(function(sp){
      var el = document.createElement('span');
      el.className = 'sp' + (sp === savedSpeed ? ' active' : '');
      el.textContent = sp + 'x';
      el.addEventListener('click', function(){
        savedSpeed = sp;
        v.playbackRate = sp;
        try{ localStorage.setItem('bili_speed', String(sp)); }catch(e){}
        renderSpeeds();
      });
      speedbar.appendChild(el);
    });
  }
  renderSpeeds();

  // ===== 音量记忆 =====
  var savedVol = parseFloat(localStorage.getItem('bili_vol') || '1');
  if(savedVol >= 0 && savedVol <= 1) v.volume = savedVol;
  v.addEventListener('volumechange', function(){
    try{ localStorage.setItem('bili_vol', String(v.volume)); }catch(e){}
  });

  // ===== 画中画（仅桌面Chrome） =====
  if (document.pictureInPictureEnabled && v.requestPictureInPicture) {
    var pipBtn = document.createElement('a');
    pipBtn.className = 'dlbtn';
    pipBtn.href = 'javascript:void(0)';
    pipBtn.textContent = '🖼 画中画';
    pipBtn.style.cssText = 'color:var(--text-2);border:1px solid var(--line-2)';
    pipBtn.addEventListener('click', function(){
      if (document.pictureInPictureElement) {
        document.exitPictureInPicture().catch(function(){});
      } else {
        v.requestPictureInPicture().catch(function(){});
      }
    });
    var dlrow = document.querySelector('.dlrow');
    if(dlrow) dlrow.appendChild(pipBtn);
  }

  // ===== 双击快进/快退（左30%退10s，右30%进10s） =====
  var lastTap = 0, tapTimer = null;
  var player = document.querySelector('.player') || v.parentNode;
  player.addEventListener('click', function(e){
    if(e.target !== v && e.target !== player) return;
    var now = Date.now();
    if(now - lastTap < 280){
      if(tapTimer){ clearTimeout(tapTimer); tapTimer = null; }
      var rect = player.getBoundingClientRect();
      var x = (e.clientX || e.touches && e.touches[0] && e.touches[0].clientX || 0) - rect.left;
      var pct = x / rect.width;
      if(pct < 0.3){
        v.currentTime = Math.max(0, v.currentTime - 10);
        showTapHint('-10s');
      } else if(pct > 0.7){
        v.currentTime = Math.min(v.duration || 0, v.currentTime + 10);
        showTapHint('+10s');
      } else {
        // 中间区域双击：播放/暂停
        if(v.paused) v.play().catch(function(){});
        else v.pause();
      }
      lastTap = 0;
      return;
    }
    lastTap = now;
    tapTimer = setTimeout(function(){
      // 单击：显示/隐藏原生控件
      v.controls = !v.controls;
      tapTimer = null;
    }, 280);
  });

  function showTapHint(text){
    if(!tapHint) return;
    tapHint.textContent = text;
    tapHint.classList.add('show');
    setTimeout(function(){ tapHint.classList.remove('show'); }, 600);
  }
})();
</script>

<script>
(function(){
  var btn = document.getElementById('aiSumBtn');
  if(!btn) return;
  btn.addEventListener('click', function(e){
    e.preventDefault();
    var bvid = decodeURIComponent(location.pathname.split('/').pop());
    var panel = document.getElementById('aiSumPanel');
    if(!panel){
      panel = document.createElement('div');
      panel.id = 'aiSumPanel';
      panel.style.cssText = 'position:fixed;left:16px;right:16px;bottom:80px;max-height:60vh;overflow-y:auto;background:#141413;border:1px solid rgba(77,107,254,.35);border-radius:16px;padding:18px;z-index:60;box-shadow:0 12px 40px rgba(0,0,0,.7);font-size:13px;line-height:1.7;color:#faf9f5';
      document.body.appendChild(panel);
    }
    panel.innerHTML = '<div style="font-family:monospace;font-size:10px;letter-spacing:.1em;color:#6b6a63;text-transform:uppercase;margin-bottom:10px">AI 总结生成中…</div><div style="display:flex;gap:6px"><span style="width:6px;height:6px;border-radius:50%;background:#4d6bfe;animation:pulse 1.2s infinite"></span><span style="width:6px;height:6px;border-radius:50%;background:#4d6bfe;animation:pulse 1.2s .2s infinite"></span><span style="width:6px;height:6px;border-radius:50%;background:#4d6bfe;animation:pulse 1.2s .4s infinite"></span></div>';
    panel.style.display = 'block';

    fetch('/api/summarize', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({bvid: bvid, vision: true})
    }).then(function(r){return r.json()}).then(function(j){
      if(j.code !== 0){
        panel.innerHTML = '<div style="color:#E5484D;font-family:monospace;font-size:12px">总结失败: '+esc(j.message||j.code)+'</div>';
        return;
      }
      var visTag = j.visual_used ? '<span style="font-family:monospace;font-size:9px;letter-spacing:.08em;color:#4d6bfe;border:1px solid rgba(77,107,254,.3);border-radius:4px;padding:1px 5px;margin-left:8px">视觉引擎已参与</span>' : '';
      panel.innerHTML = '<div style="display:flex;align-items:center;margin-bottom:10px"><span style="font-family:monospace;font-size:10px;letter-spacing:.1em;color:#6b6a63;text-transform:uppercase">AI 总结</span>'+visTag+'</div>'+
        '<div style="white-space:pre-wrap">'+esc(j.summary)+'</div>'+
        '<div style="margin-top:12px;text-align:right"><button onclick="this.closest(\'#aiSumPanel\').style.display=\'none\'" style="background:transparent;border:1px solid hsla(0,0%,100%,.12);border-radius:8px;padding:6px 14px;color:#6b6a63;font-family:monospace;font-size:10px;cursor:pointer">关闭</button></div>';
    }).catch(function(e){
      panel.innerHTML = '<div style="color:#E5484D;font-family:monospace;font-size:12px">请求失败: '+esc(e.message)+'</div>';
    });
  });
  function esc(s){return String(s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
})();
</script>
</body></html>"""

play_bp = Blueprint("play", __name__)

@play_bp.route("/play/<bvid>")
def play_page(bvid): return PLAY_HTML
