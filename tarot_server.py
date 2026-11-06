#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""塔罗 3D 翻牌 · 端口 8084 · 纯前端 + 本地牌库"""
import random

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

from flask import Flask, jsonify, request

app = Flask(__name__)
from app.auth import install_auth
_auth_info = install_auth(app)

CARDS = [
    (0,"愚者","The Fool","新的开始、冒险、纯真","鲁莽、犹豫、逃避"),
    (1,"魔术师","The Magician","创造力、意志、技能","欺骗、浪费才能"),
    (2,"女祭司","The High Priestess","直觉、秘密、潜意识","隐瞒、直觉受阻"),
    (3,"皇后","The Empress","丰饶、母性、创造","依赖、创造力受阻"),
    (4,"皇帝","The Emperor","权威、稳定、秩序","专制、固执"),
    (5,"教皇","The Hierophant","传统、信仰、指导","叛逆、教条"),
    (6,"恋人","The Lovers","爱、结合、选择","失衡、选择困难"),
    (7,"战车","The Chariot","意志、胜利、前进","失控、方向错误"),
    (8,"力量","Strength","勇气、耐心、内在力量","软弱、自我怀疑"),
    (9,"隐士","The Hermit","内省、孤独、寻找","孤立、逃避"),
    (10,"命运之轮","Wheel of Fortune","转机、循环、命运","厄运、失控"),
    (11,"正义","Justice","公正、平衡、因果","不公、失衡"),
    (12,"倒吊人","The Hanged Man","牺牲、等待、新视角","无谓牺牲、停滞"),
    (13,"死神","Death","结束、转变、重生","抗拒改变、停滞"),
    (14,"节制","Temperance","平衡、调和、耐心","失衡、极端"),
    (15,"恶魔","The Devil","欲望、束缚、执着","解脱、觉醒"),
    (16,"塔","The Tower","剧变、崩塌、启示","避免灾难、拖延"),
    (17,"星星","The Star","希望、疗愈、灵感","失望、失去信心"),
    (18,"月亮","The Moon","潜意识、幻象、不安","解开误会、真相"),
    (19,"太阳","The Sun","成功、喜悦、活力","暂时受挫、过誉"),
    (20,"审判","Judgement","觉醒、审判、重生","自我怀疑、逃避"),
    (21,"世界","The World","完成、圆满、成就","未完成、缺憾"),
]


# 22 张大阿卡纳的极简几何符号（SVG path，viewBox 0 0 64 64）
SYMBOLS = {
    0:  '<circle cx="32" cy="32" r="12" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<path d="M32 8 L32 56" stroke="currentColor" stroke-width="1.5"/>',
    1:  '<path d="M32 10 L54 50 L10 50 Z" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<circle cx="32" cy="38" r="3" fill="currentColor"/>',
    2:  '<rect x="18" y="18" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<circle cx="32" cy="32" r="6" fill="none" stroke="currentColor" stroke-width="2"/>',
    3:  '<path d="M32 14 C22 24, 22 40, 32 50 C42 40, 42 24, 32 14 Z" fill="none" stroke="currentColor" stroke-width="2"/>',
    4:  '<path d="M32 10 L46 22 L46 42 L32 54 L18 42 L18 22 Z" fill="none" stroke="currentColor" stroke-width="2"/>',
    5:  '<circle cx="32" cy="32" r="16" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<circle cx="32" cy="32" r="8" fill="none" stroke="currentColor" stroke-width="1.5"/>',
    6:  '<circle cx="22" cy="32" r="10" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<circle cx="42" cy="32" r="10" fill="none" stroke="currentColor" stroke-width="2"/>',
    7:  '<path d="M14 40 L32 12 L50 40 Z" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<path d="M22 44 L42 44" stroke="currentColor" stroke-width="2"/>',
    8:  '<path d="M22 20 Q32 12, 42 20 Q50 32, 42 44 Q32 52, 22 44 Q14 32, 22 20 Z" fill="none" stroke="currentColor" stroke-width="2"/>',
    9:  '<path d="M22 52 L32 12 L42 52 Z" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<circle cx="32" cy="22" r="3" fill="currentColor"/>',
    10: '<circle cx="32" cy="32" r="16" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<circle cx="32" cy="32" r="4" fill="currentColor"/>'
        '<path d="M32 16 L32 20 M32 44 L32 48 M16 32 L20 32 M44 32 L48 32" stroke="currentColor" stroke-width="1.5"/>',
    11: '<path d="M32 10 L32 54 M10 32 L54 32" stroke="currentColor" stroke-width="2"/>'
        '<circle cx="32" cy="32" r="10" fill="none" stroke="currentColor" stroke-width="1.5"/>',
    12: '<path d="M32 10 L32 54" stroke="currentColor" stroke-width="2"/>'
        '<circle cx="32" cy="20" r="8" fill="none" stroke="currentColor" stroke-width="2"/>',
    13: '<path d="M32 12 L32 44 M22 34 L32 44 L42 34" stroke="currentColor" stroke-width="2" fill="none"/>'
        '<circle cx="32" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="2"/>',
    14: '<path d="M16 32 Q32 16, 48 32 Q32 48, 16 32 Z" fill="none" stroke="currentColor" stroke-width="2"/>',
    15: '<path d="M14 50 L32 14 L50 50 Z" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<path d="M22 50 L32 30 L42 50" stroke="currentColor" stroke-width="1.5" fill="none"/>',
    16: '<path d="M18 50 L18 18 L46 18 L46 50" stroke="currentColor" stroke-width="2" fill="none"/>'
        '<path d="M30 22 L26 32 L34 32 L30 42" stroke="currentColor" stroke-width="2" fill="none"/>',
    17: '<path d="M32 10 L35 26 L52 26 L38 36 L44 52 L32 42 L20 52 L26 36 L12 26 L29 26 Z" fill="none" stroke="currentColor" stroke-width="1.5"/>',
    18: '<path d="M40 12 A20 20 0 1 0 40 52 A16 16 0 1 1 40 12 Z" fill="none" stroke="currentColor" stroke-width="2"/>',
    19: '<circle cx="32" cy="32" r="12" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<path d="M32 10 L32 16 M32 48 L32 54 M10 32 L16 32 M48 32 L54 32 M16 16 L20 20 M48 48 L44 44 M48 16 L44 20 M16 48 L20 44" stroke="currentColor" stroke-width="1.5"/>',
    20: '<path d="M32 12 L32 32 M22 42 L32 32 L42 42" stroke="currentColor" stroke-width="2" fill="none"/>'
        '<circle cx="32" cy="12" r="3" fill="currentColor"/>',
    21: '<circle cx="32" cy="32" r="16" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<path d="M22 32 Q32 22, 42 32 Q32 42, 22 32 Z" fill="none" stroke="currentColor" stroke-width="1.5"/>'
        '<circle cx="32" cy="32" r="2" fill="currentColor"/>',
}



@app.route("/api/draw")
def api_draw():
    n = request.args.get("n", "1")
    try:
        n = max(1, min(3, int(n)))
    except Exception:
        n = 1
    picked = random.sample(CARDS, n)
    out = []
    for idx, name, en, upright, reversed_ in picked:
        reversed_flag = random.random() < 0.4
        out.append({
            "id": idx,
            "roman": ["0","I","II","III","IV","V","VI","VII","VIII","IX","X",
                      "XI","XII","XIII","XIV","XV","XVI","XVII","XVIII","XIX",
                      "XX","XXI"][idx],
            "name": name,
            "en": en,
            "symbol": SYMBOLS.get(idx, ""),
            "reversed": reversed_flag,
            "meaning": reversed_ if reversed_flag else upright,
        })
    return jsonify({"code": 0, "cards": out})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "tarot", "port": 8084})

HTML = r'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>塔罗 · Tarot</title>
<style>
:root{--bg:#0a0a0a;--surface:#141413;--text:#faf9f5;--text-2:#b0aea5;
  --muted:#6b6a63;--line:hsla(0,0%,100%,.08);--line-2:hsla(0,0%,100%,.12);
  --clay:#d97757;--ease:cubic-bezier(.16,1,.3,1)}
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{background:var(--bg);color:var(--text);
  font-family:-apple-system,"Noto Sans SC",sans-serif;
  letter-spacing:-.02em;-webkit-font-smoothing:antialiased;min-height:100vh}
body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:radial-gradient(ellipse 50% 40% at 50% 0%, rgba(217,119,87,.08), transparent 70%);}
.wrap{max-width:720px;margin:0 auto;padding:24px 16px 80px}
h1{font-family:Georgia,"Noto Serif SC",serif;font-size:22px;font-weight:600;
  letter-spacing:-.04em;text-align:center;margin-bottom:6px}
.sub{text-align:center;font-family:monospace;font-size:10px;
  letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-bottom:28px}
.controls{display:flex;justify-content:center;margin-bottom:28px}
.btn{background:var(--clay);color:#1a0f0a;border:0;border-radius:11px;
  padding:12px 28px;font-size:14px;font-weight:600;cursor:pointer;
  margin:0 6px;transition:transform .15s var(--ease),opacity .15s var(--ease)}
.btn:active{transform:scale(.96);opacity:.85}
.btn.ghost{background:transparent;color:var(--text-2);border:1px solid var(--line-2)}
.stage{display:flex;justify-content:center;flex-wrap:wrap;gap:16px;margin-top:24px}
.card-wrap{width:180px;height:280px;perspective:1200px;flex-shrink:0}
.card{position:relative;width:100%;height:100%;transform-style:preserve-3d;
  transition:transform .7s cubic-bezier(.4,.2,.2,1);cursor:pointer;
  will-change:transform}
.card.flipped{transform:rotateY(180deg)}
.face{position:absolute;inset:0;border-radius:14px;backface-visibility:hidden;
  -webkit-backface-visibility:hidden;display:flex;flex-direction:column;
  align-items:center;justify-content:center;padding:18px;overflow:hidden;
  box-shadow:inset 0 1px 0 hsla(0,0%,100%,.08),0 4px 16px rgba(0,0,0,.4)}
.face-back{background:linear-gradient(145deg,#1a1917,#0f0f0e);border:1px solid var(--line-2)}
.face-back::before{content:"✦";font-size:48px;color:var(--clay);opacity:.7;
  text-shadow:0 0 20px rgba(217,119,87,.5)}
.face-back::after{content:"";position:absolute;inset:12px;border-radius:8px;
  border:1px solid hsla(20,65%,60%,.15);pointer-events:none}
.face-front{background:linear-gradient(145deg,#f5f1e8,#e8e3d7);
  color:#2a2723;transform:rotateY(180deg);border:1px solid hsla(40,20%,50%,.3)}
.sym{color:#8a6a4a;margin-bottom:8px;opacity:.85;line-height:0}
.roman{font-family:Georgia,serif;font-size:13px;letter-spacing:.2em;
  color:#6b5d4a;margin-bottom:10px;opacity:.7}
.card-name{font-family:Georgia,"Noto Serif SC",serif;font-size:20px;
  font-weight:600;letter-spacing:-.03em;text-align:center;line-height:1.3;margin-bottom:4px}
.card-en{font-family:monospace;font-size:9px;letter-spacing:.1em;
  text-transform:uppercase;color:#8a7c68;margin-bottom:14px}
.rev-badge{font-family:monospace;font-size:9px;letter-spacing:.14em;
  text-transform:uppercase;padding:3px 8px;border-radius:4px;
  background:rgba(217,119,87,.15);color:#c96545;margin-bottom:12px}
.meaning{font-size:11px;line-height:1.5;text-align:center;color:#4a4235;
  max-width:140px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.empty{text-align:center;padding:80px 0;color:var(--muted);
  font-family:monospace;font-size:11px;letter-spacing:.12em}
.hint{text-align:center;margin-top:16px;font-family:monospace;font-size:10px;
  letter-spacing:.1em;color:var(--muted);text-transform:uppercase}
@media(prefers-reduced-motion:reduce){
  .card{transition-duration:.01ms}}
</style></head><body>
<div class="wrap">
  <h1>塔罗 · Tarot</h1>
  <div class="sub">ask the cards</div>
  <div class="controls">
    <button class="btn" id="draw1">抽一张</button>
    <button class="btn ghost" id="draw3">三张牌</button>
  </div>
  <div class="stage" id="stage">
    <div class="empty">点击上方按钮开始</div>
  </div>
  <div class="hint" id="hint"></div>
</div>
<script>
(function(){
  var stage=document.getElementById("stage"),hint=document.getElementById("hint");
  function esc(s){return(s||"").replace(/[&<>"]/g,function(c){
    return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
  function draw(n){
    stage.innerHTML='<div class="empty">洗牌中…</div>';
    hint.textContent="";
    fetch("/api/draw?n="+n).then(function(r){return r.json()}).then(function(j){
      if(j.code!==0){stage.innerHTML='<div class="empty">抽牌失败</div>';return;}
      stage.innerHTML="";
      j.cards.forEach(function(c,i){
        var w=document.createElement("div");w.className="card-wrap";
        var card=document.createElement("div");card.className="card";
        card.innerHTML=
          '<div class="face face-back"></div>'+
          '<div class="face face-front">'+
            '<div class="sym"><svg viewBox="0 0 64 64" width="44" height="44">'+(c.symbol||'')+'</svg></div>'+
            '<div class="roman">'+esc(c.roman)+'</div>'+
            '<div class="card-name">'+esc(c.name)+'</div>'+
            '<div class="card-en">'+esc(c.en)+'</div>'+
            (c.reversed?'<div class="rev-badge">reversed · 逆位</div>':'')+
            '<div class="meaning">'+esc(c.meaning)+'</div>'+
          '</div>';
        w.appendChild(card);stage.appendChild(w);
        w.style.opacity="0";w.style.transform="translateY(20px)";
        setTimeout(function(){
          w.style.transition="opacity .5s var(--ease),transform .5s var(--ease)";
          w.style.opacity="1";w.style.transform="translateY(0)";
        },i*120);
        setTimeout(function(){card.classList.add("flipped");},600+i*180);
        card.addEventListener("click",function(){card.classList.toggle("flipped");});
      });
      hint.textContent=(n===1?"单击牌面可再次翻转":"共 "+n+" 张 · 单击任意牌可翻转");
    });
  }
  document.getElementById("draw1").addEventListener("click",function(){draw(1)});
  document.getElementById("draw3").addEventListener("click",function(){draw(3)});
})();
</script></body></html>'''

@app.route("/")
def index(): return HTML

if __name__ == "__main__":
    print(f"🔮 塔罗: http://{_lan_ip()}:8084/")
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=8084, threads=4)
    except ImportError:
        app.run(host="0.0.0.0", port=8084, threaded=True)
