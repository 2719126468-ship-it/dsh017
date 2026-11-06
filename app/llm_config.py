#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM 配置：ZHIPU API + 预设目录"""
import os


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PRESET_DIR = os.path.abspath(os.environ.get("DSH017_PRESET_DIR", os.path.join(_PROJECT_ROOT, "presets")))
os.makedirs(_PRESET_DIR, exist_ok=True)

ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")
ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
ZHIPU_MODEL = "glm-4.7-flash"
