# DSH-017 · 点读笔个人门户

在破解点读笔（Android 8.1 / armv7 / 双核）上，通过 Termux + proot-distro Ubuntu
容器运行的个人门户服务。

## 包含

- **B 站播放器**：WBI 签名搜索 / 播放 / 下载 / 多P / 收藏 / 进度
- **短视频流**：Scroll-Snap 全屏吸附 + 双击点赞
- **AI 聊天**：GLM-4.7-Flash 流式 + 预设 + 思考面板
- **AI 视频总结**：视觉 + 文本双引擎
- **工作区**：文件 CRUD + AI 改文件 + 5 层权限闸门
- **塔罗 3D 翻牌**：22 张大阿卡纳 + 正逆位
- **统一控制台**：5 卡片 + 30s 健康检查

## 环境

- 设备：破解点读笔，Android 8.1，armv7，双核
- 容器：proot-distro Ubuntu `dsh017`
- HTTP：curl_cffi 0.13.0（impersonate=chrome120）
- Python：/usr/bin/python3（3.10）
- Web：Waitress（线程 = CPU × 2）

## 端口

| 端口 | 服务 |
|---|---|
| 8092 | 主服务（B站 + Chat + Workspace + Shorts + Play + Fav） |
| 8084 | 塔罗 3D 翻牌 |
| 8091 | 番茄小说（搜索端点失效，UI/阅读可用） |
| 8080 | 统一控制台 |

访问：`http://<局域网IP>:8092/`

> 安全提示：四个 Web 服务（`8080`、`8084`、`8091`、`8092`）均监听局域网网卡（`0.0.0.0`），远程访问全部要求 Token。仍建议只在可信家庭/个人网络使用，不要直接暴露到公网或不可信公共 Wi-Fi。代理接口仅允许 HTTPS 的 B 站/CDN 域名，并拒绝解析到非公网 IP 的地址。

## 快速开始

```bash
python3 -m pip install -r requirements.txt
cp run_bili.sh.example run_bili.sh
# 编辑 run_bili.sh，设置 ZHIPU_API_KEY；也可在启动前通过环境变量传入
chmod +x run_bili.sh
nohup ./run_bili.sh > /dev/null 2>&1 &

nohup python3 -u tarot_server.py > tarot.log 2>&1 &
nohup python3 -u novel_server.py > novel.log 2>&1 &
nohup python3 -u hub_server.py   > hub.log   2>&1 &
```


### 远程访问认证

主机本机访问免认证：`127.0.0.1` / `::1`，以及各服务启动时自动识别到的本机网卡地址均视为本机。其他设备访问四个端口（`8080`、`8084`、`8091`、`8092`）都必须携带 Token。认证分别安装在每个 Flask 服务的全局入口，覆盖页面、API 和 `/health`；不会依赖客户端提交的 `X-Forwarded-For`。四个服务共用同一组 Token 文件。

跨设备写入同时检查 `Origin` / `Sec-Fetch-Site`，拒绝跨站写入请求，降低浏览器 Basic 凭据被第三方网页滥用的风险。

默认首次启动自动生成两枚独立随机 Token，保存在权限为 `600` 的文件中（若设置了对应环境变量，则使用环境变量而不创建该 Token 文件）：

- `data/auth_token`：普通 Token，可远程读取和执行常规写入。
- `data/admin_token`：管理员 Token，额外允许修改工作区权限规则、创建备份、修改/删除聊天预设，以及执行 `mode=auto` 的 AI 自动编辑。

远程浏览器打开任意服务地址（例如 `http://<主机局域网IP>:8092/`）时会出现 HTTP Basic 认证提示，用户名填写 `dsh017`，密码填写对应 Token。普通设备使用 `auth_token`；需要管理权限时才使用 `admin_token`。两个 Token 在四个服务端口通用；由于端口不同，浏览器可能会分别弹出认证提示。程序/API 客户端也可发送 `Authorization: Bearer <TOKEN>`。在服务主机上可用 `cat data/auth_token` 和 `cat data/admin_token` 查看默认 Token。主机本机无需输入任何 Token。删除对应 Token 文件并重启全部服务即可重新生成。

若主机有多张网卡，自动识别未覆盖到用于本机访问的地址，可在启动前设置 `DSH017_AUTH_EXEMPT_IPS`，填写主机自身的精确 IP，多个地址用逗号分隔；不要填写整个局域网网段。也可以通过 `DSH017_AUTH_TOKEN` 和 `DSH017_ADMIN_TOKEN` 环境变量自定义 Token（至少 32 个字符）。更换 Token 后重启服务。不要把 Token 写入仓库或分享给其他人；HTTP Basic/Bearer 在普通 HTTP 网络中不加密，跨不可信网络访问应使用 HTTPS 或 VPN。

### 数据目录与测试

默认运行数据保存在项目目录的 `data/`（数据库、备份和日志），预设保存在 `presets/`。可通过 `DSH017_DATA_DIR`、`DSH017_DB_PATH`、`DSH017_BACKUP_DIR`、`DSH017_PRESET_DIR` 自定义位置。无需以 root 身份运行。首次启动时，如果新数据目录为空且旧的 `/root/bili_data.db` 或 `/root/presets` 仍存在，会自动复制旧数据库和缺失的自定义预设；已有新数据不会被覆盖。

本地验证：

```bash
python3 -m compileall -q app *.py tests
python3 -m unittest discover -s tests -v
bash -n run_bili.sh.example
```

GitHub Actions 会在 push、PR 和手动触发时运行 Python 3.10–3.12 测试。

目录结构

```
.
├── bili_console.py        主入口（<100 行，只做 import + register + main）
├── run_bili.sh.example    守护脚本模板（内联 env + 日志轮转 + 崩溃拉起）
├── app/
│   ├── auth.py            本机免认证 + 远程 Token / 权限分级
│   ├── db.py              SQLite 层 + 备份 + 规则表
│   ├── bili_client.py     BiliClient + WBI 签名 + curl_cffi 共享实例
│   ├── metrics.py         指标计数器 + playurl 缓存
│   ├── llm_config.py      ZHIPU API Key / BASE / MODEL
│   ├── bili_routes.py     B 站 8 路由
│   ├── chat_routes.py     预设 CRUD + summarize
│   ├── chat_ui.py         /api/chat 流式 + CHAT_HTML
│   ├── workspace_routes.py  workspace + history/fav/progress/backup
│   ├── shorts_routes.py   /api/shorts + SHORTS_HTML
│   ├── play_routes.py     播放页 + PLAY_HTML
│   └── misc_routes.py     /fav + / + /health + /metrics + gzip
├── tarot_server.py        塔罗（8084）
├── hub_server.py          控制台（8080）
├── novel_server.py        番茄小说（8091）
└── presets/               聊天预设（公开 3 个）
```


## 已知限制

- B 站游客上限 480P/720P（除非加 SESSDATA）
- 智谱 GLM 1305 过载是物理限制，自动重试 3 次
- armv7 双核：blur / backdrop-filter / 大阴影能砍就砍
- 校园网挡 api.fxtwitter.com，`/api/x` 不可用

## 设计原则

- Token 约束界面，暖调微对比，陶土色只做签名
- 弹簧曲线只用于入场/展开/按压，不做全局 !important
- 面板对比度 1.05–1.11:1，边框 alpha 10%–16%
- 廉价感 = 信号过剩；浮得太用力的东西，看起来就是廉价的

## 致谢

这套系统从「WBI 签名卡死」啃到「AI 直接改文件 + 5 层权限闸门」，
每一步都带自动回滚，每一步都验证过。骨架很稳，剩下的是收尾和打磨。