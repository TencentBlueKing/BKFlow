# Harness E2E hardening implementation plan

**Goal:** 修复已复现的自主编排、调试结果读取和配置录入问题，不放宽授权或执行门禁。

**Architecture:** 保持 15 个 MCP Tool。把编排协议公开在 validate_workflow 的参数 Schema；插件 Schema 仍按需检索。get_debug_session 增加独立于 Evidence history 的有界节点分页，终态只读本会话已脱敏的持久化快照。空间 Admin 使用条件表单，不修改数据库模型。

**Tech stack:** Django/DRF、Pydantic、OpenAPI、pytest。

## 执行清单

- [x] 协议与校验：以真实错误形态补回归；公开完整 a2flow v2 参数与合法示例；对错误节点类型、缺少 binding 字段、重复或不匹配 binding 返回静态安全修复提示。
- [x] 调试读取：摘要、节点分页与单节点读取；不增加单份 Evidence 安全预算；终态保存本会话快照，分页游标绑定会话和快照；保持权限、脱敏及关停语义。
- [x] 配置管理：JSON 配置不要求文本占位；Harness 可信部署绑定在保存前验证；提供接入检查清单，不自动开启授权。
- [x] 同步接口文档、网关 YAML、文档包；完成一次独立审查，发现项均已增加复现测试并修复。

## 验证与边界

- 工作区：`ai/a2flow-harness-master-sync` 的已有隔离 worktree；保留未跟踪联调证据。
- 基线：validator 59 tests passed（2026-10-09，现有 Python 3.9 环境）。
- 测试使用干净进程环境、仓库 tests/interface.env、已核对的本地 SQLite / LocMem / memory broker；不连接线上。
- 按 RED → GREEN 逐项验证；本地通过不等于云端或真实 Agent E2E 验收。
- 本地实施验收阶段不提交、不推送、不部署，不改线上配置；BKAIDev 澄清回传和知识库模型权限另行定位。后续交付以用户新增授权为准。

## 执行记录

- 初始化：确认本地 SQLite 设置及内存缓存/消息队列；原有 validator 回归通过。尚未修改实现。
- RED：8 项新增校验/表单用例失败；修复后连同原 validator 共 69 项通过。协议 Schema 回归先因缺少 example 失败，随后通过。
- RED：大上下文分页、终态续页、快照漂移复现失败；修复并增加单节点、跨会话游标、非法参数、最终 APIGW guard 回归。
- 首轮完整回归：2,156 passed / 2 failed / 9 skipped。两处失败是新增快照事件后的 Golden Case 预期，已显式更新；定向 91 项通过。
- 独立审查裁决：保留字段/深层兼容 context 阻断最终响应、waiting/paused 汇总遗漏、快照 code 污染反馈归因均采纳并修复；各项均有 RED → GREEN 证据。version:null 广告与运行时不一致、重复 binding 提示缺失同样修正。
- 事务补查：分片持久化失败回滚全部新快照并保持 RUNNING；过期分页游标不会回滚已确认终态；终态多次读取只保存一份快照。MySQL 真并发仍需目标数据库验证，不能用 SQLite 结果替代。
- 审查未覆盖项裁决：云端 Schema 刷新、OAuth 和真实 BKAIDev E2E 留给发布后的验收；本地无云端写入。审查者未重审最终修复，由主执行者以针对性回归和最终完整回归验证，不宣称独立复审已通过。
- 静态检查：flake8、git diff --check 通过；网关仅两个目标路由变化，auth/backend 完全保留；文档 ZIP 完整且逐项与源码一致。
- 最终完整回归：**2,169 passed / 9 skipped / 0 failed**（48.50 秒），范围为 Harness 全套、空间配置及全部 Harness APIGW 测试；报告位于 `output/harness-e2e-hardening-final.xml`。跳过项为 MySQL utf8mb4 联合索引及双连接行锁测试。Black 22.3.0 检查的 15 个 Python 文件均无需调整。
- 本地验收时状态：仍在 `ai/a2flow-harness-master-sync` 工作区；未提交、未推送、未部署；未更改云端权限、门禁、BKAIDev Agent 或知识库。
- 交付授权（2026-10-09）：用户指定通过蓝盾 `bkee/p-48c16ca956d6487d917e3710eb6d1fe6` 的 SES Smart 打包流水线构建，并在 bkop 的 `bkflow-eng-svc` 应用发布。保持现有应用身份、权限和门禁；按实际源码提交、流水线产物和 PaaS 部署记录分别确认结果，不以历史构建代替本轮验证。
