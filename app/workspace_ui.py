#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dedicated project workspace UI."""
from flask import Blueprint, Response

workspace_ui_bp = Blueprint("workspace_ui", __name__)

WORKSPACE_HTML = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Workspaces · DSH-017</title>
<style>
:root{
 --ws-bg:#101113;--ws-surface:#17191d;--ws-surface-2:#1d2025;--ws-surface-3:#242830;
 --ws-text:#f2f1ed;--ws-text-2:#c1c0bb;--ws-muted:#858891;
 --ws-line:rgba(255,255,255,.085);--ws-line-2:rgba(255,255,255,.14);
 --ws-accent:#d97757;--ws-accent-soft:rgba(217,119,87,.12);
 --ws-good:#5ccea1;--ws-warn:#e4b56d;--ws-bad:#ef8888;
 --ws-shadow:0 12px 32px rgba(0,0,0,.20);
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{height:100%;margin:0;background:var(--ws-bg);color:var(--ws-text);
 font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif}
body{overflow:hidden}
button,input,textarea,select{font:inherit}
button{cursor:pointer}
.ws-app{height:100vh;height:100dvh;height:var(--ws-vh,100dvh);min-height:0;display:flex;flex-direction:column;background:var(--ws-bg)}
.ws-topbar{height:54px;flex:none;display:flex;align-items:center;gap:10px;padding:0 13px;
 background:var(--ws-surface);border-bottom:1px solid var(--ws-line);z-index:3}
.ws-brand{display:flex;align-items:center;gap:9px;min-width:0;margin-right:auto}
.ws-mark{width:28px;height:28px;border-radius:9px;background:linear-gradient(145deg,#d97757,#a94e39);
 display:grid;place-items:center;color:#fff;font-size:13px;font-weight:750;box-shadow:0 4px 12px rgba(217,119,87,.22)}
.ws-brand-title{font-size:13px;font-weight:660;letter-spacing:-.02em}
.ws-brand-sub{font-size:9px;color:var(--ws-muted);margin-top:2px;letter-spacing:.09em;text-transform:uppercase}
.top-btn,.ws-action{height:32px;border:1px solid var(--ws-line);border-radius:9px;padding:0 10px;
 background:var(--ws-surface-2);color:var(--ws-text-2);font-size:11px;white-space:nowrap}
.top-btn:active,.ws-action:active{transform:scale(.97)}
.ws-action.primary{background:var(--ws-accent);border-color:transparent;color:white;font-weight:650}
.ws-action:disabled{opacity:.45;cursor:default;transform:none}
.ws-status{font:10px ui-monospace,SFMono-Regular,monospace;color:var(--ws-muted);white-space:nowrap}
.ws-status.dirty{color:var(--ws-warn)}.ws-status.saved{color:var(--ws-good)}
.ws-main{display:grid;grid-template-columns:210px 238px minmax(300px,1fr) 330px;flex:1;min-height:0}
.ws-panel{display:flex;flex-direction:column;min-width:0;min-height:0;background:var(--ws-surface);
 border-right:1px solid var(--ws-line)}
.ws-panel-head{height:48px;flex:none;padding:0 13px;display:flex;align-items:center;gap:8px;
 border-bottom:1px solid var(--ws-line)}
.ws-panel-title{font-size:11px;font-weight:680;letter-spacing:.055em;text-transform:uppercase;color:var(--ws-muted);flex:1}
.ws-panel-sub{font-size:10px;color:var(--ws-muted)}
.ws-panel-body{flex:1;min-height:0;overflow:auto;padding:9px}
.ws-project-list{display:flex;flex-direction:column;gap:3px}
.ws-project{display:flex;align-items:center;gap:8px;min-height:36px;padding:7px 9px;border-radius:9px;
 color:var(--ws-text-2);font-size:12px;cursor:pointer;transition:background .16s ease,color .16s ease}
.ws-project:hover,.ws-project.active{background:var(--ws-surface-3);color:var(--ws-text)}
.ws-project.active{box-shadow:inset 2px 0 var(--ws-accent)}
.ws-project-icon{width:20px;height:20px;border-radius:6px;display:grid;place-items:center;
 background:var(--ws-surface-3);color:var(--ws-accent);font-size:10px;flex:none}
.ws-project-name{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ws-count{font:9px ui-monospace,monospace;color:var(--ws-muted)}
.ws-section{padding:13px 8px 6px;font:9px ui-monospace,monospace;letter-spacing:.12em;
 text-transform:uppercase;color:var(--ws-muted)}
.ws-create-row{display:flex;gap:6px;padding:8px 2px 3px}
.ws-create-row button{flex:1}
.ws-icon-btn{width:28px;height:28px;display:grid;place-items:center;border:1px solid transparent;
 border-radius:8px;background:transparent;color:var(--ws-muted);font-size:14px}
.ws-icon-btn:hover{background:var(--ws-surface-3);color:var(--ws-text)}
.ws-filetree{font-size:12px}
.tree-item{display:flex;align-items:center;gap:6px;min-height:31px;padding:4px 5px 4px 7px;
 border-radius:8px;color:var(--ws-text-2);cursor:pointer;min-width:0}
.tree-item:hover{background:var(--ws-surface-2)}
.tree-item.active{background:var(--ws-accent-soft);color:var(--ws-text)}
.tree-arrow{width:12px;flex:none;color:var(--ws-muted);font-size:9px;text-align:center}
.tree-icon{width:17px;flex:none;color:var(--ws-muted);text-align:center;font-size:11px}
.tree-name{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tree-actions{display:none;gap:1px}
.tree-item:hover .tree-actions{display:flex}
.tree-actions button{width:22px;height:22px;border:0;border-radius:6px;background:transparent;color:var(--ws-muted)}
.tree-actions button:hover{background:var(--ws-surface-3);color:var(--ws-text)}
.tree-children{margin-left:15px;border-left:1px solid var(--ws-line);padding-left:4px}
.ws-center{display:flex;flex-direction:column;min-width:0;min-height:0;background:var(--ws-bg)}
.editor-top{height:49px;flex:none;display:flex;align-items:center;gap:8px;padding:0 12px;
 border-bottom:1px solid var(--ws-line);background:var(--ws-surface)}
.crumb{min-width:0;flex:1;font-size:12px;color:var(--ws-text-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.crumb strong{color:var(--ws-text);font-weight:620}
.file-version{font:10px ui-monospace,monospace;color:var(--ws-muted);padding:4px 6px;background:var(--ws-surface-2);border-radius:6px}
.editor-modes{display:flex;gap:3px;padding:3px;border-radius:9px;background:var(--ws-surface-2)}
.mode-btn{border:0;border-radius:6px;background:transparent;color:var(--ws-muted);padding:5px 8px;font-size:10px}
.mode-btn.active{background:var(--ws-surface-3);color:var(--ws-text)}
.editor-area{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.editor-area.source-only{grid-template-columns:minmax(0,1fr)}
.editor-area.preview-only{grid-template-columns:minmax(0,1fr)}
.editor-wrap,.preview-wrap{display:flex;flex-direction:column;min-width:0;min-height:0}
.editor-wrap{border-right:1px solid var(--ws-line)}
.editor-label{height:32px;flex:none;padding:0 13px;display:flex;align-items:center;justify-content:space-between;
 font:9px ui-monospace,monospace;letter-spacing:.08em;color:var(--ws-muted);text-transform:uppercase;
 background:var(--ws-surface);border-bottom:1px solid var(--ws-line)}
#editor{flex:1;min-height:0;width:100%;resize:none;border:0;outline:0;padding:17px 18px;
 background:var(--ws-bg);color:var(--ws-text-2);font:12px/1.78 ui-monospace,SFMono-Regular,Consolas,monospace;
 tab-size:2;white-space:pre;overflow:auto}
#editor:focus{box-shadow:inset 0 0 0 1px rgba(217,119,87,.14)}
.preview-content{flex:1;min-height:0;overflow:auto;padding:19px 22px;color:var(--ws-text-2);font-size:13px;line-height:1.8}
.preview-content h1,.preview-content h2,.preview-content h3{color:var(--ws-text);line-height:1.35;letter-spacing:-.03em}
.preview-content h1{font-size:23px}.preview-content h2{font-size:18px}.preview-content h3{font-size:15px}
.preview-content p{margin:0 0 13px}.preview-content pre{background:var(--ws-surface);border:1px solid var(--ws-line);
 border-radius:11px;padding:12px;overflow:auto;font:11px/1.6 ui-monospace,monospace}
.preview-content code{background:var(--ws-surface-3);border-radius:4px;padding:2px 4px;font:11px ui-monospace,monospace}
.preview-content pre code{padding:0;background:transparent}
.preview-content blockquote{margin:12px 0;padding:5px 12px;border-left:2px solid var(--ws-accent);color:var(--ws-muted)}
.preview-content a{color:var(--ws-accent);text-decoration:none}
.preview-content ul,.preview-content ol{padding-left:22px}
.preview-empty{height:100%;display:grid;place-items:center;color:var(--ws-muted);font-size:12px}
.callout{margin-top:14px;font-size:10px;line-height:1.7;color:var(--ws-muted)}
.ws-empty{flex:1;min-height:0;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:13px;
 color:var(--ws-muted);text-align:center;padding:25px}
.ws-empty-icon{width:52px;height:52px;border:1px solid var(--ws-line);border-radius:17px;display:grid;place-items:center;
 font-size:22px;color:var(--ws-accent);background:var(--ws-surface)}
.ws-empty h2{font-size:15px;color:var(--ws-text);margin:0}.ws-empty p{font-size:11px;line-height:1.6;max-width:260px;margin:0}
.ws-assistant{display:flex;flex-direction:column;background:var(--ws-surface);min-width:0;min-height:0}
.ai-head{height:49px;flex:none;display:flex;align-items:center;gap:8px;padding:0 12px;border-bottom:1px solid var(--ws-line)}
.ai-title{flex:1;font-size:12px;font-weight:640}
.ai-model{max-width:160px;border:1px solid var(--ws-line);border-radius:8px;background:var(--ws-surface-2);
 color:var(--ws-text-2);font-size:10px;padding:6px;min-width:0}
.ai-messages{flex:1;min-height:0;overflow:auto;padding:14px 12px;display:flex;flex-direction:column;gap:12px}
.ai-welcome{padding:15px;border:1px solid var(--ws-line);border-radius:13px;background:var(--ws-surface-2)}
.ai-welcome strong{font-size:12px}.ai-welcome p{font-size:10px;line-height:1.6;color:var(--ws-muted);margin:7px 0 0}
.ai-message{max-width:100%;display:flex;flex-direction:column;gap:5px}
.ai-message.user{align-items:flex-end}
.ai-bubble{font-size:12px;line-height:1.7;color:var(--ws-text-2);white-space:pre-wrap;overflow-wrap:anywhere}
.ai-message.user .ai-bubble{background:var(--ws-surface-3);color:var(--ws-text);border-radius:13px 13px 4px 13px;padding:9px 11px;max-width:92%}
.ai-message.assistant .ai-bubble{padding:2px 2px}
.ai-meta{font:9px ui-monospace,monospace;color:var(--ws-muted);letter-spacing:.06em}
.ai-compose{padding:10px;border-top:1px solid var(--ws-line);background:var(--ws-surface)}
.ai-controls{display:flex;align-items:center;gap:6px;margin-bottom:7px}
.ai-controls select{flex:1;min-width:0;background:var(--ws-surface-2);border:1px solid var(--ws-line);
 border-radius:8px;padding:6px;color:var(--ws-muted);font-size:10px}
.ai-input-wrap{display:flex;gap:7px;align-items:flex-end;padding:8px;border:1px solid var(--ws-line-2);
 background:var(--ws-bg);border-radius:13px}
#aiInput{flex:1;min-width:0;max-height:125px;min-height:35px;resize:vertical;border:0;outline:0;background:transparent;
 color:var(--ws-text);font-family:inherit;font-size:12px;line-height:1.6}
#aiSend{width:34px;height:34px;border:0;border-radius:10px;background:var(--ws-accent);color:white;font-weight:700}
#aiSend:disabled{opacity:.4}
.pending-edit{border:1px solid rgba(228,181,109,.35);background:rgba(228,181,109,.08);padding:10px;border-radius:11px}
.pending-edit strong{font-size:11px}.pending-edit p{font-size:10px;color:var(--ws-muted);line-height:1.5}
.pending-edit button{border:1px solid var(--ws-line);border-radius:8px;padding:7px 9px;background:var(--ws-surface-3);color:var(--ws-text);font-size:10px}
.ws-bottom-hint{padding:6px 12px;border-top:1px solid var(--ws-line);font:9px ui-monospace,monospace;color:var(--ws-muted)}
.version-pop{position:fixed;z-index:30;inset:0;background:rgba(0,0,0,.58);display:none;align-items:center;justify-content:center;padding:18px}
.version-pop.open{display:flex}
.version-card{width:min(460px,100%);max-height:75vh;overflow:auto;background:var(--ws-surface);border:1px solid var(--ws-line);
 border-radius:17px;padding:15px;box-shadow:var(--ws-shadow)}
.version-row{padding:10px 4px;border-bottom:1px solid var(--ws-line);display:flex;align-items:center;gap:10px;font-size:11px}
.version-row span{flex:1;color:var(--ws-muted)}
.version-row button{padding:6px 9px;background:var(--ws-surface-3);border:1px solid var(--ws-line);border-radius:7px;color:var(--ws-text);font-size:10px}
@media(max-width:1150px){.ws-main{grid-template-columns:190px 210px minmax(260px,1fr)}.ws-assistant{display:none}.ws-main.ai-open{grid-template-columns:180px minmax(0,1fr)}.ws-main.ai-open .tree-panel{display:none}.ws-main.ai-open .ws-assistant{display:flex}}
@media(max-width:760px){
 .ws-topbar{height:49px;padding:0 8px;gap:5px}.ws-brand-sub,.ws-status{display:none}
 .ws-topbar .top-btn{padding:0 7px;font-size:10px}
 .ws-main{grid-template-columns:170px minmax(0,1fr)}
 .project-rail{display:none}
 .ws-main.project-open{grid-template-columns:170px minmax(0,1fr)}.ws-main.project-open .project-rail{display:flex}.ws-main.project-open .tree-panel{display:none}
 .ws-main.files-open{grid-template-columns:190px minmax(0,1fr)}.ws-main.files-open .tree-panel{display:flex}
 .ws-main.ai-open{grid-template-columns:minmax(0,1fr)}.ws-main.ai-open .ws-center{display:none}.ws-main.ai-open .ws-assistant{display:flex}
 .ws-assistant{display:none}.editor-area{grid-template-columns:1fr}.preview-wrap{display:none}
 .editor-area.preview-only .editor-wrap{display:none}.editor-area.preview-only .preview-wrap{display:flex}
 .editor-area.split .editor-wrap{display:flex}.editor-area.split .preview-wrap{display:none}
}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{transition:none!important;animation:none!important}}
</style></head><body>
<div class="ws-app">
 <header class="ws-topbar topbar">
  <a class="top-btn" href="/chat">← 聊天</a>
  <div class="ws-brand"><div class="ws-mark">W</div><div><div class="ws-brand-title">Workspaces</div><div class="ws-brand-sub">Projects · Files · AI workspace</div></div></div>
  <span class="ws-status" id="saveStatus">就绪</span>
  <button class="top-btn" id="mobileProjects">项目</button>
  <button class="top-btn" id="mobileFiles">文件</button>
  <button class="top-btn" id="mobileAI">AI</button>
 </header>
 <div class="ws-main" id="mainLayout">
  <aside class="ws-panel project-rail">
   <div class="ws-panel-head"><span class="ws-panel-title">项目</span><button class="ws-icon-btn" id="newProject" title="新建项目">＋</button></div>
   <div class="ws-panel-body">
    <div class="ws-project-list" id="projectList"></div>
    <div class="callout" style="margin-top:14px;font-size:10px;line-height:1.7;color:var(--ws-muted)">
     每个项目有独立文件树、编辑内容和 AI 上下文。旧文件已迁入“我的工作区”。
    </div>
   </div>
   <div class="ws-bottom-hint">LOCAL PROJECT STORAGE</div>
  </aside>
  <aside class="ws-panel tree-panel">
   <div class="ws-panel-head"><span class="ws-panel-title">文件</span><button class="ws-icon-btn" id="newFolder" title="新建文件夹">▱</button><button class="ws-icon-btn" id="newFile" title="新建文件">＋</button></div>
   <div class="ws-panel-body"><div class="ws-filetree" id="fileTree"><div class="hint">请选择项目…</div></div></div>
   <div class="ws-bottom-hint" id="treeFoot">0 FILES</div>
  </aside>
  <main class="ws-center">
   <div class="editor-top">
    <div class="crumb" id="crumb"><strong>Workspace</strong> / 尚未打开文件</div>
    <span class="file-version" id="fileVersion">—</span>
    <div class="editor-modes">
     <button class="mode-btn active" data-mode="source">编辑</button>
     <button class="mode-btn" data-mode="split">分栏</button>
     <button class="mode-btn" data-mode="preview">预览</button>
    </div>
    <button class="ws-action" id="historyBtn" disabled>历史</button>
    <button class="ws-action primary" id="saveFile" disabled>保存</button>
   </div>
   <div class="ws-empty" id="editorEmpty">
    <div class="ws-empty-icon">▤</div><h2>从一个项目开始</h2>
    <p>创建或选择项目，在文件树中打开文件。你可以在右侧让 AI 阅读当前文件并协助修改。</p>
    <button class="ws-action primary" id="emptyCreate">新建文件</button>
   </div>
   <div class="editor-area source-only" id="editorArea" style="display:none">
    <section class="editor-wrap"><div class="editor-label"><span>EDITOR</span><span id="editorLanguage">TEXT</span></div>
     <textarea id="editor" spellcheck="false" autocomplete="off" autocapitalize="off" placeholder="开始编写…"></textarea>
    </section>
    <section class="preview-wrap"><div class="editor-label"><span>PREVIEW</span><span>MARKDOWN</span></div>
     <div class="preview-content" id="preview"></div>
    </section>
   </div>
   <div class="ws-bottom-hint" id="editorFoot">选择文件开始编辑 · Ctrl/⌘ + S 保存</div>
  </main>
  <aside class="ws-assistant">
   <div class="ai-head"><span class="ai-title">AI 助手</span><select class="ai-model" id="aiModel"><option value="zhipu::glm-4.7-flash">GLM-4.7-Flash</option></select></div>
   <div class="ai-messages" id="aiMessages">
    <div class="ai-welcome"><strong>在工作区里一起完成任务</strong><p>我可以解释当前文件、整理结构、生成代码修改建议。打开文件后会自动将其内容作为上下文。</p></div>
   </div>
   <div class="ai-compose">
    <div class="ai-controls">
     <select id="aiPermission"><option value="ask">修改需要确认</option><option value="suggest">仅生成建议</option><option value="auto">按已授权规则自动应用</option></select>
    </div>
    <div class="ai-input-wrap"><textarea id="aiInput" rows="2" placeholder="询问此项目或当前文件…"></textarea><button id="aiSend" title="发送">↑</button></div>
   </div>
   <div class="ws-bottom-hint">AI EDITS · VERSIONED · REVIEWABLE</div>
  </aside>
 </div>
</div>
<div class="version-pop" id="versionPop"><div class="version-card"><div class="ws-panel-head" style="padding:0 0 11px"><b style="flex:1;font-size:13px">文件版本历史</b><button class="ws-icon-btn" id="closeVersions">×</button></div><div id="versionList"></div></div></div>
<script>
(function(){
 "use strict";
 var $=function(id){return document.getElementById(id)};
 var projects=[],files=[],currentProject="default",currentFile=null,currentVersion=0,dirty=false;
 var expanded={},currentParent=null,editorMode="source",aiHistory=[],activeReader=null,aiBusy=false;
 var pendingEdit=null;
 var layout=$("mainLayout"),tree=$("fileTree"),editor=$("editor"),preview=$("preview");
 function syncViewportHeight(){
  var viewport=window.visualViewport;
  var height=viewport&&viewport.height?viewport.height:window.innerHeight;
  if(height>0)document.documentElement.style.setProperty("--ws-vh",Math.round(height)+"px");
 }
 syncViewportHeight();
 window.addEventListener("resize",syncViewportHeight,{passive:true});
 if(window.visualViewport){window.visualViewport.addEventListener("resize",syncViewportHeight,{passive:true});}
 var providers=[];
 function api(path,options){
  return fetch(path,options||{}).then(function(r){return r.json().then(function(j){if(!r.ok||j.code!==0)throw new Error(j.message||("HTTP "+r.status));return j;});});
 }
 function esc(value){return String(value==null?"":value).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
 function setStatus(text,kind){$("saveStatus").textContent=text;$("saveStatus").className="ws-status "+(kind||"");}
 function post(path,body,method){return api(path,{method:method||"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body||{})});}
 function projectName(){var p=projects.find(function(x){return x.id===currentProject;});return p?p.name:"工作区";}
 function loadProjects(){
  api("/api/workspace/projects").then(function(j){
   projects=j.items||[];
   if(!projects.some(function(p){return p.id===currentProject;}))currentProject=projects.length?projects[0].id:"default";
   renderProjects();loadFiles();
  }).catch(function(e){tree.textContent="项目读取失败："+e.message;});
 }
 function renderProjects(){
  var list=$("projectList");list.innerHTML="";
  projects.forEach(function(project){
   var row=document.createElement("div");row.className="ws-project"+(project.id===currentProject?" active":"");
   var icon=document.createElement("span");icon.className="ws-project-icon";icon.textContent=project.id==="default"?"⌂":"▤";
   var name=document.createElement("span");name.className="ws-project-name";name.textContent=project.name;
   var count=document.createElement("span");count.className="ws-count";count.textContent=project.file_count||0;
   row.appendChild(icon);row.appendChild(name);row.appendChild(count);
   row.onclick=function(){if(dirty&&!confirm("当前文件尚未保存，切换项目会丢弃编辑内容。继续？"))return;
    currentProject=project.id;currentFile=null;currentParent=null;dirty=false;renderProjects();loadFiles();};
   list.appendChild(row);
  });
 }
 function loadFiles(){
  api("/api/workspace/files?project_id="+encodeURIComponent(currentProject)).then(function(j){
   files=j.items||[];renderTree();$("treeFoot").textContent=files.filter(function(x){return x.kind==="file";}).length+" FILES";
   $("crumb").innerHTML="<strong>"+esc(projectName())+"</strong> / "+(currentFile?esc(currentFile.name):"尚未打开文件");
  }).catch(function(e){tree.textContent="文件树读取失败："+e.message;});
 }
 function renderTree(){
  tree.innerHTML="";
  if(!files.length){var empty=document.createElement("div");empty.className="ws-empty";empty.style.padding="20px 8px";empty.textContent="暂无文件，点击右上角 ＋ 创建。";tree.appendChild(empty);return;}
  function addChildren(parent,container,depth){
   var children=files.filter(function(f){return (f.parent_id==null?null:Number(f.parent_id))===(parent==null?null:Number(parent));});
   children.sort(function(a,b){if(a.kind!==b.kind)return a.kind==="directory"?-1:1;return a.name.localeCompare(b.name);});
   children.forEach(function(file){
    var row=document.createElement("div");row.className="tree-item"+(currentFile&&currentFile.id===file.id?" active":"");
    row.style.paddingLeft=(7+Math.min(depth,5)*4)+"px";row.dataset.id=file.id;
    var arrow=document.createElement("span");arrow.className="tree-arrow";arrow.textContent=file.kind==="directory"?(expanded[file.id]?"▾":"▸"):"";
    var icon=document.createElement("span");icon.className="tree-icon";icon.textContent=file.kind==="directory"?(expanded[file.id]?"▾":"▱"):fileIcon(file.name);
    var name=document.createElement("span");name.className="tree-name";name.textContent=file.name;
    var actions=document.createElement("span");actions.className="tree-actions";
    var rename=document.createElement("button");rename.textContent="…";rename.title="重命名";
    rename.onclick=function(e){e.stopPropagation();renameItem(file);};
    var remove=document.createElement("button");remove.textContent="×";remove.title="删除";
    remove.onclick=function(e){e.stopPropagation();deleteItem(file);};
    actions.appendChild(rename);actions.appendChild(remove);
    row.appendChild(arrow);row.appendChild(icon);row.appendChild(name);row.appendChild(actions);
    row.onclick=function(){
     if(file.kind==="directory"){expanded[file.id]=!expanded[file.id];currentParent=file.id;renderTree();}
     else openFile(file.id);
    };
    container.appendChild(row);
    if(file.kind==="directory"&&expanded[file.id]){
     var branch=document.createElement("div");branch.className="tree-children";addChildren(file.id,branch,depth+1);container.appendChild(branch);
    }
   });
  }
  addChildren(null,tree,0);
 }
 function fileIcon(name){var ext=(name.split(".").pop()||"").toLowerCase();return ({md:"M",txt:"T",py:"Py",js:"JS",ts:"TS",json:"{}",html:"H",css:"C",yml:"Y",yaml:"Y",sh:"$"}[ext]||"·");}
 function openFile(id){
  if(dirty&&!confirm("当前文件尚未保存，打开另一个文件会丢弃修改。继续？"))return;
  api("/api/workspace/files/"+id).then(function(j){
   currentFile=j;currentVersion=j.version;editor.value=j.content||"";dirty=false;
   $("editorEmpty").style.display="none";$("editorArea").style.display="grid";
   $("saveFile").disabled=false;$("historyBtn").disabled=false;$("fileVersion").textContent="v"+currentVersion;
   $("crumb").innerHTML="<strong>"+esc(projectName())+"</strong> / "+esc(j.name);
   $("editorLanguage").textContent=fileIcon(j.name).toUpperCase()+" · "+(j.content||"").length+" CHARS";
   setStatus("已保存","saved");renderTree();renderPreview();window.wsContext={file_id:j.id,name:j.name,content:j.content||"",version:j.version};
  }).catch(function(e){setStatus("打开失败："+e.message,"dirty");});
 }
 function saveFile(){
  if(!currentFile||!dirty)return;
  $("saveFile").disabled=true;setStatus("正在保存…");
  post("/api/workspace/files/"+currentFile.id,{content:editor.value,base_version:currentVersion},"PUT")
   .then(function(j){
    currentVersion=j.version;currentFile.content=editor.value;currentFile.version=j.version;dirty=false;
    $("fileVersion").textContent="v"+j.version;$("saveFile").disabled=false;
    $("editorLanguage").textContent=fileIcon(currentFile.name).toUpperCase()+" · "+editor.value.length+" CHARS";
    if(window.wsContext){window.wsContext.content=editor.value;window.wsContext.version=j.version;}
    setStatus("已保存","saved");loadFiles();loadProjects();
   }).catch(function(e){$("saveFile").disabled=false;setStatus(e.message,"dirty");});
 }
 function markDirty(){
  dirty=!!currentFile&&editor.value!==(currentFile.content||"");
  $("saveFile").disabled=!dirty;setStatus(dirty?"未保存更改":"已保存",dirty?"dirty":"saved");
  $("editorLanguage").textContent=(currentFile?fileIcon(currentFile.name).toUpperCase():"TEXT")+" · "+editor.value.length+" CHARS";
  renderPreview();
 }
 function markdown(source){
  var lines=String(source||"").replace(/\r/g,"").split("\n"),out=[],inCode=false,code=[],list=null;
  function closeList(){if(list){out.push("</"+list+">");list=null;}}
  lines.forEach(function(line){
   if(line.trim().slice(0,3)==="\x60\x60\x60"){
    closeList();if(inCode){out.push("<pre><code>"+esc(code.join("\n"))+"</code></pre>");code=[];inCode=false;}
    else inCode=true;return;
   }
   if(inCode){code.push(line);return;}
   var m;
   if(!line.trim()){closeList();return;}
   if((m=line.match(/^###\s+(.+)/))){closeList();out.push("<h3>"+inline(m[1])+"</h3>");return;}
   if((m=line.match(/^##\s+(.+)/))){closeList();out.push("<h2>"+inline(m[1])+"</h2>");return;}
   if((m=line.match(/^#\s+(.+)/))){closeList();out.push("<h1>"+inline(m[1])+"</h1>");return;}
   if((m=line.match(/^>\s?(.*)/))){closeList();out.push("<blockquote>"+inline(m[1])+"</blockquote>");return;}
   if((m=line.match(/^[-*]\s+(.+)/))){if(list!=="ul"){closeList();out.push("<ul>");list="ul";}out.push("<li>"+inline(m[1])+"</li>");return;}
   if((m=line.match(/^\d+\.\s+(.+)/))){if(list!=="ol"){closeList();out.push("<ol>");list="ol";}out.push("<li>"+inline(m[1])+"</li>");return;}
   closeList();out.push("<p>"+inline(line)+"</p>");
  });
  if(inCode)out.push("<pre><code>"+esc(code.join("\n"))+"</code></pre>");closeList();
  return out.join("");
 }
 function inline(text){
  var value=esc(text);
  value=value.replace(/\x60([^\x60]+)\x60/g,"<code>$1</code>");
  value=value.replace(/\*\*([^*]+)\*\*/g,"<strong>$1</strong>");
  value=value.replace(/\*([^*]+)\*/g,"<em>$1</em>");
  value=value.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,'<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  return value;
 }
 function renderPreview(){
  if(!currentFile){preview.innerHTML='<div class="preview-empty">打开 Markdown 文件以查看预览</div>';return;}
  if(/\.md$/i.test(currentFile.name))preview.innerHTML=markdown(editor.value);
  else preview.innerHTML='<pre><code>'+esc(editor.value)+'</code></pre>';
 }
 function setMode(mode){
  editorMode=mode;$("editorArea").className="editor-area "+(mode==="source"?"source-only":mode==="preview"?"preview-only":"split");
  Array.prototype.forEach.call(document.querySelectorAll("[data-mode]"),function(b){b.classList.toggle("active",b.getAttribute("data-mode")===mode);});
 }
 document.querySelectorAll("[data-mode]").forEach(function(button){button.onclick=function(){setMode(button.getAttribute("data-mode"));};});
 editor.addEventListener("input",markDirty);
 editor.addEventListener("keydown",function(e){
  if(e.key==="Tab"){e.preventDefault();var a=this.selectionStart,b=this.selectionEnd;this.value=this.value.slice(0,a)+"  "+this.value.slice(b);this.selectionStart=this.selectionEnd=a+2;markDirty();}
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="s"){e.preventDefault();saveFile();}
 });
 $("saveFile").onclick=saveFile;
 $("newProject").onclick=function(){
  var name=prompt("项目名称");if(!name||!name.trim())return;
  post("/api/workspace/projects",{name:name.trim()}).then(function(j){currentProject=j.item.id;currentFile=null;loadProjects();$("editorEmpty").style.display="flex";$("editorArea").style.display="none";}).catch(function(e){alert(e.message);});
 };
 function createNode(kind){
  var name=prompt(kind==="directory"?"文件夹名称":"文件名称（例如 README.md）");if(!name||!name.trim())return;
  post("/api/workspace/files",{name:name.trim(),project_id:currentProject,parent_id:currentParent,kind:kind})
   .then(function(j){if(kind==="directory"){expanded[j.id]=true;loadFiles();}else{loadFiles();openFile(j.id);}})
   .catch(function(e){alert(e.message);});
 }
 $("newFile").onclick=function(){createNode("file");};
 $("newFolder").onclick=function(){createNode("directory");};
 $("emptyCreate").onclick=function(){createNode("file");};
 function renameItem(file){
  var name=prompt("重命名",file.name);if(!name||!name.trim()||name.trim()===file.name)return;
  post("/api/workspace/files/"+file.id,{name:name.trim()},"PATCH").then(function(){if(currentFile&&currentFile.id===file.id){currentFile.name=name.trim();$("crumb").innerHTML="<strong>"+esc(projectName())+"</strong> / "+esc(currentFile.name);}loadFiles();}).catch(function(e){alert(e.message);});
 }
 function deleteItem(file){
  if(!confirm("删除 "+file.name+"？"+(file.kind==="directory"?"其内部内容也会一起移入回收状态。":"")))return;
  api("/api/workspace/files/"+file.id,{method:"DELETE"}).then(function(){
   if(currentFile&&currentFile.id===file.id){currentFile=null;window.wsContext=null;$("editorEmpty").style.display="flex";$("editorArea").style.display="none";}
   loadFiles();loadProjects();
  }).catch(function(e){alert(e.message);});
 }
 $("historyBtn").onclick=function(){
  if(!currentFile)return;$("versionPop").classList.add("open");$("versionList").textContent="读取版本历史…";
  api("/api/workspace/files/"+currentFile.id+"/versions").then(function(j){
   $("versionList").innerHTML="";
   (j.items||[]).forEach(function(v){
    var row=document.createElement("div");row.className="version-row";
    var label=document.createElement("span");label.textContent="v"+(v.base_version||0)+" · "+v.source+" · "+new Date(v.created_at*1000).toLocaleString();
    var restore=document.createElement("button");restore.textContent="恢复到此版本";
    restore.onclick=function(){
     if(!confirm("恢复该版本会生成一个新的当前版本，继续？"))return;
     post("/api/workspace/files/"+currentFile.id+"/restore",{version_id:v.id,base_version:currentVersion})
      .then(function(j2){editor.value=j2.content;currentVersion=j2.version;currentFile.content=j2.content;currentFile.version=j2.version;
       $("fileVersion").textContent="v"+j2.version;dirty=false;markDirty();setStatus("历史版本已恢复","saved");$("versionPop").classList.remove("open");})
      .catch(function(e){alert(e.message);});
    };
    row.appendChild(label);row.appendChild(restore);$("versionList").appendChild(row);
   });
   if(!j.items.length)$("versionList").textContent="暂无版本记录";
  }).catch(function(e){$("versionList").textContent=e.message;});
 };
 $("closeVersions").onclick=function(){$("versionPop").classList.remove("open");};
 $("versionPop").onclick=function(e){if(e.target===$("versionPop"))$("versionPop").classList.remove("open");};
 function loadModels(){
  api("/api/providers").then(function(j){
   providers=j.items||[];var options=[];
   providers.forEach(function(p){if(p.enabled===false)return;(p.models||[]).forEach(function(model){
    options.push({value:p.id+"::"+model,label:p.name+" · "+model+(p.secret_configured?"":" (未设置密钥)")});
   });});
   if(options.length){$("aiModel").innerHTML="";options.forEach(function(item){var o=document.createElement("option");o.value=item.value;o.textContent=item.label;$("aiModel").appendChild(o);});
    var selected=options.find(function(o){return o.value==="zhipu::glm-4.7-flash";})||options[0];$("aiModel").value=selected.value;}
  }).catch(function(){});
 }
 function addAiMessage(role,text){
  var row=document.createElement("div");row.className="ai-message "+role;
  var meta=document.createElement("div");meta.className="ai-meta";meta.textContent=role==="user"?"YOU":"DSH ASSISTANT";
  var bubble=document.createElement("div");bubble.className="ai-bubble";bubble.textContent=text||"";
  row.appendChild(meta);row.appendChild(bubble);$("aiMessages").appendChild(row);$("aiMessages").scrollTop=$("aiMessages").scrollHeight;
  return bubble;
 }
 function showPending(edit){
  pendingEdit=edit;
  var card=document.createElement("div");card.className="pending-edit";
  var title=document.createElement("strong");title.textContent="AI 修改建议";
  var text=document.createElement("p");text.textContent="模型为当前文件生成了一段变更。请检查后再应用；实际写入仍受文件权限规则和版本保护。";
  var button=document.createElement("button");button.textContent="查看并应用建议";
  button.onclick=function(){
   var newText=edit.new_str||"",oldText=edit.old_str||"";
   var detail="旧内容：\n"+(oldText||"（新增）")+"\n\n新内容：\n"+newText;
   var permission=$("aiPermission").value;
   if(permission==="suggest"){alert("当前为“仅生成建议”模式。切换到“修改需要确认”并再次确认，才会写入文件。");return;}
   if(!confirm(detail+"\n\n确认向服务端提交这次修改？"))return;
   var endpoint=permission==="auto"?"/api/workspace/apply_edit":"/api/workspace/confirm_edit";
   var payload=Object.assign({},edit,{mode:permission});
   post(endpoint,payload)
    .then(function(j){
     if(j.code===0&&(j.auto_applied||j.confirmed_by_user)){openFile(edit.file_id);card.remove();}
    }).catch(function(e){alert(e.message);});
  };
  card.appendChild(title);card.appendChild(text);card.appendChild(button);$("aiMessages").appendChild(card);
 }
 function parseEvent(eventText,bubble){
  var lines=eventText.split("\n");
  lines.forEach(function(line){
   if(line.slice(0,6)!=="data: ")return;
   var data=line.slice(6);if(data==="[DONE]")return;
   var j;try{j=JSON.parse(data);}catch(e){return;}
   if(j.error){bubble.textContent+="\n\n"+j.error;return;}
   if(j.info){bubble.textContent+="\n"+j.info;return;}
   if(j.type==="pane_update"||j.type==="artifact_card"){showPending(j.data||{});return;}
   var choices=j.choices||[];
   if(choices.length){var delta=choices[0].delta||{};if(delta.content){bubble.textContent+=delta.content;}$("aiMessages").scrollTop=$("aiMessages").scrollHeight;}
  });
 }
 function sendAi(){
  var promptText=$("aiInput").value.trim();if(!promptText||aiBusy)return;
  if(!currentFile&&!confirm("尚未打开文件。仍要向 AI 询问整个项目的通用问题？"))return;
  aiBusy=true;$("aiSend").disabled=true;$("aiInput").disabled=true;
  $("aiInput").value="";aiHistory.push({role:"user",content:promptText});
  addAiMessage("user",promptText);var bubble=addAiMessage("assistant","");
  var choice=$("aiModel").value.split("::"),providerId=choice[0]||"zhipu",model=choice.slice(1).join("::")||"glm-4.7-flash";
  var ws=currentFile?{file_id:currentFile.id,name:currentFile.name,content:editor.value,version:currentVersion}:null;
  var body={messages:aiHistory,provider_id:providerId,model:model,effort:"auto",
   workspace:ws,open_file_id:currentFile?currentFile.id:null};
  fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})
   .then(function(response){if(!response.ok)throw new Error("HTTP "+response.status);var reader=response.body.getReader(),decoder=new TextDecoder(),buffer="";
    function pump(){return reader.read().then(function(part){
     if(part.done){
      var finalText=bubble.textContent;
      bubble.innerHTML=markdown(finalText);
      aiBusy=false;$("aiSend").disabled=false;$("aiInput").disabled=false;
      aiHistory.push({role:"assistant",content:finalText});return;
     }
     buffer+=decoder.decode(part.value,{stream:true});var split;
     while((split=buffer.indexOf("\n\n"))>=0){var event=buffer.slice(0,split);buffer=buffer.slice(split+2);parseEvent(event,bubble);}
     return pump();
    });}
    return pump();
   }).catch(function(error){bubble.textContent=error.message;aiBusy=false;$("aiSend").disabled=false;$("aiInput").disabled=false;});
 }
 $("aiSend").onclick=sendAi;
 $("aiInput").addEventListener("keydown",function(e){if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendAi();}});
 $("mobileProjects").onclick=function(){layout.classList.toggle("project-open");layout.classList.remove("files-open","ai-open");};
 $("mobileFiles").onclick=function(){layout.classList.toggle("files-open");layout.classList.remove("project-open","ai-open");};
 $("mobileAI").onclick=function(){layout.classList.toggle("ai-open");layout.classList.remove("project-open","files-open");};
 window.addEventListener("beforeunload",function(e){if(dirty){e.preventDefault();e.returnValue="";}});
 loadModels();loadProjects();setMode("split");
})();
</script></body></html>'''


@workspace_ui_bp.route("/workspace")
def workspace_page():
    return Response(WORKSPACE_HTML, mimetype="text/html")
