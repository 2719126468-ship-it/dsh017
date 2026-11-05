#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BiliClient：B站 WBI 签名客户端"""
import os
import json
import time
import urllib.parse
from functools import reduce
from hashlib import md5


try:
    from curl_cffi import requests as http_requests
    USE_CFFI = True
except ImportError:
    import requests as http_requests
    USE_CFFI = False

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")

MIXIN_KEY_ENC_TAB = [
    46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,
    27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,
    37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,
    22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52,
]

class BiliClient:
    def __init__(self):
        self.s = http_requests.Session(impersonate="chrome120") if USE_CFFI else http_requests.Session()
        self.s.headers.update({"User-Agent":UA,"Referer":"https://www.bilibili.com/","Accept":"application/json, text/plain, */*"})
        self._keys=None; self._ts=0; self._warmed=False
    def warmup(self):
        if self._warmed: return
        try:
            self.s.get("https://www.bilibili.com/", timeout=10)
            spi = self.s.get("https://api.bilibili.com/x/frontend/finger/spi", timeout=10).json()
            if spi.get("code") == 0:
                for k in ("b_3", "b_4"):
                    v = (spi.get("data") or {}).get(k)
                    if v: self.s.cookies.set(k, v, domain=".bilibili.com")
        except Exception:
            pass
        self._warmed = True
    def keys(self):
        if self._keys and time.time()-self._ts<15*3600: return self._keys
        self.warmup()
        r=self.s.get("https://api.bilibili.com/x/web-interface/nav",timeout=10).json()
        w=(r.get("data") or {}).get("wbi_img")
        if not w: raise RuntimeError("no wbi_img")
        ik=w["img_url"].rsplit("/",1)[-1].split(".")[0]
        sk=w["sub_url"].rsplit("/",1)[-1].split(".")[0]
        self._keys=(ik,sk); self._ts=time.time(); return self._keys
    def sign(self,p):
        ik,sk=self.keys(); raw=ik+sk
        mk=reduce(lambda s,i:s+raw[i],MIXIN_KEY_ENC_TAB,"")[:32]
        p=dict(p); p["wts"]=round(time.time()); p=dict(sorted(p.items()))
        p={k:"".join(c for c in str(v) if c not in "!'()*") for k,v in p.items()}
        q=urllib.parse.urlencode(p,quote_via=urllib.parse.quote,safe="")
        p["w_rid"]=md5((q+mk).encode()).hexdigest(); return p
    def get_audio_url(self, bvid, cid=None):
        """fnval=16 拿 DASH 音频流，返回 (url, quality_id, title)"""
        info = self.s.get("https://api.bilibili.com/x/web-interface/view",
                          params={"bvid": bvid}, timeout=15).json()
        if info.get("code") != 0:
            raise RuntimeError("详情失败: " + info.get("message", ""))
        if not cid:
            cid = info["data"]["cid"]
        sp = self.sign({"bvid": bvid, "cid": cid, "qn": 80,
                        "fnval": 16, "fourk": 1})
        r = self.s.get("https://api.bilibili.com/x/player/wbi/playurl",
                       params=sp, timeout=20).json()
        if r.get("code") != 0:
            raise RuntimeError("音频地址失败: " + r.get("message", ""))
        audios = (r.get("data") or {}).get("dash", {}).get("audio") or []
        if not audios:
            raise RuntimeError("无 dash.audio，可能需要登录或视频无音频")
        a = audios[0]
        return a["baseUrl"], a.get("id", 0), info["data"]["title"]

    def search(self, kw, page=1, order="totalrank", search_type="video", duration=0):
        self.warmup()
        if search_type not in ("video", "media_bangumi", "media_ft"):
            search_type = "video"
        try: duration = int(duration)
        except: duration = 0
        if duration not in (0, 1, 2, 3, 4):
            duration = 0
        params = {
            "search_type": search_type,
            "keyword": kw,
            "page": page,
            "page_size": 20,
            "order": order if order in ("totalrank","click","pubdate","dm","stow") else "totalrank",
        }
        if search_type == "video" and duration:
            params["duration"] = duration
        sp = self.sign(params)
        r = self.s.get("https://api.bilibili.com/x/web-interface/wbi/search/type",
                       params=sp, timeout=20)
        try: return r.json()
        except Exception: return {"code":-999,"message":r.text[:200]}






_START_TS = int(time.time())

# 共享实例（全项目唯一）
client = BiliClient()
