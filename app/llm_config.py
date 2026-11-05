#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM 配置：ZHIPU API + 预设目录"""
import os


_PRESET_DIR = "/root/presets"
try:
    __import__("os").makedirs(_PRESET_DIR, exist_ok=True)
except Exception: pass

ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")
ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
ZHIPU_MODEL = "glm-4.7-flash"
