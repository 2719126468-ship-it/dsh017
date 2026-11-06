#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM 配置：ZHIPU API + 预设目录"""
import os
import shutil


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PRESET_DIR = os.path.abspath(os.environ.get("DSH017_PRESET_DIR", os.path.join(_PROJECT_ROOT, "presets")))
os.makedirs(_PRESET_DIR, exist_ok=True)
# Preserve user-created presets from the previous container-specific location.
_LEGACY_PRESET_DIR = "/root/presets"
if os.path.isdir(_LEGACY_PRESET_DIR) and os.path.realpath(_LEGACY_PRESET_DIR) != os.path.realpath(_PRESET_DIR):
    for _entry in os.scandir(_LEGACY_PRESET_DIR):
        _target = os.path.join(_PRESET_DIR, _entry.name)
        if _entry.is_file() and not os.path.exists(_target):
            try:
                shutil.copy2(_entry.path, _target)
            except OSError:
                pass

ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")
ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
ZHIPU_MODEL = "glm-4.7-flash"
