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
    if len(q) > 100:
        return jsonify({"code": -1, "message": "关键词过长"}), 400
    try:
        page = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    if page < 1 or page > 100:
        return jsonify({"code": -1, "message": "页码超出范围"}), 400
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
                "title": (v.ge���q�^