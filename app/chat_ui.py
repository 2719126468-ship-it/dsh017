#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chat UI：/api/chat 流式 + CHAT_HTML + /chat 页面"""
import os
import json
import time
import urllib.parse
from flask import Blueprint, request, jsonify, Response
from app.llm_config import ZHIPU_API_KEY, ZHIPU_BASE, ZHIPU_MODEL
from app.bili_client import client

chat_ui_bp = Blueprint('chat_ui', __name__)

_MAX_CHAT_MESSAGES = 100
_MAX_CHAT_CHARS = 200_000

# 模型白名单 + payload 辅助（/api/chat 依赖）
MODEL_MAP = {
    "glm-4.7-flash": "glm-4.7-flash",
}

@chat_ui_bp.route("/api/chat", methods=["POST"])
def api_chat():
    try:
        body = request.get_json(force=True, silent=True) or {}
        if not isinstance(body, dict):
            return jsonify({"code": -1, "message": "请求必须是 JSON 对象"}), 400

        messages = body.get("messages")
        if not isinstance(messages, list):
            return jsonify({"code": -1, "message": "messages 必须是数组"}), 400
        if not messages:
            return jsonify({"code": -1, "message": "messages 为空"})
        if len(messages) > _MAX_CHAT_MESSAGES:
            return jsonify({"code": -1, "message": "单次聊天最多允许100条消息"}), 413
        if any(not isinstance(message, dict) for message in messages):
            return jsonify({"code": -1, "message": "每条 message 必须是对象"}), 400

        system = body.get("system")
        if system is not None and not isinstance(system, str):
            return jsonify({"code": -1, "message": "system 必须是字符串"}), 400
        workspace = body.get("workspace")  # {file_id, name, content, version}
        open_file_id = body.get("open_file_id")  # 当前窗格里打开的文件 ID
        if workspace is not None and not isinstance(workspace, dict):
            return jsonify({"code": -1, "message": "workspace 必须是对象"}), 400
        if isinstance(workspace, dict) and not isinstance(workspace.get("content", ""), str):
            return jsonify({"code": -1, "message": "workspace.content 必须是字符串"}), 400

        payload_chars = len(json.dumps(messages, ensure_ascii=False, separators=(",", ":")))
        payload_chars += len(system or "")
        if isinstance(workspace, dict):
            payload_chars += len(json.dumps(workspace, ensure_ascii=False, separators=(",", ":")))
        if payload_chars > _MAX_CHAT_CHARS:
            return jsonify({"code": -1, "message": "聊天上下文超过200000字符限制"}), 413

        # 如果有 workspace 上下文，拼到 system 里
        if workspace and isinstance(workspace, dict):
            ws_sys = (
                "当前工作区：打开的文件 %s (id=%s, version=%s)。\n"
                "文件内容：\n```\n%s\n```\n"
                "当用户要求修改这个文件时，你必须在回复的最后输出一个特殊编辑块，格式：\n"
                "```workspace_edit\n"
                '{"file_id": %s, "old_str": "要替换的原文（必须在文件中唯一）", "new_str": "替换后的新内容", "base_version": %s}\n'
                "```\n"
                "规则：old_str 必须唯一存在；新增内容时 old_str 用空字符串；"
                "每次只输出一个编辑块；块本身不会显示给用户，块外文字会显示。\n"
            ) % (
                workspace.get("name","?"),
                workspace.get("file_id","?"),
                workspace.get("version",1),
                workspace.get("content",""),
                workspace.get("file_id","null"),
                workspace.get("version",1),
            )
            system = (system + "\n\n" + ws_sys) if system else ws_sys
        # 如果传了 system 且 messages 第一条不是 system，就插入
        if system and isinstance(system, str) and system.strip():
            if not messages or messages[0].get("role") != "system":
                messages = [{"role": "system", "content": system.strip()}] + messages
    except Exception as e:
        return jsonify({"code": -500, "message": str(e)})

    headers = {
        "Authorization": "Bearer " + ZHIPU_API_KEY,
        "Content-Type": "application/json",
    }
    # 模型白名单
    MODEL_MAP = {
        "glm-4.7-flash":  "glm-4.7-flash",
        "glm-4.6v-flash": "glm-4.6v-flash",
    }
    req_model = body.get("model") or "glm-4.7-flash"
    model = MODEL_MAP.get(req_model, "glm-4.7-flash")
    # 思考强度：仅部分模型支持 reasoning_effort
    effort = body.get("effort") or "auto"
    last_err = None
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.7,
    }
    # 编辑任务关闭思考，直接出正文
    if workspace and isinstance(workspace, dict):
        payload["thinking"] = {"type": "disabled"}
    if effort in ("low", "medium", "high") and req_model == "glm-4.7-flash":
        payload["thinking"] = {"type": "enabled"}
        payload["reasoning_effort"] = effort

    def generate():
        import json
        import time as _t
        max_attempts = 3
        last_err = None
        for attempt in range(max_attempts):
            try:
                r = client.s.post(ZHIPU_BASE, headers=headers, json=payload,
                                  stream=True, timeout=180)
                # 状态码检查：429/1305 走重试，其他非 200 直接吐错误
                if r.status_code != 200:
                    try:
                        err_body = r.text[:500]
                    except Exception:
                        err_body = ""
                    is_overload = (r.status_code == 429 or
                                   "1305" in err_body or
                                   "overloaded" in err_body.lower())
                    if is_overload:
                        last_err = "1305 过载"
                        if attempt < max_attempts - 1:
                            # 第2次重试起，如果是编辑任务，切到 4.6v-flash
                            if attempt >= 1 and workspace and isinstance(workspace, dict):
                                if payload.get("model") != "glm-4.6v-flash":
                                    payload["model"] = "glm-4.6v-flash"
                                    payload.pop("thinking", None)  # 4.6v 不支持 thinking
                            wait = 3.0 * (attempt + 1)
                            yield "data: " + json.dumps(
                                {"info": "模型繁忙，%.1f秒后重试(%d/%d)... 当前模型: %s" % (
                                    wait, attempt+1, max_attempts, payload.get("model", "?"))},
                                ensure_ascii=False) + "\n\n"
                            _t.sleep(wait)
                            continue
                        else:
                            yield "data: " + json.dumps(
                                {"error": "1305 重试3次仍失败，请稍后再试"},
                                ensure_ascii=False) + "\n\n"
                            return
                    else:
                        yield "data: " + json.dumps(
                            {"error": "HTTP %d: %s" % (r.status_code, err_body)},
                            ensure_ascii=False) + "\n\n"
                        return
                content_buf = ""
                line_buf = ""
                edit_buf = ""
                in_edit = False
                pending_edits = []
                first_chunk_checked = False
                MARKER_START = "```workspace_edit"
                MARKER_END = "```"

                def check_edit_complete():
                    nonlocal in_edit, edit_buf
                    idx = edit_buf.find(MARKER_END)
                    if idx < 0:
                        return
                    json_str = edit_buf[:idx].strip()
                    try:
                        pending_edits.append(json.loads(json_str))
                    except Exception as pe:
                        pending_edits.append({"__parse_error__": str(pe), "raw": json_str[:200]})
                    in_edit = False
                    edit_buf = ""

                def feed_content(ct):
                    nonlocal content_buf, edit_buf, in_edit
                    result = []
                    if in_edit:
                        edit_buf += ct
                        check_edit_complete()
                        while pending_edits:
                            result.append(("edit", pending_edits.pop(0)))
                        return result
                    content_buf += ct
                    idx = content_buf.find(MARKER_START)
                    if idx >= 0:
                        before = content_buf[:idx]
                        edit_buf = content_buf[idx + len(MARKER_START):]
                        content_buf = ""
                        in_edit = True
                        if before:
                            result.append(("content", before))
                        check_edit_complete()
                        while pending_edits:
                            result.append(("edit", pending_edits.pop(0)))
                        return result
                    hold = 0
                    max_l = min(len(MARKER_START), len(content_buf))
                    for l in range(1, max_l + 1):
                        if MARKER_START.startswith(content_buf[-l:]):
                            hold = l
                    if hold:
                        emit = content_buf[:-hold]
                        content_buf = content_buf[-hold:]
                        if emit:
                            result.append(("content", emit))
                    else:
                        if content_buf:
                            result.append(("content", content_buf))
                        content_buf = ""
                    return result

                def flush_line(ln):
                    ln = ln.strip()
                    if not ln or not ln.startswith("data: "):
                        return
                    payload_str = ln[6:]
                    if payload_str == "[DONE]":
                        return
                    try:
                        j = json.loads(payload_str)
                    except Exception:
                        return
                    choices = j.get("choices") or []
                    if not choices:
                        return
                    delta = choices[0].get("delta", {})
                    rc = delta.get("reasoning_content", "")
                    ct = delta.get("content", "")
                    if rc:
                        yield "data: " + json.dumps(
                            {"choices":[{"delta":{"reasoning_content": rc}}]},
                            ensure_ascii=False) + "\n\n"
                    if ct:
                        for kind, val in feed_content(ct):
                            if kind == "content":
                                yield "data: " + json.dumps(
                                    {"choices":[{"delta":{"content": val}}]},
                                    ensure_ascii=False) + "\n\n"
                            elif kind == "edit":
                                edit_file_id = val.get("file_id") if isinstance(val, dict) else None
                                if open_file_id is not None and edit_file_id == open_file_id:
                                    event_type = "pane_update"
                                else:
                                    event_type = "artifact_card"
                                yield "data: " + json.dumps(
                                    {"type": event_type, "data": val},
                                    ensure_ascii=False) + "\n\n"

                for ch in r.iter_content(chunk_size=None, decode_unicode=False):
                    if not ch:
                        continue
                    txt = ch.decode("utf-8", "ignore")
                    line_buf += txt
                    if not first_chunk_checked and line_buf:
                        first_chunk_checked = True
                        if "1305" in line_buf or "overloaded" in line_buf.lower():
                            last_err = "1305 过载"
                            if attempt < max_attempts - 1:
                                wait = 3.0 * (attempt + 1)
                                yield "data: " + json.dumps(
                                    {"info": "模型繁忙，%.1f秒后重试(%d/%d)..." % (wait, attempt+1, max_attempts)},
                                    ensure_ascii=False) + "\n\n"
                                _t.sleep(wait)
                                continue
                    while "\n" in line_buf:
                        ln, line_buf = line_buf.split("\n", 1)
                        yield from flush_line(ln)
                if line_buf.strip():
                    yield from flush_line(line_buf)
                if content_buf:
                    yield "data: " + json.dumps(
                        {"choices":[{"delta":{"content": content_buf}}]},
                        ensure_ascii=False) + "\n\n"
                    content_buf = ""
                yield "data: [DONE]\n\n"
                return
            except Exception as e:
                last_err = str(e)
                if attempt < max_attempts - 1:
                    _t.sleep(1.5 * (attempt + 1))
                    continue
                yield "data: " + json.dumps({"error": last_err}) + "\n\n"
                return


    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


CHAT_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chat</title>
<style>
:root{
  /* Claude 暖调三档 */
  --bg:#FAF9F5;
  --bg-soft:#F0EEE6;
  --bg-hover:#E8E5DB;
  --text:#1F1915;
  --text-2:#5C5650;
  --muted:#9A948C;
  --border:rgba(31,25,21,.06);
  --border-2:rgba(31,25,21,.10);
  --accent:#DA7756;
  --mask-fade:#FFFFFF;
  --topbar-bg:#FFFFFF;
  --accent-hover:#C4553D;
  --accent-soft:rgba(218,119,86,.10);
  --dark:#1F1915;
  --dark-text:#FAF9F5;
  --radius-sm:6px;
  --radius:8px;
  --radius-lg:16px;
  --ease:cubic-bezier(.22,1,.36,1);
  --ease-spring:cubic-bezier(.34,1.56,.64,1);
  --dur-fast:120ms;
  --dur-base:180ms;
  --dur-panel:320ms;
  /* Claude 字体：衬线 + 无衬线 */
  --font-serif:Georgia,"Songti SC","Noto Serif SC",serif;
  --font-sans:"PingFang SC","Noto Sans SC",-apple-system,sans-serif;
}
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{background:var(--bg);color:var(--text);height:100%;
  font-family:var(--font-sans);
  letter-spacing:-.01em;-webkit-font-smoothing:antialiased;overflow:hidden}

/* ============ 外壳：桌面 flex，移动堆叠 ============ */
.shell{display:flex;height:100vh;height:100dvh;width:100%}

/* ============ 侧边栏 ============ */
.sidebar{width:280px;flex-shrink:0;background:var(--bg-soft);
  border-right:1px solid var(--border);
  display:flex;flex-direction:column;height:100%}
.sb-head{padding:18px 16px 12px;display:flex;align-items:center;gap:10px;
  border-bottom:1px solid var(--border)}
.sb-head h2{font-family:var(--font-serif);font-size:16px;font-weight:600;
  flex:1;letter-spacing:-.02em}
.sb-head .sb-close{display:none;background:none;border:0;font-size:20px;
  color:var(--text-2);cursor:pointer;padding:2px 8px;border-radius:6px;
  line-height:1}
.sb-head .sb-close:active{background:var(--bg-hover)}
.sb-body{flex:1;overflow-y:auto;padding:12px 10px}
.sb-item{display:flex;align-items:center;gap:10px;width:100%;
  padding:10px 12px;border-radius:8px;background:none;border:0;
  color:var(--text-2);font-size:13px;font-family:inherit;cursor:pointer;
  text-align:left;transition:background var(--dur-fast) var(--ease),
             color var(--dur-fast) var(--ease)}
.sb-item:active{background:var(--bg-hover)}
.sb-item.new{background:var(--bg);color:var(--text);font-weight:600;
  border:1px solid var(--border-2);margin-bottom:6px;
  
  transition:background var(--dur-fast) var(--ease),
             border-color var(--dur-fast) var(--ease)}
.sb-item.new:active{transform:scale(.97)}
.sb-item .icon{width:18px;text-align:center;font-size:14px;flex-shrink:0}
.sb-item .label{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sb-sep{height:1px;background:var(--border);margin:10px 6px}
.sb-label{font-family:monospace;font-size:9px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--muted);padding:8px 12px 4px}
.sb-select-wrap{padding:4px 12px 8px}
#presetSel{width:100%;background:var(--bg);border:1px solid var(--border-2);
  border-radius:8px;color:var(--text-2);font-size:12px;padding:8px 10px;
  outline:none;font-family:inherit;
  transition:border-color var(--dur-fast) var(--ease)}
#presetSel:focus{border-color:var(--accent)}
.sb-foot{padding:12px 16px;border-top:1px solid var(--border);
  font-family:monospace;font-size:9px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--muted)}

/* ============ 主区 ============ */
.main{flex:1;display:flex;flex-direction:row;min-width:0;position:relative}
.chat-pane{display:flex;flex-direction:column;flex:1 1 0;min-width:0;height:100%}
.canvas-pane{display:none;flex-direction:column;flex:1 1 0;min-width:0;height:100%;
  border-left:1px solid var(--border);background:var(--bg)}
.canvas-pane.open{display:flex}

/* 工作区头部 */
.canvas-header{display:flex;align-items:center;gap:8px;padding:10px 14px;
  border-bottom:1px solid var(--border);flex-shrink:0}
.canvas-back{background:none;border:0;cursor:pointer;font-size:16px;
  color:var(--text-2);padding:6px 10px;border-radius:6px}
.canvas-back:hover{background:var(--bg-hover)}
.canvas-title{flex:1;font-family:var(--font-serif);font-size:15px;font-weight:600;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.canvas-btn{background:var(--bg-soft);border:1px solid var(--border-2);
  border-radius:6px;padding:5px 12px;font-size:12px;color:var(--text-2);
  cursor:pointer;font-family:inherit}
.canvas-btn:hover{background:var(--bg-hover);color:var(--text)}
.canvas-btn.primary{background:var(--accent);color:#fff;border-color:var(--accent)}
.canvas-btn.primary:hover{background:var(--accent-hover)}
.canvas-btn:disabled{opacity:.5;cursor:not-allowed}

/* 文件列表 */
.canvas-files{flex:1;overflow-y:auto;padding:16px}
.canvas-file-item{display:flex;align-items:flex-start;gap:12px;
  padding:12px 14px;border-radius:10px;cursor:pointer;font-size:13px;
  border:1px solid transparent;
  transition:background var(--dur-fast) var(--ease),
             border-color var(--dur-fast) var(--ease),
             transform var(--dur-fast) var(--ease)}
.canvas-file-item:hover{background:var(--bg-soft);border-color:var(--border)}
.canvas-file-item:active{transform:scale(.99)}
.canvas-file-item .file-icon{width:28px;height:28px;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;
  background:var(--bg-soft);border-radius:8px;
  font-family:monospace;font-size:10px;color:var(--text-2);font-weight:600}
.canvas-file-item .file-info{flex:1;min-width:0;display:flex;
  flex-direction:column;gap:3px}
.canvas-file-item .name{font-size:13.5px;font-weight:500;color:var(--text);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.canvas-file-item .meta{display:flex;gap:10px;font-family:monospace;
  font-size:10px;letter-spacing:.04em;color:var(--muted)}
.canvas-file-item .meta span{display:inline-flex;align-items:center;gap:3px}
.canvas-file-item .ver{font-family:monospace;font-size:10px;
  color:var(--text-2);background:var(--bg-soft);padding:2px 6px;
  border-radius:4px;flex-shrink:0;align-self:flex-start;margin-top:2px}
.canvas-file-item .ver.v-multi{color:var(--accent);background:var(--accent-soft)}

/* 空状态 */
.canvas-empty{text-align:center;padding:60px 24px;color:var(--muted);
  display:flex;flex-direction:column;align-items:center;gap:14px}
.canvas-empty .empty-icon{width:56px;height:56px;border-radius:14px;
  background:var(--bg-soft);display:flex;align-items:center;
  justify-content:center;font-size:24px;opacity:.7}
.canvas-empty .empty-title{font-size:14px;color:var(--text-2);font-weight:500}
.canvas-empty .empty-hint{font-size:12px;line-height:1.6;
  font-family:monospace;letter-spacing:.02em;max-width:280px}
.canvas-empty .empty-btn{margin-top:4px;background:var(--accent);color:#fff;
  border:0;border-radius:8px;padding:9px 20px;font-size:12.5px;
  font-weight:600;cursor:pointer;font-family:inherit;
  transition:background var(--dur-fast) var(--ease),
             transform var(--dur-fast) var(--ease)}
.canvas-empty .empty-btn:hover{background:var(--accent-hover)}
.canvas-empty .empty-btn:active{transform:scale(.97)}
/* ============ Artifact 卡片 ============ */
.artifact-card{display:flex;align-items:center;gap:12px;padding:12px 14px;
  margin:12px 0;border:1px solid var(--border-2);border-radius:12px;
  background:var(--bg);cursor:pointer;max-width:360px;
  transition:border-color var(--dur-fast) var(--ease),
             background var(--dur-fast) var(--ease)}
.artifact-card:hover{border-color:var(--accent);
  background:var(--accent-soft)}
.artifact-card:active{transform:scale(.99)}
.artifact-card .ac-icon{width:36px;height:36px;border-radius:8px;
  background:var(--bg-soft);display:flex;align-items:center;
  justify-content:center;font-size:18px;flex-shrink:0}
.artifact-card .ac-info{flex:1;min-width:0}
.artifact-card .ac-title{font-size:13.5px;font-weight:600;
  color:var(--text);overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;margin-bottom:2px}
.artifact-card .ac-sub{font-family:monospace;font-size:10px;
  color:var(--muted);letter-spacing:.04em}
.artifact-card .ac-arrow{color:var(--muted);font-size:14px;flex-shrink:0}


/* 编辑器 */
.canvas-editor-wrap{flex:1;display:flex;flex-direction:column;min-height:0}
.canvas-editor-header{display:flex;align-items:center;gap:8px;
  padding:8px 14px;border-bottom:1px solid var(--border);
  background:var(--bg-soft);flex-shrink:0}
.canvas-editor-name{flex:1;font-family:monospace;font-size:12px;color:var(--text-2);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.canvas-editor-version{font-family:monospace;font-size:10px;color:var(--muted);
  background:var(--bg);padding:2px 6px;border-radius:4px}
.canvas-editor{flex:1;width:100%;padding:16px;border:0;outline:none;resize:none;
  font-family:monospace;font-size:13px;line-height:1.6;
  color:var(--text);background:var(--bg);min-height:0}

/* 文件按钮（顶栏） */
.files-btn{background:none;border:1px solid var(--border-2);border-radius:6px;
  padding:5px 10px;font-size:12px;color:var(--text-2);cursor:pointer;
  font-family:inherit;flex-shrink:0}
.files-btn:hover{background:var(--bg-hover);color:var(--text)}
.files-btn.active{background:var(--accent-soft);color:var(--accent);border-color:var(--accent)}

@media (max-width:1024px){
  .main{flex-direction:column}
  .chat-pane.hidden-mobile{display:none}
  .canvas-pane{flex:1 1 100%;border-left:0;border-top:1px solid var(--border)}
}
.topbar{display:flex;align-items:center;gap:8px;padding:10px 14px;
  border-bottom:1px solid var(--border);background:var(--topbar-bg);
  flex-shrink:0;z-index:2}
.menu-btn{display:none;background:none;border:0;font-size:18px;
  color:var(--text);cursor:pointer;padding:6px 10px;border-radius:6px;
  flex-shrink:0;transition:background var(--dur-fast) var(--ease)}
.menu-btn:active{background:var(--bg-hover)}
.topbar h1{font-family:var(--font-serif);font-size:16px;font-weight:600;
  flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  letter-spacing:-.02em}
.topbar .model{font-family:monospace;font-size:9px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--muted);background:var(--bg-soft);
  padding:4px 8px;border-radius:6px;flex-shrink:0}

/* ============ 消息区 ============ */
.messages-wrap{flex:1;position:relative;overflow:hidden;min-height:0}
.messages{height:100%;overflow-y:auto;padding:28px 24px 16px;
  display:flex;flex-direction:column;gap:28px;
  -webkit-overflow-scrolling:touch}
.messages::-webkit-scrollbar{width:6px}
.messages::-webkit-scrollbar-thumb{background:#e0e2e5;border-radius:3px}
.messages::-webkit-scrollbar-track{background:transparent}

/* 底部渐变遮罩 */
.messages-wrap::after{content:"";position:absolute;left:0;right:0;bottom:0;
  height:24px;pointer-events:none;
  background:linear-gradient(to top,var(--mask-fade),rgba(255,255,255,0))}
.messages-wrap::before{content:"";position:absolute;left:0;right:0;top:0;
  height:16px;pointer-events:none;z-index:1;
  background:linear-gradient(to bottom,var(--mask-fade),rgba(255,255,255,0))}

/* 骨架屏扫光（加载占位） */
@keyframes cds-skeleton-sweep{
  0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}
.skeleton{position:relative;overflow:hidden;background:var(--bg-soft);
  border-radius:6px;height:14px;margin:6px 0}
.skeleton::after{content:"";position:absolute;inset:0;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.6),transparent);
  animation:cds-skeleton-sweep 1.4s ease-in-out infinite}

/* 分段滑块呼吸 */
@keyframes df-pill-pending{to{opacity:.45}}
.pill-pending{animation:df-pill-pending .8s ease-in-out infinite alternate}

/* ============ 消息条目 ============ */
.msg-row{display:flex;flex-direction:column;width:100%;
  animation:msgIn var(--dur-base) var(--ease-spring) both}
@keyframes msgIn{from{opacity:0;transform:translateY(8px)}
  to{opacity:1;transform:none}}
.msg-row.user{align-items:flex-end}
.msg-row.assistant{align-items:flex-start}

/* 用户气泡：钴蓝、圆角收紧、右下切平 */
.msg-row.user .msg-body{max-width:82%;padding:11px 16px;
  background:var(--accent);color:#141413;border-radius:var(--radius);
  border-bottom-right-radius:4px;font-size:14px;line-height:1.6;
  white-space:pre-wrap;word-break:break-word;font-weight:500}

/* 助手：透明画布，无边框无背景 */
.msg-row.assistant .msg-body{max-width:100%;padding:0;
  background:transparent;color:var(--text);
  font-family:var(--font-serif);font-size:15.5px;
  line-height:1.85;white-space:pre-wrap;word-break:break-word;
  letter-spacing:-.005em}

/* 编辑态 */
.msg-row.user.editing .msg-body{display:none}
.msg-row.user.editing .edit-box{display:block}
.edit-box{display:none;width:82%;background:var(--bg-soft);
  border:1px solid var(--accent);border-radius:var(--radius);
  padding:10px 14px;box-shadow:0 0 0 3px var(--accent-soft)}
.edit-box textarea{width:100%;background:transparent;border:0;outline:none;
  color:var(--text);font-family:inherit;font-size:14px;line-height:1.6;
  resize:none;min-height:40px;max-height:180px}
.edit-box .edit-bar{display:flex;justify-content:flex-end;gap:6px;
  margin-top:8px}
.edit-box .edit-bar button{background:none;border:1px solid var(--border-2);
  border-radius:6px;padding:5px 12px;font-size:12px;color:var(--text-2);
  cursor:pointer;font-family:inherit;
  transition:background var(--dur-fast) var(--ease)}
.edit-box .edit-bar button.save{background:var(--accent);color:#fff;
  border-color:var(--accent);font-weight:600}
.edit-box .edit-bar button:active{opacity:.8}

/* 操作栏 */
.msg-actions{display:flex;gap:2px;margin-top:6px;padding:0 2px;
  opacity:0;transform:translateY(-2px);
  transition:opacity var(--dur-fast) var(--ease),transform var(--dur-fast) var(--ease)}
.msg-row:hover .msg-actions,.msg-row.show-actions .msg-actions{
  opacity:1;transform:none}
.act{background:none;border:1px solid transparent;border-radius:6px;
  padding:4px 9px;font-size:11.5px;color:var(--muted);cursor:pointer;
  font-family:inherit;display:inline-flex;align-items:center;gap:4px;
  transition:color var(--dur-fast) var(--ease),
             background var(--dur-fast) var(--ease),
             transform var(--dur-fast) var(--ease-spring)}
.act:active{transform:scale(.94)}
.act:hover{background:var(--bg-hover);color:var(--text)}
.act.copied{color:var(--accent);border-color:var(--accent-soft);
  background:var(--accent-soft)}
.act.liked{color:var(--accent)}
.act svg{width:13px;height:13px;flex-shrink:0}

/* 光标 */
.cursor{display:inline-block;width:2px;height:15px;background:var(--accent);
  margin-left:2px;vertical-align:middle;border-radius:1px;
  animation:blink .9s steps(2,start) infinite}
@keyframes blink{50%{opacity:0}}

/* 思考中 */
.typing{align-self:flex-start;padding:6px 0;display:flex;gap:5px;
  align-items:center}
.typing .dot{width:6px;height:6px;border-radius:50%;background:var(--accent);
  opacity:.4;animation:breathe 1.3s ease-in-out infinite}
.typing .dot:nth-child(2){animation-delay:.18s}
.typing .dot:nth-child(3){animation-delay:.36s}
@keyframes breathe{0%,100%{opacity:.25;transform:scale(.8)}
  50%{opacity:1;transform:scale(1.15)}}
.typing .think-text{font-family:monospace;font-size:11px;
  letter-spacing:.06em;color:var(--text-2);margin-left:4px}

/* 思考过程面板 */
.think-panel{margin-top:10px;border:1px solid var(--border);
  border-radius:10px;overflow:hidden;background:var(--bg-soft);
  font-size:12px;line-height:1.6;color:var(--text-2)}
.think-head{display:flex;align-items:center;gap:6px;padding:8px 12px;
  cursor:pointer;user-select:none;font-family:monospace;font-size:10px;
  letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.think-head .arrow{transition:transform var(--dur-fast) var(--ease)}
.think-panel.open .think-head .arrow{transform:rotate(90deg)}
.think-body{display:none;padding:0 12px 10px;white-space:pre-wrap;
  word-break:break-word;color:var(--text-2);max-height:240px;
  overflow-y:auto}
.think-panel.open .think-body{display:block}
.think-panel.collapsed:not(.open) .think-body{display:none}
.think-panel.collapsed:not(.open) .think-head .arrow{transform:none}
.think-panel.open .think-body{display:block}
.think-panel.open .think-head .arrow{transform:rotate(90deg)}

/* 欢迎 */
.welcome{text-align:center;padding:90px 20px;color:var(--muted);
  animation:welcomeIn 420ms var(--ease) both}
@keyframes welcomeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.welcome h2{font-family:var(--font-serif);font-size:22px;font-weight:600;
  color:var(--text);margin-bottom:10px;letter-spacing:-.02em}
.welcome p{font-size:12px;line-height:1.7;font-family:monospace;
  letter-spacing:.02em}

/* ============ 输入区 ============ */
.composer{padding:16px 20px;
  padding-bottom:calc(16px + env(safe-area-inset-bottom,0));
  border-top:1px solid var(--border);display:flex;gap:10px;
  flex-shrink:0;background:var(--bg);align-items:flex-end}
.composer textarea{flex:1;background:var(--bg-soft);
  border:1px solid var(--border);border-radius:var(--radius-lg);
  padding:11px 18px;color:var(--text);font-size:14px;
  line-height:1.5;outline:none;resize:none;max-height:120px;min-height:44px;
  font-family:inherit;
  transition:border-color var(--dur-base) var(--ease),
             box-shadow var(--dur-base) var(--ease),
             background var(--dur-base) var(--ease)}
.composer textarea::placeholder{color:var(--muted)}
.composer textarea:focus{border-color:var(--accent);background:#fff;
  box-shadow:0 0 0 3px var(--accent-soft)}
.composer button{flex-shrink:0;width:44px;height:44px;border-radius:50%;
  background:var(--accent);color:#fff;border:0;font-size:17px;
  cursor:pointer;display:flex;align-items:center;justify-content:center;
  transition:transform var(--dur-fast) var(--ease-spring),
             opacity var(--dur-fast) var(--ease)}
.composer button:active{transform:scale(.9)}
.composer button:disabled{opacity:.35;transform:none;cursor:default}

/* ============ 移动端：抽屉化 ============ */
.mask{display:none;position:fixed;inset:0;background:rgba(0,0,0,.35);
  z-index:90;opacity:0;pointer-events:none;
  transition:opacity var(--dur-panel) var(--ease)}
@media (max-width:1024px){
  .sidebar{position:fixed;top:0;left:0;bottom:0;z-index:100;
    width:min(86vw,320px);transform:translateX(-100%);
    transition:transform var(--dur-panel) var(--ease-spring);
    box-shadow:4px 0 24px rgba(0,0,0,.12)}
  .sidebar.open{transform:translateX(0)}
  .sb-head .sb-close{display:block}
  .menu-btn{display:block}
  .mask.show{display:block;opacity:1;pointer-events:auto}
  .main{width:100%}
}

/* 无障碍 */
@media(prefers-reduced-motion:reduce){
  *{animation-duration:.01ms!important;transition-duration:.01ms!important}
  .msg-row{animation:none;opacity:1;transform:none}
}

/* ============ 大厂动效参数 ============ */
@keyframes grapheme-reveal {
  0% { opacity: 0; filter: blur(6px); }
  100% { opacity: 1; filter: blur(0); }
}
@keyframes quiet-dot {
  0%, 8% { opacity: 0; transform: translateY(2px); }
  22% { opacity: 1; transform: translateY(-2.5px); }
  36%, 70% { opacity: 1; transform: translateY(0); }
  90%, 100% { opacity: 0; transform: translateY(0); }
}
@keyframes message-fade-up {
  0% { opacity: 0; transform: translateY(10px); }
  100% { opacity: 1; transform: translateY(0); }
}
@keyframes user-bubble-enter {
  0% { opacity: 0; transform: scale(0.92) translateY(6px); }
  100% { opacity: 1; transform: none; }
}

/* 流式字符容器 */
.grapheme-group span {
  display: inline-block;
  opacity: 0;
  filter: blur(6px);
  animation: grapheme-reveal 0.4s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

/* 思考三点 */
.typing .dot {
  animation: quiet-dot 1.5s ease-in-out infinite;
}
.typing .dot:nth-child(2) { animation-delay: 0.18s; }
.typing .dot:nth-child(3) { animation-delay: 0.36s; }

/* 消息入场 */
.msg-row { animation: message-fade-up 0.3s cubic-bezier(0.22, 1, 0.36, 1) both; }
.msg-row.user { animation: user-bubble-enter 0.25s cubic-bezier(0.34, 1.56, 0.64, 1) both; }

/* 复制反馈 */
.act.copied { animation: saved-check-decay 0.3s ease 1s forwards; }

/* ============ 按钮层级系统 ============ */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;
  font-family:inherit;cursor:pointer;border:0;outline:none;
  transition:transform var(--dur-fast) var(--ease-spring),
             background var(--dur-fast) var(--ease),
             color var(--dur-fast) var(--ease),
             box-shadow var(--dur-fast) var(--ease),
             opacity var(--dur-fast) var(--ease);
  -webkit-user-select:none;user-select:none}
.btn:disabled{opacity:.4;cursor:default;pointer-events:none}

/* 主要按钮：发送 */
.btn-primary{background:var(--accent);color:#141413;border-radius:50%;
  width:44px;height:44px;font-size:17px;font-weight:600}
.btn-primary:hover{background:#C96545}
.btn-primary:active{background:#B8573A}

/* 次要按钮：重新生成 */
.btn-secondary{background:var(--bg-soft);color:var(--text-2);
  border:1px solid var(--border-2);border-radius:8px;
  padding:6px 12px;font-size:12px}
.btn-secondary:hover{background:var(--bg-hover);color:var(--text);
  border-color:var(--border-strong)}
.btn-secondary:active{background:var(--bg-hover)}

/* 幽灵按钮：复制 */
.btn-ghost{background:transparent;color:var(--muted);
  border:1px solid transparent;border-radius:6px;
  padding:4px 9px;font-size:11.5px}
.btn-ghost:hover{background:var(--bg-hover);color:var(--text);
  border-color:var(--border)}
.btn-ghost:active{background:var(--bg-hover)}
.btn-ghost.copied{color:var(--accent);border-color:var(--accent-soft);
  background:var(--accent-soft)}

/* 危险按钮：删除 */
.btn-danger{background:transparent;color:#e5484d;
  border:1px solid rgba(229,72,77,.3);border-radius:8px;
  padding:6px 12px;font-size:12px}
.btn-danger:hover{background:rgba(229,72,77,.08)}
.btn-danger:active{transform:translateY(1px);
  box-shadow:inset 0 1px 3px rgba(229,72,77,.2)}

/* 图标按钮 */
.btn-icon{width:32px;height:32px;border-radius:8px;
  background:transparent;color:var(--muted);font-size:15px}
.btn-icon:hover{background:var(--bg-hover);color:var(--text)}

/* 输入框底部工具栏：默认隐形，聚焦/悬停显形 */
.composer-toolbar{display:flex;align-items:center;gap:8px;
  padding:6px 16px 0;opacity:0;
  transition:opacity var(--dur-base) var(--ease);
  pointer-events:none}
.composer-toolbar.visible,.composer:focus-within .composer-toolbar{
  opacity:1;pointer-events:auto}
.composer-toolbar select{background:var(--bg-soft);
  border:1px solid var(--border);border-radius:6px;
  color:var(--text-2);font-size:11px;padding:4px 8px;
  outline:none;font-family:inherit;
  transition:border-color var(--dur-fast) var(--ease)}
.composer-toolbar select:focus{border-color:var(--accent)}

/* 思考面板按钮 */
.think-toggle{background:none;border:0;cursor:pointer;
  font-family:monospace;font-size:10px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--muted);
  padding:4px 0;transition:color var(--dur-fast) var(--ease)}
.think-toggle:hover{color:var(--text-2)}

html[data-theme="dark"]{
  --bg: #121212;
  --bg-soft: #1a1a1a;
  --bg-hover: #232323;
  --text: #E0E0E0;
  --text-2: #A0A0A0;
  --muted: #6C6C6C;
  --border: rgba(255,255,255,.06);
  --border-2: rgba(255,255,255,.10);
  --accent: #D97757;
  --accent-hover: #C96545;
  --accent-soft: rgba(217,119,87,.12);
  --dark: #E0E0E0;
  --dark-text: #121212;
  --mask-fade:#121212;
  --topbar-bg:#1a1a1a;
}
html[data-theme="dark"] .msg-row.user .msg-body{
  background: #2A2420; color: #E8E0D8;
}
html[data-theme="dark"] .sidebar{
  background: #1a1a1a;
}
html[data-theme="dark"] .canvas-pane{
  background: #121212;
}
</style></head><body>

<div class="shell">
  <aside class="sidebar" id="sidebar">
    <div class="sb-head">
      <h2>智谱清言</h2>
      <button class="sb-close" id="sbClose">×</button>
    </div>
    <div class="sb-body">
      <button class="sb-item new" id="sbNew">
        <span class="icon">＋</span><span class="label">新对话</span>
      </button>
      <div class="sb-sep"></div>
      <div class="sb-label">预设</div>
      <div class="sb-select-wrap">
        <select id="presetSel"><option value="">无预设</option></select>
      </div>
      <div class="sb-label">模型</div>
      <div class="sb-select-wrap">
        <select id="modelSel">
          <option value="glm-4.7-flash">GLM-4.7-Flash · 200K</option>
          <option value="glm-4-flash">GLM-4-Flash · 128K</option>
        </select>
      </div>
      <div class="sb-label">思考强度</div>
      <div class="sb-select-wrap">
        <select id="effortSel">
          <option value="auto">自动</option>
          <option value="low">轻量 (low)</option>
          <option value="medium">标准 (medium)</option>
          <option value="high">深度 (high)</option>
        </select>
      </div>
      <div class="sb-label">权限模式</div>
      <div class="sb-select-wrap">
        <select id="permModeSel">
          <option value="ask">询问我（默认）</option>
          <option value="auto">自动应用</option>
          <option value="suggest">仅建议</option>
        </select>
      </div>
      <div class="sb-sep"></div>
      <div class="sb-label">导航</div>
      <button class="sb-item" id="sbPresets">
        <span class="icon">⚙</span><span class="label">预设管理</span>
      </button>
      <button class="sb-item" id="sbBili">
        <span class="icon">🎬</span><span class="label">返回 B 站</span>
      </button>
      <button class="sb-item" id="sbShorts">
        <span class="icon">📱</span><span class="label">短视频流</span>
      </button>
      <button class="sb-item" id="sbFav">
        <span class="icon">★</span><span class="label">我的收藏</span>
      </button>
    </div>
    <div class="sb-foot">GLM-4.7-FLASH · DSH</div>
  </aside>

  <div class="mask" id="mask"></div>

  <main class="main">
  <div class="chat-pane" id="chatPane">
    <div class="topbar">
      <button class="menu-btn" id="menuBtn">☰</button>
      <h1>智谱清言</h1>
      <button class="files-btn" id="themeBtn" title="切换深色/浅色">◐</button>
      <button class="files-btn" id="filesBtn">📄 文件</button>
      <span class="model">GLM-4.7</span>
    </div>
    <div class="messages-wrap">
      <div class="messages" id="msgs" aria-live="polite" aria-relevant="additions text">
        <div class="welcome" id="welcome">
          <h2>有什么可以帮你的？</h2>
          <p>输入消息开始对话 · 支持流式输出与预设切换</p>
        </div>
      </div>
      <button id="jumpLatest" type="button" aria-label="回到最新消息">↓ 最新消息</button>
    </div>
    <div class="composer" id="composer">
      <textarea id="input" rows="1" placeholder="给智谱清言发送消息…"></textarea>
      <button id="send" class="btn btn-primary">↑</button>
    </div>
    <div class="composer-toolbar" id="composerToolbar">
      <select id="modelSelInline">
        <option value="glm-4.7-flash">GLM-4.7-Flash</option>
        <option value="glm-4-flash">GLM-4-Flash</option>
      </select>
      <select id="effortSelInline">
        <option value="auto">自动</option>
        <option value="low">轻量</option>
        <option value="medium">标准</option>
        <option value="high">深度</option>
      </select>
    </div>
  </div>
  <div class="canvas-pane" id="canvasPane">
    <div class="canvas-header">
      <button class="canvas-back" id="canvasBack" title="返回">←</button>
      <span class="canvas-title" id="canvasTitle">工作区</span>
      <button class="canvas-btn" id="canvasNew">+ 新建</button>
      <button class="canvas-btn primary" id="canvasSave" disabled>保存</button>
    </div>
    <div class="canvas-files" id="canvasFiles">
      <div class="canvas-empty">暂无文件，点「+ 新建」创建</div>
    </div>
    <div class="canvas-editor-wrap" id="canvasEditorWrap" style="display:none">
      <div class="canvas-editor-header">
        <span class="canvas-editor-name" id="canvasEditorName"></span>
        <span class="canvas-editor-version" id="canvasEditorVersion">v1</span>
      </div>
      <textarea class="canvas-editor" id="canvasEditor" placeholder="在这里编辑…"></textarea>
    </div>
  </div>
  </main>
</div>

<script>
(function(){
  var msgs      = document.getElementById('msgs');
  var input     = document.getElementById('input');
  var sendBtn   = document.getElementById('send');
  var sidebar   = document.getElementById('sidebar');
  var mask      = document.getElementById('mask');
  var presetSel = document.getElementById('presetSel');
  var composer  = document.getElementById('composer');
  var jumpLatest = document.getElementById('jumpLatest');

  if(typeof window.wsContext === 'undefined') window.wsContext = null;
  var history = [];          // [{role, content}]
  var busy = false;
  var currentSystem = '';
  var autoFollow = true;
  var mobileRefocusAfterStream = false;

  function isNearBottom() {
    return msgs.scrollHeight - msgs.scrollTop - msgs.clientHeight < 120;
  }
  function updateJumpLatest() {
    if(jumpLatest) jumpLatest.classList.toggle('visible', !isNearBottom());
  }
  msgs.addEventListener('scroll', function() {
    autoFollow = isNearBottom();
    updateJumpLatest();
  }, {passive:true});
  if(jumpLatest) {
    jumpLatest.onclick = function() {
      autoFollow = true;
      scrollBottom(true);
      jumpLatest.classList.remove('visible');
    };
  }

  /* ================= 侧边栏 ================= */
  function openSb(){
    sidebar.classList.add('open');
    mask.classList.add('show');
    sidebar.setAttribute('aria-hidden', 'false');
  }
  function closeSb(){
    sidebar.classList.remove('open');
    mask.classList.remove('show');
    sidebar.setAttribute('aria-hidden', 'true');
  }
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape' && sidebar.classList.contains('open')) closeSb();
  });
  function isMobile(){ return window.innerWidth <= 1024; }

  document.getElementById('menuBtn').onclick = openSb;
  document.getElementById('sbClose').onclick = closeSb;
  mask.onclick = closeSb;
  document.getElementById('sbPresets').onclick = function(){ location.href='/presets'; };
  document.getElementById('sbBili').onclick = function(){ location.href='/'; };
  document.getElementById('sbShorts').onclick = function(){ location.href='/shorts'; };
  document.getElementById('sbFav').onclick = function(){ location.href='/fav'; };
  document.getElementById('sbNew').onclick = function(){ newChat(); if(isMobile()) closeSb(); };

  /* 移动端手势：左边缘起手右滑打开，左滑关闭 */
  var tx0 = 0, ty0 = 0, tracking = false;
  document.addEventListener('touchstart', function(e){
    if(!isMobile()) return;
    tx0 = e.touches[0].clientX;
    ty0 = e.touches[0].clientY;
    tracking = true;
  }, {passive:true});
  document.addEventListener('touchend', function(e){
    if(!tracking) return;
    tracking = false;
    var dx = e.changedTouches[0].clientX - tx0;
    var dy = e.changedTouches[0].clientY - ty0;
    if(Math.abs(dy) > Math.abs(dx)) return;
    if(!sidebar.classList.contains('open')){
      if(tx0 < 24 && dx > 60) openSb();
    } else {
      if(dx < -60) closeSb();
    }
  }, {passive:true});

  /* ================= 工具 ================= */
  function esc(s){return String(s||'').replace(/[&<>\"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
  function scrollBottom(force){
    if(force || autoFollow) msgs.scrollTop = msgs.scrollHeight;
    updateJumpLatest();
  }

  // Safe, dependency-free Markdown rendering for completed assistant messages.
  // Streaming stays as one text node; rich blocks are built once when the stream ends.
  function appendInlineMarkdown(parent, source) {
    var text = String(source || '');
    var tick = String.fromCharCode(96);
    var tokenPattern = new RegExp('(' + tick + '[^' + tick + ']+' + tick +
      '|\\*\\*[^*]+\\*\\*|__[^_]+__|~~[^~]+~~|\\*[^*]+\\*|_[^_]+_' +
      '|\\[[^\\]]+\\]\\(https?:\\/\\/[^\\s)]+\\))', 'g');
    var last = 0, match;
    while((match = tokenPattern.exec(text))) {
      if(match.index > last) parent.appendChild(document.createTextNode(text.slice(last, match.index)));
      var token = match[0], node = null;
      if(token.charAt(0) === tick) {
        node = document.createElement('code');
        node.className = 'md-inline-code';
        node.textContent = token.slice(1, -1);
      } else if(token.indexOf('**') === 0 || token.indexOf('__') === 0) {
        node = document.createElement('strong');
        node.textContent = token.slice(2, -2);
      } else if(token.indexOf('~~') === 0) {
        node = document.createElement('del');
        node.textContent = token.slice(2, -2);
      } else if(token.charAt(0) === '*' || token.charAt(0) === '_') {
        node = document.createElement('em');
        node.textContent = token.slice(1, -1);
      } else {
        var linkMatch = token.match(/^\\[([^\\]]+)\\]\\((https?:\\/\\/[^\\s)]+)\\)$/);
        if(linkMatch) {
          node = document.createElement('a');
          node.className = 'md-link';
          node.textContent = linkMatch[1];
          node.href = linkMatch[2];
          node.target = '_blank';
          node.rel = 'noopener noreferrer';
        }
      }
      if(node) parent.appendChild(node);
      else parent.appendChild(document.createTextNode(token));
      last = tokenPattern.lastIndex;
    }
    if(last < text.length) parent.appendChild(document.createTextNode(text.slice(last)));
  }

  function renderAssistantMarkdown(target, source) {
    target.textContent = '';
    var lines = String(source || '').replace(/\\r/g, '').split('\\n');
    var i = 0;
    var tick = String.fromCharCode(96);
    var fenceStart = new RegExp('^\\s*' + tick + tick + tick + '\\s*([a-zA-Z0-9_+.-]*)');
    var fenceEnd = new RegExp('^\\s*' + tick + tick + tick + '\\s*$');
    function isBlockStart(line) {
      return fenceStart.test(line) || /^#{1,3}\\s/.test(line) ||
        /^\\s*(?:[-*+]\\s+|\\d+\\.\\s+)/.test(line) ||
        /^\\s*>/.test(line) || /^\\s*([-*_]\\s*){3,}$/.test(line);
    }
    while(i < lines.length) {
      var line = lines[i];
      if(!line.trim()) { i++; continue; }

      var fence = line.match(fenceStart);
      if(fence) {
        var codeLines = [];
        i++;
        while(i < lines.length && !fenceEnd.test(lines[i])) codeLines.push(lines[i++]);
        if(i < lines.length) i++;
        var codeWrap = document.createElement('div');
        codeWrap.className = 'md-code md-rendered';
        var codeHead = document.createElement('div');
        codeHead.className = 'md-code-head';
        var lang = document.createElement('span');
        lang.textContent = fence[1] || 'CODE';
        codeHead.appendChild(lang);
        codeWrap.appendChild(codeHead);
        var pre = document.createElement('pre');
        var code = document.createElement('code');
        code.textContent = codeLines.join('\\n');
        pre.appendChild(code);
        codeWrap.appendChild(pre);
        target.appendChild(codeWrap);
        continue;
      }

      var heading = line.match(/^\\s*(#{1,3})\\s+(.+)$/);
      if(heading) {
        var h = document.createElement('h' + heading[1].length);
        h.className = 'md-h md-h' + heading[1].length + ' md-rendered';
        appendInlineMarkdown(h, heading[2]);
        target.appendChild(h);
        i++;
        continue;
      }

      if(/^\\s*([-*_]\\s*){3,}$/.test(line)) {
        var hr = document.createElement('hr');
        hr.className = 'md-hr';
        target.appendChild(hr);
        i++;
        continue;
      }

      if(/^\\s*>/.test(line)) {
        var quoteLines = [];
        while(i < lines.length && /^\\s*>/.test(lines[i])) {
          quoteLines.push(lines[i++].replace(/^\\s*>\\s?/, ''));
        }
        var quote = document.createElement('blockquote');
        quote.className = 'md-quote md-rendered';
        appendInlineMarkdown(quote, quoteLines.join(' '));
        target.appendChild(quote);
        continue;
      }

      var unordered = /^\\s*[-*+]\\s+/.test(line);
      var ordered = /^\\s*\\d+\\.\\s+/.test(line);
      if(unordered || ordered) {
        var list = document.createElement(ordered ? 'ol' : 'ul');
        list.className = 'md-list md-rendered';
        var matcher = ordered ? /^\\s*\\d+\\.\\s+/ : /^\\s*[-*+]\\s+/;
        while(i < lines.length && matcher.test(lines[i])) {
          var li = document.createElement('li');
          appendInlineMarkdown(li, lines[i++].replace(matcher, ''));
          list.appendChild(li);
        }
        target.appendChild(list);
        continue;
      }

      var paragraphLines = [];
      while(i < lines.length && lines[i].trim() && !isBlockStart(lines[i])) {
        paragraphLines.push(lines[i++]);
      }
      if(!paragraphLines.length) paragraphLines.push(lines[i++]);
      var p = document.createElement('p');
      p.className = 'md-p md-rendered';
      appendInlineMarkdown(p, paragraphLines.join('\\n'));
      target.appendChild(p);
    }
  }

  function flushStreamText(state) {
    if(state.pending && state.textNode) {
      state.textNode.nodeValue += state.pending;
      state.pending = '';
    }
    state.queued = false;
    if(autoFollow) scrollBottom();
  }
  function queueStreamText(state, chunk) {
    state.pending += chunk;
    if(state.queued) return;
    state.queued = true;
    requestAnimationFrame(function(){ flushStreamText(state); });
  }

  /* ================= 预设 ================= */
  fetch('/api/presets').then(function(r){return r.json()}).then(function(j){
    if(j.code !== 0 || !j.items) return;
    j.items.forEach(function(it){
      var o = document.createElement('option');
      o.value = it.name; o.textContent = it.name;
      presetSel.appendChild(o);
    });
  }).catch(function(){});

  var modelSel = document.getElementById('modelSel');
  var effortSel = document.getElementById('effortSel');
  var permModeSel = document.getElementById('permModeSel');
  var currentPermMode = 'ask';
  permModeSel.onchange = function(){ currentPermMode = permModeSel.value; };
  var modelSelInline = document.getElementById('modelSelInline');
  var effortSelInline = document.getElementById('effortSelInline');
  var composerToolbar = document.getElementById('composerToolbar');
  var currentModel = 'glm-4.7-flash';
  var currentEffort = 'auto';

  modelSel.onchange = function(){ currentModel = modelSel.value; };
  effortSel.onchange = function(){ currentEffort = effortSel.value; };
  modelSelInline.onchange = function(){ currentModel = modelSelInline.value; };
  effortSelInline.onchange = function(){ currentEffort = effortSelInline.value; };

  // 输入框聚焦/悬停时工具栏显形
  var composer = document.getElementById('composer');
  composer.addEventListener('mouseenter', function(){ composerToolbar.classList.add('visible'); });
  composer.addEventListener('mouseleave', function(){ composerToolbar.classList.remove('visible'); });
  document.getElementById('input').addEventListener('focus', function(){ composerToolbar.classList.add('visible'); });
  document.getElementById('input').addEventListener('blur', function(){ composerToolbar.classList.remove('visible'); });

  presetSel.onchange = function(){
    var n = presetSel.value;
    if(!n){ currentSystem = ''; return; }
    fetch('/api/preset/' + encodeURIComponent(n))
      .then(function(r){return r.json()})
      .then(function(j){ if(j.code===0) currentSystem = j.content; })
      .catch(function(){});
  };

  /* ================= 渲染 ================= */
  var SVG_COPY = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="5" y="5" width="9" height="9" rx="2"/><path d="M3 11V4a1 1 0 0 1 1-1h7"/></svg>';
  var SVG_CHECK = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 8.5l3 3 7-7"/></svg>';
  var SVG_REGEN = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2.5 8a5.5 5.5 0 1 1 1.6 3.9"/><path d="M2.5 12v-3.5H6"/></svg>';
  var SVG_EDIT  = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M11 2.5l2.5 2.5L5.5 13H3v-2.5z"/></svg>';
  var SVG_LIKE  = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M5 14V7l3-5 1 1v4h4a1 1 0 0 1 1 1.2l-1 5A1 1 0 0 1 12 14z"/><path d="M5 7H2v7h3"/></svg>';

  function renderAll(){
    msgs.innerHTML = '';
    if(history.length === 0){
      msgs.innerHTML = '<div class="welcome" id="welcome"><h2>有什么可以帮你的？</h2><p>输入消息开始对话 · 支持流式输出与预设切换</p></div>';
      autoFollow = true;
      updateJumpLatest();
      return;
    }
    history.forEach(function(m, idx){
      appendMessage(m, idx);
    });
    scrollBottom(true);
  }

  function appendMessage(m, idx){
    var row = document.createElement('div');
    row.className = 'msg-row ' + m.role;
    row.dataset.idx = idx;

    var body = document.createElement('div');
    body.className = 'msg-body';
    if(m.role === 'assistant') renderAssistantMarkdown(body, m.content);
    else body.textContent = m.content;
    row.appendChild(body);

    // 用户消息：编辑框 + 编辑按钮
    if(m.role === 'user'){
      var box = document.createElement('div');
      box.className = 'edit-box';
      var ta = document.createElement('textarea');
      ta.value = m.content;
      var bar = document.createElement('div');
      bar.className = 'edit-bar';
      var cancel = document.createElement('button');
      cancel.textContent = '取消';
      var save = document.createElement('button');
      save.className = 'save'; save.textContent = '保存并重发';
      bar.appendChild(cancel); bar.appendChild(save);
      box.appendChild(ta); box.appendChild(bar);
      row.appendChild(box);

      var acts = document.createElement('div');
      acts.className = 'msg-actions';
      var editBtn = document.createElement('button');
      editBtn.className = 'act';
      editBtn.innerHTML = SVG_EDIT + '编辑';
      editBtn.onclick = function(){
        row.classList.add('editing');
        ta.focus();
        ta.style.height = 'auto';
        ta.style.height = ta.scrollHeight + 'px';
      };
      cancel.onclick = function(){ row.classList.remove('editing'); };
      save.onclick = function(){
        var newText = ta.value.trim();
        if(!newText) return;
        editUserAndResend(idx, newText);
      };
      ta.oninput = function(){
        ta.style.height = 'auto';
        ta.style.height = Math.min(ta.scrollHeight, 180) + 'px';
      };
      acts.appendChild(editBtn);
      row.appendChild(acts);
    }

    // 助手消息：复制 / 重新生成 / 赞
    if(m.role === 'assistant'){
      var aacts = document.createElement('div');
      aacts.className = 'msg-actions';

      var copyBtn = document.createElement('button');
      copyBtn.className = 'act';
      copyBtn.innerHTML = SVG_COPY + '复制';
      copyBtn.onclick = function(){
        var ta2 = document.createElement('textarea');
        ta2.value = m.content;
        ta2.style.position = 'fixed'; ta2.style.opacity = '0';
        document.body.appendChild(ta2);
        ta2.select();
        try{ document.execCommand('copy'); }catch(e){}
        document.body.removeChild(ta2);
        copyBtn.innerHTML = SVG_CHECK + '已复制';
        copyBtn.classList.add('copied');
        setTimeout(function(){
          copyBtn.innerHTML = SVG_COPY + '复制';
          copyBtn.classList.remove('copied');
        }, 1500);
      };
      aacts.appendChild(copyBtn);

      var regenBtn = document.createElement('button');
      regenBtn.className = 'act';
      regenBtn.innerHTML = SVG_REGEN + '重新生成';
      regenBtn.onclick = function(){
        if(busy) return;
        regenFrom(idx);
      };
      aacts.appendChild(regenBtn);

      var likeBtn = document.createElement('button');
      likeBtn.className = 'act';
      likeBtn.innerHTML = SVG_LIKE + '赞';
      likeBtn.onclick = function(){
        likeBtn.classList.toggle('liked');
      };
      aacts.appendChild(likeBtn);

      row.appendChild(aacts);
      // 流式结束后 3 秒内保持可见
      if(m.fresh){
        row.classList.add('show-actions');
        setTimeout(function(){ row.classList.remove('show-actions'); }, 3000);
      }
    }

    msgs.appendChild(row);
    scrollBottom();
    return row;
  }

  /* ================= 请求流式 ================= */
  async function requestStream(){
    mobileRefocusAfterStream = document.activeElement === input && window.innerWidth > 768;
    busy = true;
    sendBtn.disabled = true;
    composer.classList.add('is-streaming');
    composer.setAttribute('aria-busy', 'true');
    autoFollow = isNearBottom();

    var typing = document.createElement('div');
    typing.className = 'typing';
    typing.setAttribute('aria-label', '正在生成回复');
    typing.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
    msgs.appendChild(typing);
    scrollBottom();

    var assistantRow = null;
    var fullText = '';
    var thinkShown = false;
    var streamState = {textNode:null, pending:'', queued:false};

    try{
      var resp = await fetch('/api/chat', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({messages: history, system: currentSystem,
                            model: currentModel, effort: currentEffort,
                            workspace: window.wsContext || null,
                            open_file_id: (typeof WS !== 'undefined' ? WS.currentId : null)})
      });
      if(!resp.ok) throw new Error('HTTP ' + resp.status);

      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';

      while(true){
        var r = await reader.read();
        if(r.done) break;
        buffer += decoder.decode(r.value, {stream:true});
        var lines = buffer.split('\n');
        buffer = lines.pop();

        for(var i=0; i<lines.length; i++){
          var line = lines[i].trim();
          if(!line || line.indexOf('data: ') !== 0) continue;
          var payload = line.slice(6);
          if(payload === '[DONE]') continue;
          try{
            var j = JSON.parse(payload);
            if(j.error) throw new Error(typeof j.error === 'string' ? j.error : JSON.stringify(j.error));
            if(j.info) {
              typing.setAttribute('aria-label', j.info);
              continue;
            }
            if((j.type === 'artifact_card' || j.type === 'pane_update') && j.data){
              handleArtifact(j.type, j.data);
              continue;
            }
            if(j.type === 'workspace_edit' && j.data){
              handleArtifact('artifact_card', j.data);
              continue;
            }
            if(j.type === 'error'){
              console.warn('workspace error:', j.message);
              continue;
            }
            var delta = j.choices && j.choices[0] && j.choices[0].delta;
            if(delta && delta.reasoning_content){
              if(!thinkShown && !assistantRow){
                thinkShown = true;
                typing.innerHTML = '';
                var tp = document.createElement('div');
                tp.className = 'think-panel';
                tp.innerHTML = '<div class="think-head"><span class="arrow">▸</span>思考中 <span class="tlen">(0 字)</span></div><div class="think-body"></div>';
                typing.appendChild(tp);
                tp.querySelector('.think-head').onclick = function(){
                  var isOpen = tp.classList.contains('open');
                  tp.classList.toggle('open', !isOpen);
                  tp.classList.toggle('collapsed', isOpen);
                };
                window._thinkText = '';
                window._thinkBody = tp.querySelector('.think-body');
                window._thinkLen = tp.querySelector('.tlen');
              }
              if(window._thinkBody){
                window._thinkText += delta.reasoning_content;
                window._thinkBody.textContent = window._thinkText;
                window._thinkLen.textContent = '(' + window._thinkText.length + ' 字)';
                if(autoFollow) scrollBottom();
              }
            }
            if(delta && delta.content){
              if(!assistantRow){
                var tpEl = typing.querySelector('.think-panel');
                if(tpEl){
                  tpEl.classList.add('collapsed');
                  var head = tpEl.querySelector('.think-head');
                  if(head) head.innerHTML = '<span class="arrow">▸</span>思考过程 · 点击展开';
                  msgs.insertBefore(tpEl, typing);
                }
                if(typing.parentNode) typing.remove();
                window._thinkBody = null;
                window._thinkLen = null;

                assistantRow = document.createElement('div');
                assistantRow.className = 'msg-row assistant';
                var body = document.createElement('div');
                body.className = 'msg-body streaming-text';
                streamState.textNode = document.createTextNode('');
                body.appendChild(streamState.textNode);
                var cursor = document.createElement('span');
                cursor.className = 'cursor';
                cursor.setAttribute('aria-hidden', 'true');
                body.appendChild(cursor);
                assistantRow.appendChild(body);
                msgs.appendChild(assistantRow);
              }
              fullText += delta.content;
              queueStreamText(streamState, delta.content);
            }
          }catch(pe){
            if(pe.message && pe.message.indexOf('error') !== -1) throw pe;
          }
        }
      }

      if(streamState.queued) flushStreamText(streamState);
      if(typing.parentNode) typing.remove();

      if(assistantRow){
        var bodyEl2 = assistantRow.querySelector('.msg-body');
        renderAssistantMarkdown(bodyEl2, fullText);
        history.push({role:'assistant', content: fullText, fresh: true});
        var idx = history.length - 1;
        assistantRow.dataset.idx = idx;
        attachAssistantActions(assistantRow, fullText, idx);
        assistantRow.classList.add('show-actions');
        setTimeout(function(){ assistantRow.classList.remove('show-actions'); }, 2800);
      }
    }catch(e){
      if(typing.parentNode) typing.remove();
      if(streamState.queued) flushStreamText(streamState);
      if(assistantRow) {
        var partial = assistantRow.querySelector('.msg-body');
        if(partial) partial.textContent = fullText;
      }
      var errRow = document.createElement('div');
      errRow.className = 'msg-row assistant';
      var errBody = document.createElement('div');
      errBody.className = 'msg-body';
      errBody.style.color = '#e5484d';
      errBody.textContent = '连接失败: ' + e.message;
      errRow.appendChild(errBody);
      msgs.appendChild(errRow);
      scrollBottom();
    }finally{
      busy = false;
      sendBtn.disabled = false;
      composer.classList.remove('is-streaming');
      composer.removeAttribute('aria-busy');
      if(mobileRefocusAfterStream) input.focus();
    }
  }

  function attachAssistantActions(row, text, idx){
    // 移除旧的（如果有）
    var old = row.querySelector('.msg-actions');
    if(old) old.remove();

    var acts = document.createElement('div');
    acts.className = 'msg-actions';

    var copyBtn = document.createElement('button');
    copyBtn.className = 'btn btn-ghost act';
    copyBtn.innerHTML = SVG_COPY + '复制';
    copyBtn.onclick = function(){
      var ta = document.createElement('textarea');
      ta.value = text; ta.style.position='fixed'; ta.style.opacity='0';
      document.body.appendChild(ta); ta.select();
      try{ document.execCommand('copy'); }catch(e){}
      document.body.removeChild(ta);
      copyBtn.innerHTML = SVG_CHECK + '已复制';
      copyBtn.classList.add('copied');
      setTimeout(function(){
        copyBtn.innerHTML = SVG_COPY + '复制';
        copyBtn.classList.remove('copied');
      }, 1400);
    };
    acts.appendChild(copyBtn);

    var regenBtn = document.createElement('button');
    regenBtn.className = 'btn btn-ghost act';
    regenBtn.innerHTML = SVG_REGEN + '重新生成';
    regenBtn.onclick = function(){
      if(!busy) regenFrom(idx);
    };
    acts.appendChild(regenBtn);

    var likeBtn = document.createElement('button');
    likeBtn.className = 'btn btn-ghost act';
    likeBtn.innerHTML = SVG_LIKE + '赞';
    likeBtn.onclick = function(){
      likeBtn.classList.toggle('liked');
    };
    acts.appendChild(likeBtn);

    row.appendChild(acts);
  }

  /* ================= 发送 / 重新生成 / 编辑 ================= */
  async function send(){
    var text = input.value.trim();
    if(!text || busy) return;
    input.value = '';
    input.style.height = '44px';
    history.push({role:'user', content:text});
    renderAll();
    autoFollow = true;
    scrollBottom(true);
    await requestStream();
  }

  async function regenFrom(assistantIdx){
    // 找到该助手消息前最近的一条 user
    var userIdx = -1;
    for(var i=assistantIdx-1; i>=0; i--){
      if(history[i].role === 'user'){ userIdx = i; break; }
    }
    if(userIdx < 0) return;
    // 截断到该 user
    history = history.slice(0, userIdx + 1);
    renderAll();
    await requestStream();
  }

  async function editUserAndResend(userIdx, newText){
    if(busy) return;
    history[userIdx] = {role:'user', content:newText};
    history = history.slice(0, userIdx + 1);
    renderAll();
    await requestStream();
  }

  function newChat(){
    if(busy) return;
    history = [];
    renderAll();
    input.value = '';
    input.style.height = '44px';
    if(window.innerWidth > 768) input.focus();
  }

  /* ================= 绑定 ================= */
  sendBtn.onclick = send;
  input.onkeydown = function(e){
    if(e.key === 'Enter' && !e.shiftKey){
      e.preventDefault();
      send();
    }
  };
  input.oninput = function(){
    input.style.height = '44px';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  };

  // 初始渲染
  renderAll();
})();
</script>

<script>
(function(){
  var WS = { files: [], currentId: null, currentVersion: 0, currentName: '',
             originalContent: '', view: 'list' };

  var filesBtn   = document.getElementById('filesBtn');
  var canvasPane = document.getElementById('canvasPane');
  var chatPane   = document.getElementById('chatPane');
  var canvasBack = document.getElementById('canvasBack');
  var canvasNew  = document.getElementById('canvasNew');
  var canvasSave = document.getElementById('canvasSave');
  var canvasTitle= document.getElementById('canvasTitle');
  var canvasFiles= document.getElementById('canvasFiles');
  var editorWrap = document.getElementById('canvasEditorWrap');
  var editorName = document.getElementById('canvasEditorName');
  var editorVer  = document.getElementById('canvasEditorVersion');
  var editor     = document.getElementById('canvasEditor');

  function isMobile(){ return window.innerWidth <= 1024; }

  function openCanvas(){
    canvasPane.classList.add('open');
    filesBtn.classList.add('active');
    if(isMobile()) chatPane.classList.add('hidden-mobile');
    if(WS.view === 'list') loadFileList();
  }
  function closeCanvas(){
    canvasPane.classList.remove('open');
    filesBtn.classList.remove('active');
    chatPane.classList.remove('hidden-mobile');
  }
  function toggleCanvas(){
    if(canvasPane.classList.contains('open')) closeCanvas();
    else openCanvas();
  }

  filesBtn.onclick = toggleCanvas;
  canvasBack.onclick = function(){
    if(WS.view === 'edit'){ WS.view = 'list'; renderView(); loadFileList(); }
    else closeCanvas();
  };

  function api(path, opts){
    return fetch(path, opts).then(function(r){ return r.json(); });
  }
  

  // ==== Artifact 卡片 + pane_update 处理 ====
  function handleArtifact(kind, editData){
    var editFileId = editData.file_id;
    var fileName = editData.__name__ || null;

    if(kind === 'pane_update'){
      // 已打开文件：直接 apply（走安全闸门）+ 原地更新窗格，不插卡片
      fetch('/api/workspace/apply_edit', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify(Object.assign({}, editData, {mode: currentPermMode}))
      }).then(function(r){return r.json()}).then(function(aj){
        if(aj.code === 0 && aj.auto_applied){
          if(typeof WS !== 'undefined' && WS.currentId === editFileId){
            editor.value = aj.content;
            WS.currentVersion = aj.version;
            WS.originalContent = aj.content;
            editorVer.textContent = 'v' + aj.version;
            if(window.wsContext){ window.wsContext.version = aj.version; window.wsContext.content = aj.content; }
          }
          if(typeof loadFileList === 'function') loadFileList();
        } else if(aj.code === 409){
          // 安全闸门要求确认：退回 diff 面板
          showDiff(editData);
        } else if(aj.code === 403){
          appendInfoMsg('规则禁止修改 ' + (fileName || '该文件'));
        }
      }).catch(function(){ showDiff(editData); });
      return;
    }

    // artifact_card：未打开文件，插一张信标卡片
    // 先拉文件名
    fetch('/api/workspace/files/' + editFileId)
      .then(function(r){return r.json()})
      .then(function(info){
        if(info.code !== 0) return;
        var card = renderArtifactCard(info.name, editData);
        appendCardToChat(card);
      }).catch(function(){});
  }

  function renderArtifactCard(name, editData){
    var card = document.createElement('div');
    card.className = 'artifact-card';
    var isNew = !editData.old_str;
    var actionLabel = isNew ? '新建 · 点击打开' : '已就绪 · 点击打开';
    card.innerHTML =
      '<div class="ac-icon">📄</div>' +
      '<div class="ac-info">' +
        '<div class="ac-title">' + esc(name) + '</div>' +
        '<div class="ac-sub">' + esc(actionLabel) + '</div>' +
      '</div>' +
      '<div class="ac-arrow">→</div>';
    card.onclick = function(){
      openArtifactCard(editData);
    };
    return card;
  }

  function appendCardToChat(card){
    if(typeof msgs === 'undefined') return;
    var wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;justify-content:flex-start;width:100%';
    wrap.appendChild(card);
    msgs.appendChild(wrap);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function appendInfoMsg(text){
    if(typeof msgs === 'undefined') return;
    var wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;justify-content:flex-start;width:100%';
    var m = document.createElement('div');
    m.style.cssText = 'padding:8px 14px;background:var(--bg-soft);border-radius:8px;font-family:monospace;font-size:11px;color:var(--text-2)';
    m.textContent = text;
    wrap.appendChild(m);
    msgs.appendChild(wrap);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function openArtifactCard(editData){
    // 点击卡片：打开窗格 + 走 apply_edit 应用
    fetch('/api/workspace/files/' + editData.file_id)
      .then(function(r){return r.json()})
      .then(function(info){
        if(info.code !== 0) return;
        // 打开窗格（触发工作区）
        if(typeof filesBtn !== 'undefined' && filesBtn) filesBtn.click();
        // 等待窗格打开后再 apply
        setTimeout(function(){
          fetch('/api/workspace/apply_edit', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify(Object.assign({}, editData, {mode: currentPermMode}))
          }).then(function(r){return r.json()}).then(function(aj){
            if(aj.code === 0 && aj.auto_applied){
              if(typeof openFile === 'function') openFile(editData.file_id);
            } else if(aj.code === 409){
              showDiff(editData);
            }
          }).catch(function(){});
        }, 100);
      }).catch(function(){});
  }

  // ==== 主题切换 ====
  var themeBtn = document.getElementById('themeBtn');
  var savedTheme = localStorage.getItem('theme');
  var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.setAttribute('data-theme', savedTheme || (prefersDark ? 'dark' : 'light'));
  if(themeBtn){
    themeBtn.onclick = function(){
      var cur = document.documentElement.getAttribute('data-theme');
      var next = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try{ localStorage.setItem('theme', next); }catch(e){}
    };
  }

// ==== diff 预览 + 应用 ====
  var diffPanel = null;
  var pendingEdit = null;

  function showDiff(edit){
    pendingEdit = edit;
    if(!diffPanel){
      diffPanel = document.createElement('div');
      diffPanel.id = 'diffPanel';
      diffPanel.style.cssText = 'position:fixed;left:16px;right:16px;bottom:80px;max-height:40vh;overflow-y:auto;background:#FAF9F5;border:1px solid rgba(20,20,19,.12);border-radius:12px;padding:14px;z-index:60;box-shadow:0 12px 40px rgba(0,0,0,.15);font-size:13px;line-height:1.6;color:#1F1915';
      document.body.appendChild(diffPanel);
    }
    var oldStr = edit.old_str || '';
    var newStr = edit.new_str || '';
    diffPanel.innerHTML = '<div style="font-family:monospace;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:#9A948C;margin-bottom:10px">AI 建议修改 · 请确认</div>' +
      '<div style="background:#FBE9E3;border-radius:6px;padding:8px 10px;margin-bottom:6px;font-family:monospace;font-size:12px;white-space:pre-wrap;word-break:break-word;color:#A03A1F">- ' + esc(oldStr || '(新增内容)') + '</div>' +
      '<div style="background:#E3F5E9;border-radius:6px;padding:8px 10px;margin-bottom:10px;font-family:monospace;font-size:12px;white-space:pre-wrap;word-break:break-word;color:#1F6B3A">+ ' + esc(newStr) + '</div>' +
      '<div style="display:flex;gap:8px;justify-content:flex-end">' +
        '<button id="diffIgnore" style="background:none;border:1px solid rgba(20,20,19,.12);border-radius:6px;padding:6px 14px;font-size:12px;color:#5C5650;cursor:pointer">忽略</button>' +
        '<button id="diffApply" style="background:#DA7756;border:0;border-radius:6px;padding:6px 14px;font-size:12px;color:#fff;font-weight:600;cursor:pointer">应用</button>' +
      '</div>';
    diffPanel.style.display = 'block';
    document.getElementById('diffIgnore').onclick = function(){
      diffPanel.style.display = 'none'; pendingEdit = null;
    };
    document.getElementById('diffApply').onclick = applyEdit;
  }

  function applyEdit(){
    if(!pendingEdit) return;
    var edit = pendingEdit;
    var btn = document.getElementById('diffApply');
    btn.textContent = '应用中…';
    btn.disabled = true;
    fetch('/api/workspace/apply_edit', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(Object.assign({}, edit, {mode: currentPermMode}))
    }).then(function(r){return r.json()}).then(function(j){
      btn.textContent = '应用';
      btn.disabled = false;
      if(j.code === 409){
        var reasonText = {
          'scope_violation': '越出项目作用域',
          'rule_ask': '规则要求确认',
          'mode_suggest': '仅建议模式',
          'mode_ask': '询问模式',
          'auto_downgraded': '连续拦截过多，已降级',
          'version_conflict': '文件版本冲突',
          'old_str_not_found': 'old_str 未找到',
          'old_str_not_unique': 'old_str 不唯一'
        }[j.reason] || (j.message || '需要确认');
        var reasonDiv = diffPanel.querySelector('.reason');
        if(!reasonDiv){
          reasonDiv = document.createElement('div');
          reasonDiv.className = 'reason';
          reasonDiv.style.cssText = 'background:#FFF7E6;border-radius:6px;padding:6px 10px;margin-bottom:8px;font-family:monospace;font-size:11px;color:#8B6914';
          diffPanel.insertBefore(reasonDiv, diffPanel.children[1]);
        }
        reasonDiv.textContent = '⚠ ' + reasonText;
        btn.textContent = '仍要应用';
        return;
      }
      if(j.code === 403){
        alert('规则禁止修改此文件');
        diffPanel.style.display = 'none'; pendingEdit = null;
        return;
      }
      if(j.code !== 0){
        alert(j.message || '应用失败');
        return;
      }
      // 成功
      if(WS.currentId === edit.file_id){
        editor.value = j.content;
        WS.currentVersion = j.version;
        WS.originalContent = j.content;
        editorVer.textContent = 'v' + j.version;
        if(window.wsContext){ window.wsContext.version = j.version; window.wsContext.content = j.content; }
      }
      diffPanel.style.display = 'none';
      pendingEdit = null;
      loadFileList();
    }).catch(function(e){
      btn.textContent = '应用';
      btn.disabled = false;
      alert('应用失败: ' + e.message);
    });
  }



  function loadFileList(){
    api('/api/workspace/files').then(function(j){
      if(j.code !== 0) return;
      WS.files = j.items || [];
      renderFileList();
    });
  }

  function fmtTime(ts){
    if(!ts) return '—';
    var d = new Date(ts * 1000);
    var now = new Date();
    var sameDay = d.toDateString() === now.toDateString();
    var hh = d.getHours().toString().padStart(2, '0');
    var mm = d.getMinutes().toString().padStart(2, '0');
    if(sameDay) return hh + ':' + mm;
    var M = (d.getMonth() + 1);
    var D = d.getDate();
    return M + '月' + D + '日 ' + hh + ':' + mm;
  }

  function fileIcon(name){
    var ext = (name.split('.').pop() || '').toLowerCase();
    var map = {
      'md': 'MD', 'txt': 'TXT', 'py': 'PY', 'js': 'JS',
      'json': '{}', 'html': '<>', 'css': '#', 'yml': 'Y', 'yaml': 'Y',
      'sh': '$', 'log': '·', 'csv': 'CSV'
    };
    return map[ext] || '·';
  }

  function renderFileList(){
    if(WS.files.length === 0){
      canvasFiles.innerHTML =
        '<div class="canvas-empty">' +
          '<div class="empty-icon">📄</div>' +
          '<div class="empty-title">还没有文件</div>' +
          '<div class="empty-hint">新建一个 Markdown 文件，或让 AI 帮你创建一个</div>' +
          '<button class="empty-btn" id="emptyNewBtn">新建第一个文件</button>' +
        '</div>';
      var eb = document.getElementById('emptyNewBtn');
      if(eb) eb.onclick = canvasNew.onclick;
      return;
    }
    var h = '';
    WS.files.forEach(function(f){
      var icon = fileIcon(f.name);
      var time = fmtTime(f.updated_at);
      var verCls = f.version > 1 ? 'ver v-multi' : 'ver';
      h += '<div class="canvas-file-item" data-id="' + f.id + '">' +
           '<div class="file-icon">' + esc(icon) + '</div>' +
           '<div class="file-info">' +
             '<div class="name">' + esc(f.name) + '</div>' +
             '<div class="meta">' +
               '<span>🕐 ' + esc(time) + '</span>' +
               '<span>v' + f.version + '</span>' +
             '</div>' +
           '</div>' +
           '<span class="' + verCls + '">v' + f.version + '</span>' +
           '</div>';
    });
    canvasFiles.innerHTML = h;
    Array.prototype.forEach.call(canvasFiles.querySelectorAll('.canvas-file-item'), function(el){
      el.onclick = function(){ openFile(parseInt(el.dataset.id, 10)); };
    });
  }

  function openFile(id){
    api('/api/workspace/files/' + id).then(function(j){
      if(j.code !== 0){ alert(j.message || '打开失败'); return; }
      WS.currentId = j.id;
      WS.currentVersion = j.version;
      WS.currentName = j.name;
      WS.originalContent = j.content || '';
      WS.view = 'edit';
      editor.value = j.content || '';
      window.wsContext = {
        file_id: j.id, name: j.name,
        content: j.content || '', version: j.version
      };
      renderView();
    });
  }

  function renderView(){
    if(WS.view === 'list'){
      canvasFiles.style.display = '';
      editorWrap.style.display = 'none';
      canvasTitle.textContent = '工作区';
      canvasSave.disabled = true;
    } else {
      canvasFiles.style.display = 'none';
      editorWrap.style.display = 'flex';
      canvasTitle.textContent = '编辑文件';
      editorName.textContent = WS.currentName;
      editorVer.textContent = 'v' + WS.currentVersion;
      canvasSave.disabled = false;
    }
  }

  canvasNew.onclick = function(){
    var name = prompt('文件名（如 notes.md）');
    if(!name) return;
    name = name.trim();
    if(!name) return;
    api('/api/workspace/files', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({name: name})
    }).then(function(j){
      if(j.code !== 0){ alert(j.message || '创建失败'); return; }
      openFile(j.id);
    });
  };

  canvasSave.onclick = function(){
    if(WS.currentId == null) return;
    canvasSave.disabled = true;
    canvasSave.textContent = '保存中…';
    api('/api/workspace/files/' + WS.currentId, {
      method: 'PUT',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        content: editor.value,
        base_version: WS.currentVersion
      })
    }).then(function(j){
      canvasSave.disabled = false;
      canvasSave.textContent = '保存';
      if(j.code === 409){
        alert('文件已被其他位置修改（当前 v' + j.current_version +
              '，你基于 v' + WS.currentVersion + '）。\n请点 ← 返回列表，重新打开文件后再编辑。');
        WS.currentVersion = j.current_version;
        editorVer.textContent = 'v' + WS.currentVersion + ' ⚠';
        return;
      }
      if(j.code !== 0){ alert(j.message || '保存失败'); return; }
      WS.currentVersion = j.version;
      WS.originalContent = editor.value;
      editorVer.textContent = 'v' + j.version;
      loadFileList();
    }).catch(function(e){
      canvasSave.disabled = false;
      canvasSave.textContent = '保存';
      alert('保存失败: ' + e.message);
    });
  };

  // Tab 插入两空格
  editor.addEventListener('keydown', function(e){
    if(e.key === 'Tab'){
      e.preventDefault();
      var start = this.selectionStart, end = this.selectionEnd;
      this.value = this.value.substring(0, start) + '  ' + this.value.substring(end);
      this.selectionStart = this.selectionEnd = start + 2;
    }
    // Ctrl/Cmd + S 保存
    if((e.ctrlKey || e.metaKey) && e.key === 's'){
      e.preventDefault();
      canvasSave.click();
    }
  });

  // 窗口尺寸变化时重置移动端状态
  window.addEventListener('resize', function(){
    if(!isMobile()) chatPane.classList.remove('hidden-mobile');
    else if(canvasPane.classList.contains('open')) chatPane.classList.add('hidden-mobile');
  });

  function esc(s){return String(s||'').replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
})();
</script>
</body></html>"""


@chat_ui_bp.route("/chat")
def chat_page(): return CHAT_HTML
