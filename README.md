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

> 安全提示：主服务监听局域网网卡（`0.0.0.0`），请只在可信家庭/个人网络使用，不要直接暴露到公网或不可信公共 Wi-Fi。代理接口仅允许 HTTPS 的 B 站/CDN 域名，并拒绝解析到非公网 IP 的地址。

## 快速开始

```bash
python3 -m pip install -r requirements.txt
cp run_bili.sh.example run_bili.sh
# 编辑 run_bi���q�^