# DSH-017 Master Plan v1.0

> **文档状态：** 战略基线 / 执行规划  
> **规划基准日：** 2026-11-07  
> **规划周期：** 2026 Q4—2027 Q4  
> **当前仓库基线：** `main`，2026-11-07 审查时最新提交 `07fa91c63a1ddbdae4cf42be4ba5fb7520f909e7`  
> **产品定位：** Personal AI Operating Environment（个人 AI 工作与生活中枢）

本文件是 DSH-017 的长期产品战略、架构方向和版本规划依据。它不意味着文中所有目标能力都已实现。凡涉及现状的描述均以当前仓库代码、README、Android README、测试文件和提交记录为依据；未完成验收的能力会明确标为“待验证”。

---

## 0. 一页战略摘要

### 我们要打造什么

DSH-017 是一个以个人为中心、以 AI 为智能核心、以 Workspace 为工作载体、以 Agent 为受控执行能力、以 Android 为重要入口的个人智能工作环境。

它不是另一个大模型，也不试图在模型能力上取代 ChatGPT、Claude 或 Gemini。它的价值在于把用户自己的项目、文件、聊天上下文、工具、媒体和服务连接成一个可控、可迁移、可持续使用的工作系统。

### 为什么值得做

单独使用 AI 聊天产品可以获得强模型能力，但个人工作往往散落在模型对话、代码仓库、本地文件、手机应用和自托管服务中。DSH-017 要解决的不是“再提供一个聊天框”，而是减少这些环境之间的断裂：

1. **上下文连续：** 项目文件、对话、任务和执行记录能够关联。
2. **模型可替换：** 用户可以选择供应商，不把产品逻辑绑定到某一个模型。
3. **从回答走向完成：** AI 能在明确授权下读取、修改、验证和归档工作成果。
4. **数据由用户掌控：** 本地优先、可导出、可备份、可恢复。
5. **移动端可用：** 用户能够通过 Android 入口持续访问自己的工作环境。

### 战略选择

- **主路线：** 路线 B——个人 AI 工作平台。
- **现有基础：** 路线 A——个人门户、媒体和工具服务。
- **远期愿景：** 路线 C——可扩展的个人 AI 操作环境；暂不建设通用操作系统或大型插件生态。
- **近期原则：** 先稳定现有核心，再产品化 Workspace，然后建设受控 Agent，最后扩展个人数据与跨模块自动化。

### 未来一年最重要的三个结果

1. Workspace 成为可靠的个人项目工作区，而不仅是文件 CRUD 页面。
2. Agent 能够完成少量高价值、可审计、可撤销的真实任务。
3. 聊天、项目、知识和媒体能够通过统一上下文与工作流协作，同时保持数据权限边界。

### 明确不做什么

近期不训练基础模型、不做企业级多租户、不做无边界自主 Agent、不急于建立插件市场、不为微服务而拆分、不以媒体功能数量作为主要增长指标，也不为了支持大量供应商而牺牲兼容性与稳定性。

---


## 0.1 当前执行状态（2026-11-07）

本节记录战略文件建立后、P0 Issue 登记时可从 GitHub 直接核实的状态。它是带时间戳的审查快照，不会自动代表后续日期的状态。

### 当前主分支与自动化证据

- **main HEAD：** [`07fa91c`](https://github.com/2719126468-ship-it/dsh017/commit/07fa91c63a1ddbdae4cf42be4ba5fb7520f909e7)（`docs: link master strategy from README`）。
- **CI：** [main push run #42363124784](https://github.com/2719126468-ship-it/dsh017/actions/runs/42363124784) 成功；Python 3.10、3.11、3.12 三个矩阵 Job 全部成功，包含依赖安装、Python 编译、单元 / 路由测试、内联 JavaScript 检查和 Shell 语法检查。
- **Android：** [main push run #42363124808](https://github.com/2719126468-ship-it/dsh017/actions/runs/42363124808) 成功；`Build ARMv7-32bit` 与 `Build ARM64-64bit` 两个 Job 均成功，均完成 APK stage 和 workflow artifact 上传。该次 main push 的 `Publish GitHub Release` Job 按工作流条件跳过，这是预期行为；正式 Release 只在推送 `v*` tag 时创建。
- **当前 main workflow artifacts：** [Android run artifacts](https://github.com/2719126468-ship-it/dsh017/actions/runs/42363124808)。ARMv7 artifact SHA256：`fea0ef7fd4ec22c7774b010f14786dcbed4ea5c63fca8bcce82990d3b599622c`；ARM64 artifact SHA256：`b4b9429bf18d61da42f52ea206a1e484494c9a25703a141edcbc1323ab52d427`。Actions artifact 有保留期限，不能代替长期 Release 资产。
- **历史 PR 检查：** PR #23 的最终 PR 检查成功并已合并；早期中间提交曾因测试 Mock 仍使用旧 `client.s.post` 接口、以及模拟 SSE 响应缺少 `status` 属性而失败。后续提交同步更新测试并补齐模拟对象，最终 PR 检查和 main push 检查通过。不要把这些早期 PR 失败误报为当前 main 失败。
- **Issues / PR：** 本轮登记前没有开放 Issue 或 PR；近期 PR #20–#23 均已合并。现已创建以下八个 P0 跟踪项，见第 7 节。

### Release 基线差异

当前公开 [v0.1.2 Release](https://github.com/2719126468-ship-it/dsh017/releases/tag/v0.1.2) 指向提交 `5aa8ea52225de8b341436ba9aa51cd51549d0ce7`，并包含 ARMv7 APK、ARM64 APK 与 `SHA256SUMS.txt`。但 main 后续又合入 Magpie 自动发现、Provider DNS 固定传输 / SSE 修复及 Master Plan 文档；这些后续提交不在现有 v0.1.2 Release 的目标提交中。

当前 Gradle 配置仍为 `versionName 0.1.2`、`versionCode 3`。因此不能移动或覆盖现有 v0.1.2 tag。建议在 P0 实机与集成验收通过后发布下一个 patch 版本（建议 v0.1.3），递增 versionCode，并为该 Release 重新构建双 ABI APK。

另一个发布阻断项是 APK 签名连续性：当前 CI 构建 Debug variant，尚未证明不同 workflow run 使用同一证书。必须先完成 [P0 Issue #31](https://github.com/2719126468-ship-it/dsh017/issues/31)，验证覆盖升级和应用私有数据保留；不能把“APK 构建成功”误认为“升级安装成功”。

### 尚未由仓库自动化证明的事项

以下项目即使有对应代码或单元测试，也仍需真实环境证据：
- Mate 20 Pro / Android 10 的安装、启动、WebView、网络和 Workspace 实机验收。
- 使用真实 API 凭据的 Provider 完整调用、模型发现与流式输出。
- Magpie Gateway 与 Qoder 插件实际授权后的真实请求。
- 独立数据目录中的 SQLite 备份与恢复演练。
- 四服务认证、Keystore、日志脱敏和网络出口策略的集中安全回归。

以上均已登记为开放 P0 Issues，不把构建成功当作实机验收完成。

---

## 0.2 执行状态增补（2026-11-07，P0 修复合并后）

本节是对 0.1 初始快照的后续增补。此处的首批功能代码基线为 `285025b7481d6e9ab7607de690ed858ea8576022`；`07fa91c` 仅是最初快照中的历史 HEAD，不再代表当前功能基线。2026-11-07 后续合并与最新主分支状态见 0.3 节。

### 已合入主分支的稳定性与安全修复

| PR | 合并提交 | 内容 | 合并前验证 |
|---|---|---|---|
| [#32](https://github.com/2719126468-ship-it/dsh017/pull/32) | `74b74a9` | Workspace AI 编辑拒绝目录目标；写入前再次核验；限制 old/new patch 均不超过 1,000,000 字符 | [CI #42364195249](https://github.com/2719126468-ship-it/dsh017/actions/runs/42364195249) 成功；[Android #42364195317](https://github.com/2719126468-ship-it/dsh017/actions/runs/42364195317) 双 ABI 成功 |
| [#33](https://github.com/2719126468-ship-it/dsh017/pull/33) | `f2bd2b0` | Provider `enabled` 字段严格要求布尔类型，避免字符串 `false` 被误判为启用 | [CI #42363632348](https://github.com/2719126468-ship-it/dsh017/actions/runs/42363632348) 成功；[Android #42363632343](https://github.com/2719126468-ship-it/dsh017/actions/runs/42363632343) 双 ABI 成功 |
| [#34](https://github.com/2719126468-ship-it/dsh017/pull/34) | `c2b53cf` | Android Provider Key bridge 限制到精确的 loopback `/providers` 设置路由；更新发布与校验和文档 | [CI #42363386602](https://github.com/2719126468-ship-it/dsh017/actions/runs/42363386602) 成功；[Android #42363386530](https://github.com/2719126468-ship-it/dsh017/actions/runs/42363386530) 双 ABI 成功 |
| [#36](https://github.com/2719126468-ship-it/dsh017/pull/36) | `54eea25` | 新增隔离 SQLite / 预设备份恢复工具、版本化 SHA-256 manifest、路径与成员校验、拒绝覆盖非空目标；恢复数据库映射到应用默认 `bili_data.db` | [CI #42364482493](https://github.com/2719126468-ship-it/dsh017/actions/runs/42364482493) 成功；[Android #42364482418](https://github.com/2719126468-ship-it/dsh017/actions/runs/42364482418) 双 ABI 成功 |
| [#37](https://github.com/2719126468-ship-it/dsh017/pull/37) | `285025b` | 持久化 Release 签名；Debug CI 与 Release 发布分离；缺少 Keystore Secrets 时 fail closed；发布前核验 ARMv7 / ARM64 signer 证书相同 | [CI #42364426365](https://github.com/2719126468-ship-it/dsh017/actions/runs/42364426365) 成功；[Android #42364426364](https://github.com/2719126468-ship-it/dsh017/actions/runs/42364426364) 双 ABI Debug 构建成功；Release job 按 PR 事件跳过 |

PR #35 是旧签名分支，已关闭且未合并；由针对主线重建的 PR #37 替代。PR #32、#33、#34、#36、#37 已合入。上述 Android 结果均为 PR 分支的 Debug CI 构建，不等同于正式 Release 签名构建或设备安装验收。

### Debug APK 签名实测

对两个独立 Actions run 的 ARMv7 / ARM64 Debug APK，提取 APK v2 Signing Block 的 signer X.509 证书并用 OpenSSL 计算 SHA-256。四个指纹全部不同，确认旧临时 Debug signer 既不保证跨 run 稳定，也不保证同 run 的双 ABI 一致：

| Actions run | ABI | Artifact ID | Signer certificate SHA-256 |
|---|---|---:|---|
| [42363124808](https://github.com/2719126468-ship-it/dsh017/actions/runs/42363124808) | ARMv7 | `13570418029` | `c10371e2165ca8c55adcef75cc99b79f933e23bd39277fa57ae879fe11f17366` |
| [42363124808](https://github.com/2719126468-ship-it/dsh017/actions/runs/42363124808) | ARM64 | `13570144863` | `2d4ac3e496c81702b7ae65bb9acd50897244ff179af311004629fb26bc7daba2` |
| [42363251939](https://github.com/2719126468-ship-it/dsh017/actions/runs/42363251939) | ARMv7 | `13570825849` | `db7971dd88d8d03de836befe081af9d8f9f810d8e4f840808d912d3118f6d7ae` |
| [42363251939](https://github.com/2719126468-ship-it/dsh017/actions/runs/42363251939) | ARM64 | `13569903751` | `2ea0d3175a286763ec11a0db5c4b3d71665e8918f5ea0cfe68f9e535a74e61e3` |

该测试是 APK v2 signer 证书提取与 SHA-256 比对，不应被表述为完整的 Android 安装 / 更新验证。#37 已加入正式 Release 统一签名流程，但实际 GitHub Actions secrets、tag Release 构建、Release-to-Release 覆盖安装仍待完成。

### 备份恢复能力现状

PR #36 新增 `scripts/data_backup.py` 与 `docs/BACKUP_RESTORE.md`。备份使用 SQLite online backup API；manifest 包含版本、文件大小和 SHA-256；恢复检查路径 / tar member 类型、重复路径、大小、hash、SQLite integrity、Provider metadata 与 preset UTF-8，并且拒绝写入非空目标。Provider API Key、auth/admin Token、运行时 secrets 和 Android Keystore 项目不导出。

自动化测试使用合成数据，覆盖聊天、Workspace 文件 / 版本 / 规则、收藏、观看进度、搜索历史、预设、Provider metadata、损坏归档拒绝和非空目标保护。该证据不能代替部署环境的人工恢复演练，也不能证明 Android app-private storage 能被该 CLI 自动导出。

### 当前发布与 P0 边界

- 公开最新 Release 仍是 `v0.1.2`；没有创建或覆盖 `v0.1.3` tag。Gradle 版本仍需按发布计划从 `versionName 0.1.2` / `versionCode 3` 递增。
- #24–#31 八个 P0 issue 仍按各自验收标准跟踪；PR 合并不自动关闭依赖实机 / 真实凭据的 issue。
- #28：隔离备份 / 恢复工具已合入，并支持默认及自定义 SQLite 文件名；真实运行目录的人工恢复演练、服务停启与关键记录核验仍未完成。
- #31：持久化 Release 签名代码已合入；四项 repository Actions secrets 是否配置、正式双 ABI Release 是否用同证书、升级安装与旧 Debug 包数据迁移仍待实测。
- #25：Mate 20 Pro / Android 10 实机安装、WebView、Chat、Workspace、主题、统计和数据升级测试仍待完成。
- #26 / #27：真实 OpenAI-compatible Provider 与 Magpie / Qoder 账号授权后的集成测试仍待完成。
- #29：Provider 错误响应脱敏与 IPv6 DNS 安全回归已合入；认证、WebView bridge、代理与设备边界的整体验收仍未完成。
- #30：Workspace AI 编辑规则、大小限制、并发冲突、文件路径边界及移动键盘视口自动化回归已合入；Mate 20 Pro WebView 触摸 / 键盘实测仍待完成。

不得因为自动化通过而提前关闭 #24–#31，也不得在签名和数据迁移验收前创建下一版公开 Release。

---

## 0.3 执行状态增补（2026-11-07，后续 P0 合并）

最新主分支提交：`9503d042ab0c2d7d81e86257645b617125569299`。

### 新增合入的 P0 修复

| PR | 合并提交 | 变更 | PR 验证 |
|---|---|---|---|
| [#43](https://github.com/2719126468-ship-it/dsh017/pull/43) | `e937935` | Provider `/models`、`/test` 与 Magpie discovery 错误响应脱敏；IPv6 ULA、link-local、IPv4-mapped loopback 与混合 DNS 答案回归覆盖；全局 IPv6 仍做地址 pinning | [CI #42365238783](https://github.com/2719126468-ship-it/dsh017/actions/runs/42365238783) 三版本通过；[Android #42365238854](https://github.com/2719126468-ship-it/dsh017/actions/runs/42365238854) 双 ABI 通过 |
| [#42](https://github.com/2719126468-ship-it/dsh017/pull/42) | `c29c025` | `confirm_edit` 同时限制 old/new 1 MB；Workspace 默认 ask、deny precedence、手动确认不能绕过 deny、自动断路器、版本冲突、文件名 / parent 边界回归；移动端 visualViewport 键盘高度适配 | [CI #42365437464](https://github.com/2719126468-ship-it/dsh017/actions/runs/42365437464) Python 3.10 / 3.11 / 3.12 通过；[Android #42365437468](https://github.com/2719126468-ship-it/dsh017/actions/runs/42365437468) 双 ABI 通过 |
| [#40](https://github.com/2719126468-ship-it/dsh017/pull/40) | `9503d04` | 备份恢复支持 `--db-name`，适配自定义 `DSH017_DB_PATH` basename；拒绝路径穿越、目录分隔符、token / provider 保留名及 `backup` 冲突名；修复恢复文档环境变量初始化顺序 | [CI #42365554965](https://github.com/2719126468-ship-it/dsh017/actions/runs/42365554965) 三版本通过；[Android #42365554967](https://github.com/2719126468-ship-it/dsh017/actions/runs/42365554967) 双 ABI 通过 |

PR #41 是 Workspace 保护逻辑的较早重复草稿，已在 PR #42 合并后关闭；#42 是覆盖权限 / 并发 / 移动端的统一版本。PR #38 是基于旧主线的安全草稿，未合并；当前主线版本为 #43。

### 最新主分支验证

上述 PR 的 CI 和 Android 双 ABI 检查均在合并前通过。`main` 的合并提交 `9503d04` 又触发独立的 push CI 与 Android APK 构建；这两项主分支验证以对应 commit 的最终 Actions run 结果为准，不得用 PR 检查替代。PR 构建产物均为 Debug CI APK；Release signing job 在 PR / main push 事件中跳过是预期行为。

### 仍然阻断 v0.1.3 发布的实际验收

- 配置四项受保护的 Android Release signing repository secrets，并使用专用版本 tag 运行正式双 ABI Release；检查两份 Release APK 的 signer 证书指纹一致，并验证安装、覆盖升级及数据保留。
- 在 Huawei Mate 20 Pro / Android 10 实机验证登录 / Token、WebView、Chat、Workspace 编辑、软键盘 viewport、主题、统计及启动恢复。
- 对实际服务路径执行隔离备份 / 恢复演练：停服、备份、恢复到新目录，使用匹配的 `DSH017_DB_PATH` / data / preset 路径启动恢复副本，逐项核验聊天和 Workspace 记录后才可考虑退役原数据。
- 使用真实用户自行配置的 Provider / Magpie / Qoder 凭据验证模型列表、连通测试、流式聊天和授权流程；凭据不进入仓库、Issue 或聊天记录。
- 公开 Release 仍是 `v0.1.2`；未更改其 tag / assets，也未创建 `v0.1.3`。

自动化验证已明显扩大，但上述签名、恢复、供应商和手机验收未完成前，不把 P0 标记为已全部关闭，不创建正式新版本。

---

## 0.4 执行状态增补（2026-11-07，Provider 本地 E2E 合入）

最新功能主线包含 PR #45 合并提交 `c3356d1709f44a6d60cc03daed7dad9a2e2ae46a`。它新增本机 loopback OpenAI-compatible Chat E2E：实际执行 Flask `/api/chat`、Provider resolve、DNS-pinned HTTP transport、Chat Completions payload 与 SSE 解析；验证请求路径、Bearer header、`stream: true`、内容分块和 `[DONE]`，并证明未被 allow-list 接受的模型不会发出请求。测试使用合成凭据与 `127.0.0.1` 服务，不调用真实供应商。

PR #45 的 Python 3.10 / 3.11 / 3.12 CI [run #42365818465](https://github.com/2719126468-ship-it/dsh017/actions/runs/42365818465) 全部通过；Android [run #42365818534](https://github.com/2719126468-ship-it/dsh017/actions/runs/42365818534) 的 ARMv7 / ARM64 Debug packaging 全部通过。正式 Release jobs 在 PR 事件中按设计跳过。

### 0.4.1 Legacy Debug 到 Release 的包名迁移

已从 `v0.1.2` tag 的 Gradle 与 Android workflow 交叉确认：公开 APK 使用 `assemble*Debug`，`applicationId` 为 `com.dsh017.android` 且 Debug suffix 为 `.debug`，因此安装包名为 `com.dsh017.android.debug`。新版正式 Release 使用无 suffix 的 `com.dsh017.android`。这两个应用不是 Android 的同一 package，不能做原地覆盖更新，也不会共享 app-private SQLite / presets / SharedPreferences / Android Keystore namespace。

因此将迁移目标单独登记为 [P0 #46](https://github.com/2719126468-ship-it/dsh017/issues/46)：旧包通过 Android SAF 用户授权导出便携备份，新 Release 首次启动前验证并导入到独立私有目录；导出数据不含 API keys、auth/admin tokens 或 Android Keystore 密钥，用户在新包中重新输入凭据。旧包必须保留，直至真实 Android 10 设备验收成功。#24 下一版 Release 被 #46 阻断。

### 0.4.2 调整后的签名 / 发布任务边界

- [#31](https://github.com/2719126468-ship-it/dsh017/issues/31) 已重新打开：只跟踪持久 Release signer、Secrets 配置状态、双 ABI 统一 signer 和连续正式 Release 的覆盖升级；不再把 Debug-to-Release 当作普通包升级。
- [#46](https://github.com/2719126468-ship-it/dsh017/issues/46) 跟踪从已发布 Debug package 向 Release package 的显式导出 / 导入迁移。
- [#26](https://github.com/2719126468-ship-it/dsh017/issues/26) 的本机 Provider E2E 已具备；真实 HTTPS 上游 / 用户模型仍未通过实际凭据验收。
- 公开 Release 仍是 `v0.1.2`。未配置并验证真实签名 Secrets、#46 的 Android 实机迁移、#28 的真实恢复演练、#25/#30 实机体验及 #26/#27 真实供应商授权前，不发布 `v0.1.3`。

---

## 1. 愿景、使命与产品边界

### 1.1 Vision

让个人拥有一个属于自己的、可扩展、可控制、能够持续承载工作上下文的 AI 数字工作环境。

### 1.2 Mission

把现有模型能力、个人数据、项目文件、媒体资源和外部工具整合为一套可靠的工作流程，让用户可以在一个统一入口中理解问题、组织工作、授权执行、检查结果并保留成果。

### 1.3 一句话定位

**DSH-017 = Your Personal AI Operating Environment。**

面向个人用户的、可自托管或本地运行的 AI 工作环境；以统一智能入口连接 Workspace、受控 Agent、个人数据和日常服务。

### 1.4 首要用户与扩展用户

| 阶段 | 目标用户 | 要解决的主要问题 |
|---|---|---|
| 当前 | 项目维护者 / 个人开发者 | 自己的 AI、文件、项目和服务分散，移动端管理不便 |
| 下一阶段 | 有自托管需求的技术型个人用户 | 希望拥有可配置模型、可控数据和 AI 项目工作区 |
| 更长期 | 独立创作者、研究者、重度 AI 用户 | 需要研究、创作、资料整理和自动化执行的一体化环境 |

先把项目维护者自己的高频工作流做到稳定，再验证第二类用户是否有相同需求。不要在没有实际使用证据前，把“所有 Android 用户”当作已经验证的目标市场。

### 1.5 为什么不是直接使用现有 AI 产品

DSH-017 不与现有 AI 产品争夺基础模型质量，而是补足它们与个人工作环境之间的连接层：

- AI 产品负责模型推理；DSH-017 负责连接用户自己的项目、文件和工具。
- AI 产品提供对话体验；DSH-017 负责将对话转化为可保存、可检查、可恢复的工作成果。
- AI 产品通常以其自身工作区为中心；DSH-017 以用户可控制的数据和部署环境为中心。
- AI 产品可以作为供应商；DSH-017 保留切换供应商和本地 Gateway 的能力。

**差异化假设：** 用户愿意为“跨模型、跨项目、跨设备、可控执行”的连续工作流使用 DSH-017。这个假设必须通过实际任务完成率、重复使用率和用户反馈验证，而不是仅靠功能清单证明。

### 1.6 产品原则

1. **Personal First：** 个人优先，不提前承担企业级复杂度。
2. **AI Native：** AI 参与工作流，而不是孤立聊天窗口。
3. **Model Agnostic：** 模型可替换，能力差异明确。
4. **Local Control：** 用户能控制数据、凭据、执行和部署。
5. **Mobile First, Not Mobile Only：** Android 是一等入口，但核心服务不与单一设备绑定。
6. **Modular Monolith First：** 先明确模块边界，不为架构时髦而过早拆微服务。
7. **Security by Design：** 权限、审批、审计和恢复属于产品功能。
8. **Practical Intelligence：** 用真实任务价值决定投入，不为演示效果堆叠能力。
9. **Portable by Default：** 数据、配置、项目和工作成果应可导出、可迁移。
10. **Reliability Before Autonomy：** Agent 的权限越大，验证、审计和回滚要求越高。

---

## 2. 产品架构：八个产品域、一个治理平面、一套核心平台

原始构想称“八大产品域”，但同时把 Portal、AI、Workspace、Agent、Media、Data、System、Mobile 和 Security 列为九项。为避免长期架构、责任归属和 Issue 标签相互矛盾，本规划正式调整为：

- **八个产品域：** Portal、AI Intelligence、Workspace、Agent、Media Center、Personal Data、System Center、Mobile Client。
- **Security Center：** 横跨八个产品域的治理平面，不单独作为孤立业务模块。
- **DSH Core Platform：** 为产品域提供统一 API、数据、任务、事件、凭据、权限和日志能力。
- **Infrastructure：** Android / Termux / Linux、自托管服务、SQLite、文件系统、Gateway 和外部模型供应商。

### 2.1 八个产品域

| 产品域 | 定位 | 当前基础 | 目标方向 | 优先级 |
|---|---|---|---|---|
| DSH Portal | 统一入口、导航、个人控制中心 | 四个 Web 服务入口、统一控制台、服务状态和统计页 | 统一工作台、跨域通知、最近工作、快捷操作 | P1 |
| AI Intelligence | 统一模型和上下文入口 | 流式聊天、历史记录、OpenAI 兼容供应商注册表、Magpie 检测 | 原生协议适配、能力描述、路由、上下文策略、调用诊断 | P0/P1 |
| AI Workspace | 项目和文件工作载体 | 多项目、文件 CRUD、版本、AI 建议与授权修改 | Diff、项目上下文、搜索、Git、可靠恢复 | P0 |
| AI Agent | 受控任务执行 | 目前有工作区 AI 修改与权限规则；尚无完整通用 Agent 引擎 | 任务计划、工具注册、审批、执行状态、恢复和报告 | P1/P2 |
| Media Center | 个人媒体消费与内容提取 | B站、短视频、播放进度、收藏、AI 视频总结等 | 媒体到笔记 / 知识 / Workspace 的工作流 | P2 |
| Personal Data | 个人知识和资料管理 | SQLite 聊天记录、项目文件、预设、备份基础 | 统一搜索、导入导出、知识索引、用户授权记忆 | P2 |
| System Center | 服务运维与诊断 | 服务看护、健康端点、日志轮转、统计控制台 | 一键诊断、Provider 健康、迁移和恢复状态、告警 | P0/P1 |
| Mobile Client | Android 移动入口和本地能力 | WebView + 嵌入式 Python/Flask，ARMv7/ARM64 构建，Keystore 桥接 | 文件选择、分享、通知、下载、离线体验和重点场景原生化 | P0/P1 |

### 2.2 Security Center：横向治理平面

Security Center 不应该变成另一个需要独立维护的页面集合。它应当向所有产品域提供共同策略：

- 身份认证、会话和 Token 生命周期。
- 角色、权限范围和高风险操作审批。
- Provider 凭据加密存储与轮换。
- 文件路径隔离、版本快照和回滚。
- Agent 工具白名单、参数校验和执行沙箱。
- SSRF、DNS 重绑定、TLS、重定向和网络出口策略。
- 数据导出、备份加密、删除传播和访问隔离。
- 操作审计、敏感信息脱敏和安全事件记录。

### 2.3 DSH Core Platform：核心平台能力

核心平台不是第九个业务页面，而是产品域共同遵守的技术契约：

1. **API 层：** 统一版本、认证、请求校验和错误结构。
2. **Domain Services：** Provider、Workspace、任务、媒体、数据和系统服务。
3. **Adapter 层：** 模型供应商、Magpie、媒体来源和外部工具适配器。
4. **Persistence：** SQLite / 文件系统、版本快照、迁移、备份和导入导出。
5. **Task Runtime：** 后台任务、状态、取消、超时、重试和恢复。
6. **Event / Audit：** 统一事件和审计记录；先使用轻量本地机制。
7. **Security Policy：** 认证、授权、审批、凭据和网络出口策略。
8. **Observability：** 结构化日志、指标、诊断和健康状态。

### 2.4 模块依赖规则

- UI 只调用公开 API，不直接读写数据库或密钥。
- Agent 只通过受控 Tool API 操作 Workspace、Media 和 Personal Data。
- Agent 不直接调用某家模型供应商；它通过 AI Intelligence 请求模型。
- Provider Adapter 不依赖页面、Workspace UI 或具体 Agent。
- Workspace 是项目文件的权威来源；Personal Data 可以建立索引，但不能暗中复制并扩大访问范围。
- System Center 可以读取健康与指标，但不应绕过业务授权修改业务数据。
- Mobile Client 是入口和设备能力层，不复制一套独立业务规则。
- Security Policy 对所有 API、工具和后台任务一致生效。

### 2.5 推荐架构演进方式

**采用模块化单体作为近期默认架构。**

保留当前可独立运行的服务和 Android 打包方式，先把内部服务边界、公共接口、数据访问和权限策略收敛好。只有当某个服务确实需要独立部署、独立资源配额、独立故障域或独立扩展时，才考虑拆分进程或服务。

不以“微服务数量”衡量架构成熟度。

---

## 3. 模块协同：从功能集合变成工作流

### 3.1 标准任务链路

1. 用户从 Portal、Chat 或 Android 发起任务。
2. AI Intelligence 识别意图、选择模型，并按授权取得相关上下文。
3. 若任务需要执行，由 Agent Orchestrator 形成任务计划和工具调用清单。
4. Security Policy 对每个工具、数据范围和操作级别进行授权。
5. Workspace / Media / Personal Data / External Tools 执行具体操作。
6. 执行结果经过验证；有风险的修改等待用户审批。
7. 结果、文件版本、任务日志和引用来源写回对应模块。
8. Portal / Mobile 展示结果、失败原因和后续可执行步骤。

### 3.2 必须优先实现的三个端到端工作流

**工作流 A：研究 → 文档 → 后续计划**

- 用户提出研究主题。
- Research Tool 搜集公开资料并保留来源。
- AI 生成结构化摘要。
- Workspace 创建文档。
- Agent 创建后续任务建议。
- 用户审核后保存。

**工作流 B：项目分析 → 修改建议 → 验证**

- Agent 获取指定 Workspace 项目上下文。
- 检查目录、相关文件和项目说明。
- 先给出修改计划和受影响文件。
- 用户授权后执行文件修改。
- 展示 Diff、保存版本快照。
- 运行允许的测试工具并归档结果。
- 任何失败都能定位到任务、文件版本和工具调用。

**工作流 C：媒体 → 知识 → 项目**

- 用户从 Media Center 选择视频。
- 生成摘要、字幕 / 关键点或学习笔记。
- 标明来源和媒体时间位置（有数据时）。
- 用户确认后保存到 Workspace 或 Personal Data。
- 后续可以在项目上下文中检索。

### 3.3 统一任务对象

未来任务引擎应至少使用以下概念（字段名可在实现阶段定稿）：

- `task_id`、`task_type`、`created_at`、`updated_at`
- `status`: queued / planning / awaiting_approval / running / verifying / completed / failed / cancelled
- `input`、`plan`、`context_refs`、`tool_calls`
- `approval_state`、`permission_scope`、`retry_count`
- `result_refs`、`error_code`、`audit_refs`

任务引擎必须支持取消、超时、幂等或重复执行保护、有限重试和失败恢复。先构建单 Agent、单任务执行能力，再考虑多 Agent 协作。

---

## 4. 技术路线与标准

### 4.1 Provider Adapter

近期已有 OpenAI Chat Completions 兼容注册表。下一步不是只增加供应商名称，而是分层演进：

1. 保持 OpenAI Chat Completions 作为基础兼容协议。
2. 定义内部统一请求 / 响应 / 流式事件结构。
3. 引入原生 Anthropic Messages Adapter。
4. 引入原生 Gemini Adapter（当真实使用场景和测试样本足够时）。
5. 为每个模型声明能力：文本、视觉、工具调用、结构化输出、上下文限制、流式行为等。
6. 将路由策略与 Provider Adapter 分离。

路由第一版只依据用户明确选择、模型能力和可用性；成本 / 延迟优化必须建立在可观测数据和用户可理解的策略上。不得偷偷把用户对话发送给备用供应商。跨供应商回退需要显式策略和可见提示。

### 4.2 Workspace

Workspace 是项目数据和修改的权威载体。功能优先级：

1. 文件和项目 CRUD 的正确性。
2. 版本快照、Diff 和恢复。
3. 项目级上下文选择、摘要和排除规则。
4. 文件搜索和项目导航。
5. Git 状态、Diff、提交和分支的只读 / 低风险起步。
6. 经审批的 Git 写操作。
7. 与 Agent 任务记录关联。

不要先做完整 IDE、远程容器、复杂插件市场或任意终端执行。

### 4.3 Agent 执行安全等级

| 等级 | 行为 | 默认策略 |
|---|---|---|
| Read | 读取用户指定范围内的数据 | 允许，但必须遵守项目 / 文件权限 |
| Suggest | 生成计划、Diff 或修改建议 | 默认首选 |
| Confirm | 用户逐次确认后写入或调用工具 | 中高风险操作的默认模式 |
| Restricted Auto | 仅在预先授权的工具、目录、参数和范围内自动执行 | 默认关闭；需管理员授权、审计和可撤销 |

禁止默认开放任意 Shell、任意 URL 请求、全盘文件访问、隐式凭据访问或无审批破坏性操作。

### 4.4 数据与搜索

按成本从低到高逐步推进：

1. 先完成聊天、Workspace 和备份的可导出格式。
2. 先做元数据与文件名搜索。
3. 再做显式选择的文件内容索引。
4. 最后才评估向量检索 / RAG。

知识索引必须记录来源、更新时间、访问范围和删除状态。删除原始文件或对话时，应同步处理索引。任何索引内容进入模型上下文之前，都要执行同样的权限检查。

### 4.5 Android 与部署

- 当前 WebView + 本地 Flask 服务作为兼容性基础，不重写全部 UI。
- 原生功能按实际高频需求逐个增加：文件选择、分享、下载、通知、安全存储。
- APK 只保留必要权限；本地服务默认绑定 loopback。
- Termux / Linux 自托管服务与 Android APK 共享业务 API 契约。
- ARM32 与 ARM64 的依赖能力差异必须在构建和发布说明中清楚标出。
- 设备资源有限时，后台索引、Agent 并发和缓存必须可配置、可限额。

---

## 5. 2026 Q4—2027 Q4 路线图

路线图按季度定义结果，不用“完成多少功能”代替产品验收。所有里程碑都是目标，不是现有完成状态。

### 阶段 0：2026 Q4 — v0.1.2 稳定化

**目标：把当前功能变成可重复构建、可恢复、可验收的版本。**

重点：
- 核对主分支、CI 和 Android 双架构构建结果。
- 验证 Provider 保存、模型发现、真实聊天和 SSE。
- 验证 Magpie 检测、模型同步、Qoder 授权后的真实调用链。
- 回归 Workspace CRUD、版本、Diff / 恢复及 AI 修改权限。
- 验证数据库备份与真实恢复。
- 检查 Token、密钥、HTTP 暴露边界和日志脱敏。
- 验证 APK 版本、标签、校验和与安装步骤。
- 更新 README、Android README、变更记录和已知限制。

**里程碑 M0：** v0.1.2 候选版本通过发布门槛。未通过的项目明确列为阻断项，不靠文档宣称完成。

### 阶段 1：2027 Q1 — v0.2.0 Workspace 产品化

**目标：让用户可以完整管理一个 AI 项目。**

重点：
- Workspace 编辑体验和移动端布局。
- 文件 Diff、版本历史和恢复体验。
- 项目级上下文和忽略规则。
- 元数据 / 文件名搜索。
- Git 状态与 Diff 的只读集成。
- Prompt 与项目说明管理。
- 任务和文件版本关联的基础数据结构。

**里程碑 M1：** 完成“创建项目 → 添加文件 → AI 分析 → 审核修改 → 查看 Diff → 恢复版本”的端到端流程。

### 阶段 2：2027 Q2 — v0.3.0 受控 Agent

**目标：让 Agent 可靠执行有限任务。**

重点：
- 统一任务状态与任务记录。
- 工具注册表、参数 Schema 和权限策略。
- Research Tool、Workspace File Tool、受限测试 Tool。
- 审批、取消、超时、重试和恢复。
- 每次执行生成审计记录和结果报告。
- 任务执行基准测试集。

**里程碑 M2：** 至少三类限定流程可以重复完成：资料研究并生成文档、项目分析并进行授权文件修改、项目测试并归档结果。

### 阶段 3：2027 Q3 — v0.4.x 个人数据与跨域协作

**目标：让聊天、项目和媒体形成可控的资料闭环。**

重点：
- 聊天 / 项目 / 媒体资料的统一导出。
- 全局搜索第一版（元数据和用户选择的文件内容）。
- 研究来源和媒体引用关联。
- 知识索引的权限与删除传播。
- 备份加密与恢复演练。
- Android 分享、文件选择、下载和通知等高价值原生能力。

**里程碑 M3：** 用户能找到并重新使用之前的项目资料，且搜索结果保留来源和访问权限。

### 阶段 4：2027 Q4 — v1.0.0 产品化准备

**目标：从个人开发项目变成可长期运行、可部署、可维护的个人产品。**

重点：
- 三个核心工作流稳定运行。
- Provider Adapter 与模型能力描述稳定。
- 系统诊断中心和备份 / 恢复流程完善。
- Android 与自托管部署文档清晰。
- 数据导入导出、升级和迁移可重复。
- 安全、隐私、性能和兼容性复审。
- 评估开源贡献和扩展接口，但不默认承诺插件市场。

**里程碑 M4：** 达到第 10 节的 v1.0 验收定义；若关键安全、恢复或端到端可靠性不达标，推迟 v1.0，不以日期强行发布。

---

## 6. 版本策略

| 版本 | 战略主题 | 交付定义 |
|---|---|---|
| v0.1.2 | 稳定化 | 现有聊天、Workspace、Provider、Android 和安全能力可构建、可回归、可恢复 |
| v0.2.0 | Workspace | 项目工作区、Diff、版本、上下文与 Git 基础能力 |
| v0.3.0 | Agent | 任务引擎、工具调用、审批、执行日志和受控任务 |
| v0.4.x | Personal Data | 搜索、导出、索引和跨域资料流 |
| v1.0.0 | Personal AI Environment | 核心工作流、移动入口、安全、运维、备份与部署达到稳定验收 |

版本号是路线建议。任何版本都必须经过发布门槛，不因路线图中出现版本号就视为已排期承诺。

---

## 7. GitHub Issues 任务树

以下是项目执行 Backlog。v0.1.2 稳定化 P0 已转为实际 GitHub Issues #24–#31；v0.2.0 及后续 P1/P2 项仍是待排期建议。Issue 状态以 GitHub 当前状态为准。

### EPIC P0 — v0.1.2 稳定化

<text>**已由自动化证据验证：**</text>
- [x] **P0-02 CI Evidence**：当前 main HEAD 的 Python 3.10 / 3.11 / 3.12 CI 通过；详见 [run #42363124784](https://github.com/2719126468-ship-it/dsh017/actions/runs/42363124784)。
- [x] **P0-03 Android ARM Build**：当前 main HEAD 的 ARMv7 / ARM64 Build Job 均通过并上传 workflow artifacts；详见 [run #42363124808](https://github.com/2719126468-ship-it/dsh017/actions/runs/42363124808)。这不代表实机运行已通过。
- [x] **P0-10 Strategy / README link**：Master Plan 已提交至 `docs/MASTER_PLAN.md`，README 已添加入口。

**仍需完成的 P0：**
- [ ] **P0-01 Release alignment**：[#24](https://github.com/2719126468-ship-it/dsh017/issues/24) — 处理现有 v0.1.2 Release 与最新 main 的提交差异；验收后发布新的 patch 版本。
- [ ] **P0-04 Android device smoke test**：[#25](https://github.com/2719126468-ship-it/dsh017/issues/25) — 在真实 Android 设备上验证安装、服务启动、Chat、Workspace、主题和文件访问。
- [ ] **P0-05 Provider E2E**：[#26](https://github.com/2719126468-ship-it/dsh017/issues/26) — 使用真实 Provider 验证密钥、模型发现、聊天、SSE、错误和离线场景。
- [ ] **P0-06 Magpie / Qoder E2E**：[#27](https://github.com/2719126468-ship-it/dsh017/issues/27) — 验证真实 Gateway 检测、授权、模型同步与真实请求。
- [ ] **P0-07 Workspace Regression**：[#30](https://github.com/2719126468-ship-it/dsh017/issues/30) — 验证项目、文件、版本、冲突、审批、拒绝规则和自动修改熔断。
- [ ] **P0-08 Backup Restore Drill**：[#28](https://github.com/2719126468-ship-it/dsh017/issues/28) — 在隔离目录完成数据库与用户数据备份、恢复和校验。
- [ ] **P0-09 Security Regression**：[#29](https://github.com/2719126468-ship-it/dsh017/issues/29) — 验证认证、管理员权限、SSRF、DNS 固定、重定向、凭据脱敏和网络边界。
- [ ] **P0-11 Android Signing Continuity**：[#31](https://github.com/2719126468-ship-it/dsh017/issues/31) — 验证跨 CI 构建签名证书连续性，确保升级安装可行且不要求卸载丢失应用私有数据。

### EPIC P1 — v0.2.0 Workspace 产品化

- [ ] **P1-01 Workspace UX Audit**：梳理手机竖屏、平板 / 桌面宽屏和窄视口布局。
- [ ] **P1-02 File Diff Viewer**：提供明确的新增、删除、修改差异展示。
- [ ] **P1-03 Version History UX**：版本列表、预览、恢复确认和恢复结果反馈。
- [ ] **P1-04 Project Context**：项目说明、相关文件选择、排除规则和上下文长度提示。
- [ ] **P1-05 Workspace Search**：先做文件名、路径和元数据搜索。
- [ ] **P1-06 Git Read-only Integration**：状态、分支、未提交文件和 Diff；默认不自动提交。
- [ ] **P1-07 Prompt Library**：可复用 Prompt、项目级说明和导入导出。
- [ ] **P1-08 Workspace API Contract**：统一分页、错误、版本冲突和权限响应。
- [ ] **P1-09 Workspace E2E Tests**：建立浏览器端到端关键流程测试。

### EPIC P1 — AI Intelligence / Provider

- [ ] **P1-10 Internal Model Contract**：统一模型请求、响应、流事件、错误和使用量结构。
- [ ] **P1-11 Capability Registry**：描述 vision、tools、json、streaming、context 等能力。
- [ ] **P1-12 Anthropic Native Adapter**：原生 Messages API，含工具和流式兼容测试。
- [ ] **P1-13 Gemini Native Adapter**：在需求验证后实现原生接口。
- [ ] **P1-14 Provider Diagnostics**：连接测试、模型探测、错误分类和延迟统计。
- [ ] **P1-15 Model Routing Policy**：仅在能力 / 用户偏好 / 可用性规则明确后实施。
- [ ] **P1-16 Provider Contract Tests**：为每个 Adapter 建立公共兼容测试集。

### EPIC P1/P2 — Agent Runtime

- [ ] **P2-01 Task Schema & Lifecycle**：统一任务对象、状态迁移和持久化。
- [ ] **P2-02 Tool Registry**：工具描述、参数 Schema、版本和权限声明。
- [ ] **P2-03 Approval Service**：逐次审批、审批超时和拒绝处理。
- [ ] **P2-04 Workspace Read Tool**：限定项目和文件范围的只读工具。
- [ ] **P2-05 Workspace Patch Tool**：产生 Diff、快照、版本检查和用户确认。
- [ ] **P2-06 Research Tool**：公开资料检索、来源记录、超时和请求限额。
- [ ] **P2-07 Task Cancellation & Recovery**：取消、超时、有限重试和恢复。
- [ ] **P2-08 Execution Audit**：工具输入 / 输出摘要、操作者、权限和结果记录。
- [ ] **P2-09 Agent Benchmark**：固定任务集、成功条件、误修改率和恢复测试。
- [ ] **P2-10 Restricted Auto Policy**：默认关闭，按工具 / 目录 / 参数范围逐项授权。

### EPIC P2 — Personal Data / Media Workflow

- [ ] **P2-11 Export / Import**：聊天、项目、预设和元数据的稳定格式。
- [ ] **P2-12 Global Search Metadata**：先检索项目、文件名、会话和媒体元数据。
- [ ] **P2-13 File Content Index**：用户明确选择后索引内容，保存来源和权限。
- [ ] **P2-14 Index Deletion Propagation**：源文件删除、权限改变时同步更新索引。
- [ ] **P2-15 Media-to-Workspace**：摘要、引用和笔记经用户确认后进入 Workspace。
- [ ] **P2-16 Backup Encryption**：评估并实现备份加密、密钥恢复和验证。
- [ ] **P2-17 Personal Memory Controls**：记忆来源、查看、纠正、删除和不纳入上下文的选项。

### EPIC P1/P2 — System / Android / Quality

- [ ] **P2-18 System Diagnostics**：聚合服务、数据库、Provider、Magpie 和磁盘检查。
- [ ] **P2-19 Structured Logs**：统一字段、关联 ID、脱敏和日志保留策略。
- [ ] **P2-20 Android Native Share**：分享文本 / 文件到 DSH。
- [ ] **P2-21 Android File Picker & Downloads**：原生选择、下载和保存路径处理。
- [ ] **P2-22 Android Notifications**：任务状态通知和通知权限管理。
- [ ] **P2-23 Database Migrations**：明确 schema 版本、迁移顺序和失败恢复。
- [ ] **P2-24 Performance Budget**：定义 ARM32 / ARM64 的内存、并发、启动和响应基线。
- [ ] **P2-25 Release Smoke Suite**：每次发布前执行统一的安装、升级、主要工作流和恢复检查。

### Issue 规范

每个实际创建的 Issue 必须有：

- 用户问题与使用场景。
- 当前行为与预期行为。
- 明确验收条件（可测试）。
- 影响模块和 API / 数据结构。
- 安全与隐私影响。
- 自动化测试和设备测试要求。
- 文档更新要求。
- 依赖项、优先级和目标版本。

建议标签：
- 领域：`core`、`ai-intelligence`、`workspace`、`agent`、`media`、`personal-data`、`system`、`android`、`security`。
- 优先级：`priority:P0`、`priority:P1`、`priority:P2`。
- 类型：`type:bug`、`type:feature`、`type:security`、`type:technical-debt`、`type:research`。

优先级定义：
- **P0：** 阻断发布、数据完整性、安全边界或核心流程。
- **P1：** 当前季度关键产品结果。
- **P2：** 后续季度能力、优化或研究。

---

## 8. 发布验收标准

### 8.1 每次合并的最低要求

- Python 编译和单元 / 路由测试通过。
- 内联 JavaScript 语法检查通过。
- Shell 脚本语法检查通过。
- 新增业务逻辑有回归测试。
- 修改 API 或数据结构时更新文档。
- 不引入明文密钥、Token、Cookie 或个人数据。
- 对文件写入、网络请求和权限变更进行安全检查。

### 8.2 v0.1.2 发布门槛

- 主分支的 CI 证据完整且通过。
- ARMv7、ARM64 APK 均完成构建并验证 SHA256。
- 在可用设备上完成安装启动和主要页面 Smoke Test；未测试的设备 / 网络组合明确列出。
- Provider、Magpie / Qoder 和 Workspace 关键链路有实际或可复现的集成测试证据。
- 数据备份与恢复至少完成一次隔离环境演练。
- 无未解决的 Critical / High 安全问题。
- Token 和 Provider 密钥未进入仓库、日志或前端响应。
- Release 标签、Gradle versionName、资产命名和 README 一致。

### 8.3 v0.2.0 发布门槛

- Workspace 完整主流程可在移动端完成。
- 文件修改有 Diff、版本快照、冲突检查和恢复路径。
- 项目上下文由用户选择，界面说明实际发送给模型的数据。
- Git 第一阶段默认为只读。
- 关键浏览器端到端测试通过。

### 8.4 v0.3.0 发布门槛

- Agent 所有工具均有输入 Schema、权限声明和超时。
- 高风险工具必须审批。
- 任务可取消；失败可定位；重复请求不会造成未预期的重复写入。
- 每次写入可追踪到任务、操作者和文件版本。
- 固定任务集达到预先定义的成功率门槛；所有误修改和未授权操作必须单独披露。
- 未授权操作次数为 0。

### 8.5 v1.0.0 定义

只有同时满足以下条件，才称为 v1.0：
- 三条核心跨模块工作流稳定、可重复。
- Workspace 的文件修改、Diff、历史和恢复完整。
- Provider 适配有稳定内部契约和兼容测试。
- Agent 有审批、取消、审计和失败恢复。
- Personal Data 的导出、备份和恢复真实可用。
- Android 与自托管路径有清楚的支持矩阵和安装升级文档。
- System Center 能对关键依赖给出可操作的诊断。
- 安全审查没有未处置的 Critical / High 问题。
- 真实使用者能够在一周内多次完成有价值任务，而不是只完成演示。

---

## 9. KPI 与成功判断

先建立基线，再设目标；没有采集口径的数据不能当 KPI。

| 维度 | 指标 | 采集方式 | 目标方向 |
|---|---|---|---|
| 工程 | CI 通过率、失败重开率 | GitHub Actions | 发布分支必须通过；失败需分类 |
| 发布 | 双架构构建成功率、校验和完整率 | Release workflow | 所有正式发布资产可校验 |
| 稳定性 | 聊天请求成功率、SSE 中断率 | 服务端指标 | 按 Provider 分组并逐步改善 |
| 体验 | 首 Token 延迟、文件保存耗时 | 请求 / UI 计时 | 建立 ARM32 / ARM64 基线 |
| Workspace | 文件保存、Diff、恢复成功率 | Workspace 审计事件 | 关键操作可追踪、可恢复 |
| Agent | 任务完成率、工具成功率、误修改率 | Task Runtime | 固定基准集持续提高 |
| 安全 | 未授权操作、敏感凭据泄露、越权写入 | 安全测试 / 审计 | 目标 0 |
| 数据 | 备份验证率、恢复成功率、迁移失败率 | 定期演练 | 发布前完成恢复演练 |
| 产品价值 | 每周真实完成任务数、重复使用率 | 匿名本地使用统计或自愿记录 | 证明持续价值而非功能使用量 |

### 建议的成功判据

- **工程成功：** 可构建、可测试、可发布、可升级、可恢复。
- **产品成功：** 用户通过 DSH-017 完成工作，而不是仅打开页面。
- **智能成功：** 模型能使用用户授权上下文，Agent 能可靠完成有限任务。
- **数据成功：** 用户能理解、导出、备份、恢复并控制自己的数据。
- **战略成功：** 各模块共享工作流和平台契约，新增功能不会不断制造孤岛。

---

## 10. 技术债清单

以下清单按当前可见仓库证据列出。标为“待核对”的项目不代表已经确认存在缺陷，必须先复现或审计再决定修复方案。

| ID | 技术债 / 未完成项 | 证据 / 依据 | 风险 | 建议处理 |
|---|---|---|---|---|
| TD-01 | 发布证据与版本标签需要对齐 | Gradle 当前 versionName 为 0.1.2；APK Release 由 v* 标签触发 | 高 | 核对标签、Actions、Release 资产、SHA256 和安装结果 |
| TD-02 | 实机测试证据不足 | Android README 说明构建方式和 ABI 差异，但仓库文档不能证明目标设备已验收 | 高 | 建立设备 / Android / ABI / WebView 测试矩阵 |
| TD-03 | ARMv7 网络能力降级 | ARMv7 使用 requests fallback，curl_cffi 浏览器 TLS impersonation 不可用 | 中高 | 明确支持矩阵，关键接口实测，避免误导用户 |
| TD-04 | Provider 协议以 OpenAI Chat Completions 为主 | providers.py 的注册表协议字段和路由实现 | 中高 | 建立内部契约，再按需求增加原生 Adapter |
| TD-05 | Workspace / Chat UI 内聚度偏高 | workspace_routes.py、workspace_ui.py、chat_ui.py 承载大量逻辑 | 中 | 有测试保护后按 service / template / API 分层，不做大爆炸重写 |
| TD-06 | API 错误结构可能不一致 | 多个旧路由采用 code/message，部分新接口使用 HTTP 状态码 | 中 | 定义统一错误 Schema，渐进迁移 |
| TD-07 | 自动化测试偏单元 / 源码断言 | 当前 tests 包含路由、逻辑和 HTML / JS 字符串检查 | 中高 | 增加浏览器 E2E、真实 HTTP、设备 Smoke Test |
| TD-08 | 统一任务引擎尚未建立 | 当前有聊天停止控制和 Workspace 编辑，但没有通用 Task Runtime | 高（未来能力） | v0.3 前先定义任务状态和工具接口 |
| TD-09 | Git 项目集成尚未实现为完整工作流 | 当前 Workspace 已有项目 / 文件 / 版本能力；路线仍将 Git 列为下一阶段 | 中 | 先只读，再审批写入 |
| TD-10 | Personal Data / 全局搜索尚未形成完整产品 | 当前有 SQLite 会话、项目文件和备份，但没有完整跨域索引 | 中 | 元数据搜索优先，后续再做内容索引 |
| TD-11 | 系统诊断仍偏服务状态和统计 | hub 有 health / status / stats 基础；一键依赖诊断仍属目标 | 中 | 加 Provider、DB、备份、Magpie 的可操作检查 |
| TD-12 | 数据库迁移与恢复策略需系统化验证 | 已有 SQLite 数据和备份逻辑，但需独立验证多版本迁移 / 恢复 | 高 | schema version、迁移测试、恢复演练 |
| TD-13 | 局域网 HTTP 凭据保护依赖可信网络 | README 明确提示 HTTP Basic / Bearer 在普通 HTTP 网络中不加密 | 高 | 默认建议 VPN / HTTPS；评估安全反向代理配置 |
| TD-14 | 严格 CSP 尚未启用 | README 说明未引入会破坏内联脚本的严格 CSP | 中 | 先收敛内联脚本和 nonce/hash 策略，再逐页启用 |
| TD-15 | 模块 / 文档边界需持续同步 | 新增 Provider、Workspace 和 Android 能力后，目录与接口持续演进 | 低中 | 每个跨模块 PR 更新架构图、README 和变更记录 |
| TD-16 | Debug / Release APK 签名迁移仍未完成端到端验证 | 已实测四个 Debug APK 的签名证书指纹全部不同；PR #37 已合入 GitHub Secrets 驱动的持久化 Release 签名和 fail-closed 发布流程，但尚未验证正式签名构建与设备升级 | 高 | 安全配置签名 Secrets；使用专用测试 tag 生成双 ABI Release；检查同证书；在设备上验证 Release-to-Release 升级和旧 Debug 包数据迁移 |

技术债处理原则：先补测试和可观测性，再重构；先解决数据、安全和发布风险，再做代码美化。不得把“重写全部模块”作为默认偿还技术债的方法。

---

## 11. 风险登记表

| ID | 风险 | 可能性 / 影响 | 预防措施 | 触发后的应对 |
|---|---|---|---|---|
| R-01 | 功能范围扩张导致长期无法发布 | 高 / 高 | 季度目标、P0/P1/P2、冻结范围 | 暂停新功能，只修复发布阻断项 |
| R-02 | Agent 越权或误修改文件 | 中 / 极高 | 工具白名单、审批、版本快照、限制目录 | 立即停用相关工具、恢复版本、保留审计 |
| R-03 | 数据库升级或迁移造成数据损坏 | 中 / 极高 | schema 版本、备份、迁移测试 | 停止写入，恢复备份并导出诊断 |
| R-04 | Token / API Key 泄露 | 中 / 极高 | Keystore / 私有文件、脱敏、轮换、不回显 | 撤销凭据、轮换密钥、检查日志与访问记录 |
| R-05 | 局域网 HTTP 被旁路监听 | 中 / 高 | 可信网络限制、VPN / HTTPS、最小暴露 | 立即停止不可信网络访问并轮换 Token |
| R-06 | Provider API 行为不兼容或变更 | 高 / 中高 | Adapter、契约测试、错误分类 | 隔离问题供应商，保留其他 Provider 可用 |
| R-07 | DNS / SSRF / 重定向绕过网络策略 | 中 / 极高 | DNS pinning、目标校验、禁止重定向、出口测试 | 禁止相关 Provider / URL，发布安全修复 |
| R-08 | ARM32 资源或 TLS 兼容不足 | 高 / 中高 | ABI 测试矩阵、并发 / 内存限制 | 降级非核心能力并公开限制 |
| R-09 | WebView 与系统版本差异导致页面异常 | 中 / 高 | WebView 版本检查、兼容测试 | 提供诊断、刷新或受支持版本说明 |
| R-10 | 外部服务限流、过载或中断 | 高 / 中 | 超时、有限重试、用户可见状态 | 暂停重试、切换用户明确选择的 Provider |
| R-11 | 搜索 / 向量索引扩大敏感数据暴露面 | 中 / 高 | opt-in、访问控制、删除传播、来源标记 | 停止索引任务并重建 / 清理索引 |
| R-12 | 自托管升级导致配置和数据路径混乱 | 中 / 高 | 单一数据目录约定、迁移工具、升级前备份 | 回滚程序并恢复数据快照 |
| R-13 | 个人项目维护负担超过可持续范围 | 高 / 高 | 严格限制领域数量、减少低价值维护 | 冻结 P2，保留核心稳定能力 |
| R-14 | 过早插件化 / 微服务化增加维护复杂度 | 中 / 高 | 模块化单体优先、按真实瓶颈拆分 | 暂停平台化工作，回归稳定接口 |

---

## 12. 研发资源配置与停止规则

建议的长期精力分配（不是强制工时）：

| 方向 | 参考占比 |
|---|---:|
| Core、Security、稳定性和发布 | 30% |
| Workspace 与 Agent | 35% |
| AI Provider 与模型能力 | 15% |
| Android 与 UI 体验 | 12% |
| Media 与其他模块 | 8% |

### 停止 / 延后规则

符合任一条件时，默认不进入当前季度：

- 没有明确用户问题，只是“看起来先进”。
- 与已有能力重复，无法说明新增价值。
- 依赖未建立的权限、数据或任务接口。
- 没有可执行的验收标准。
- 会显著扩大安全面，但没有相应测试和审计。
- 会增加 ARM32 / 低内存设备负担，却没有降级策略。
- 需要维护大量第三方适配，但没有稳定使用需求。
- 会推迟当前 P0 版本发布。

### 当前明确延后的项目

- 多 Agent 自主协作和复杂 Agent 市场。
- 任意 Shell / 容器执行。
- 企业级多租户、组织管理和计费。
- 大规模向量数据库 / RAG 平台。
- 完整 IDE 或云端开发容器。
- 大型第三方插件市场。
- 全量 Android 原生重写。
- 自研基础模型或模型训练。

---

## 13. 项目治理与决策机制

### 13.1 每个 Issue 必须回答

1. 用户是谁，遇到什么问题？
2. 哪个产品域负责？
3. 是否复用现有能力？
4. API、数据和权限边界是什么？
5. 失败时如何恢复？
6. 如何自动测试和人工验收？
7. 文档如何更新？
8. 是否影响本季度里程碑？

### 13.2 Pull Request 规则

- 一个 PR 尽量只解决一个可验收问题。
- 涉及安全、凭据、文件写入、网络出口或迁移时必须单列风险说明。
- 新增工具必须声明权限、参数、超时和日志行为。
- UI 变更应覆盖移动与桌面视口。
- 所有数据结构变更要有升级 / 兼容策略。
- 不允许把真实 API Key、Token、Cookie 或个人数据提交到仓库。
- 只有 CI 和验收证据完整后才合并进发布主线。

### 13.3 版本发布门禁

需求完成 ≠ 版本可发布。发布必须具有：
- 对应提交和标签。
- 自动化测试结果。
- 构建资产和校验和。
- 关键设备测试记录。
- 迁移 / 备份结果。
- 已知问题列表。
- 回滚 / 恢复说明。

### 13.4 战略变更机制

每季度回顾：
- 哪些真实工作流被重复使用？
- 哪些功能无人使用或维护成本过高？
- 当前用户最大阻塞是什么？
- 当前架构是否有实测瓶颈？
- 哪些风险的可能性或影响上升？
- 下季度是否需要调整预算、目标或产品域优先级？

战略允许调整，但必须记录原因和影响，不能每次遇到新想法就改变核心方向。

---

## 14. 接下来 30 天的执行清单

**窗口：2026-11-07 至 2026-12-07。** 以当前开发状态，优先把 v0.1.2 做成可靠候选版本，不启动大规模 Agent 或知识库建设。

### 第一周：证据与发布基线

- 核对最新提交、分支、标签、Actions 和 Release。
- 获取 CI / APK workflow 的真实运行结果。
- 建立 ARMv7 / ARM64 设备测试表。
- 检查版本号与 Release 文档一致性。

### 第二周：核心功能回归

- Provider 新增 / 模型发现 / 真实请求 / SSE。
- Magpie Gateway / Qoder 真实授权链路。
- Workspace 项目、文件、版本和 AI 编辑。
- 三主题、明暗模式、Stats 页面与手机端布局。

### 第三周：数据与安全演练

- 备份和恢复。
- Token 权限与管理员接口。
- Provider 网络出口、DNS pinning 和重定向测试。
- Android 私有存储与 Keystore 行为。
- 日志脱敏和 HTTP / VPN 边界说明。

### 第四周：修复、冻结与发布候选

- 处理 P0 缺陷。
- 更新文档和变更记录。
- 冻结 v0.1.2 范围。
- 生成双架构候选构建。
- 形成发布验收报告；未达标则保留候选状态，不强行发布。

---

## 15. 最终成功定义

DSH-017 的成功不以页面数量、供应商数量、模型数量或 Agent 数量衡量。

最终看它是否能持续完成以下事情：

1. **理解工作：** 取得用户授权的项目和上下文，而不是只依赖一次聊天输入。
2. **承载工作：** 在 Workspace 中组织项目、文件、版本和结果。
3. **执行工作：** Agent 使用有限工具完成任务，经过验证并能被撤销。
4. **连接数据：** 聊天、媒体、知识与项目可以有来源、有权限地关联。
5. **保护数据：** 用户知道数据存在哪里、发给哪个模型、谁能访问，以及如何导出和恢复。
6. **长期运行：** 系统可以诊断、备份、升级和恢复。
7. **移动可达：** 用户可以通过 Android 完成主要高频操作，而不被设备资源限制拖垮。

> **最终战略判断：** DSH-017 以个人 AI 工作平台为核心，以现有个人门户和媒体服务为入口与场景，以受控 Agent 作为执行引擎，以个人数据和跨模块工作流形成长期价值。先做好一个人每天真正愿意使用、数据真正可控、关键任务真正可靠完成的系统，再考虑扩展为更广泛的个人 AI 生态。
