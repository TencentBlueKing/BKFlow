# 标准运维开放插件前端交付包 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出标准运维开放插件接入 BKFlow 所需的前端交互原型、页面需求文档与前后端协议文档，为后续前端实现提供明确交付基线。

**Architecture:** 这份计划不实现前端业务代码，而是围绕轻量交付包组织产物：一条主流程原型、三组独立页面原型、一份前端交互说明文档，以及一份前后端协议文档。主后端实现计划保留长期架构视角，本计划单独承接前端协作与评审材料，避免把大体量交互细节塞进主 spec。

**Tech Stack:** Prototype Toolkit (`prototypes/`), HTML/CSS/Vanilla JS, Markdown, TAPD story sync

**Spec:** `docs/specs/2026-04-20-sops-open-plugin-integration-design.md`

---

## File Structure

```text
Frontend collaboration artifacts
├── docs/plans/2026-04-20-sops-open-plugin-integration.md
│   └── 收敛主实现计划中的前端实现范围，改为引用前端交付包
├── docs/specs/2026-04-20-sops-open-plugin-frontend-interaction-design.md
│   └── 记录主流程、页面范围、状态覆盖、关键交互与增强态预留
├── docs/guide/sops_open_plugin_frontend_contract.md
│   └── 记录页面到接口映射、前端必需字段、状态枚举与展示规则
├── prototypes/output/sops-open-plugin-main-flow.html
│   └── 端到端主流程原型
├── prototypes/output/sops-open-plugin-space-open-plugin-management.html
│   └── 空间开放插件管理页原型
├── prototypes/output/sops-open-plugin-template-plugin-selection.html
│   └── 模板编辑中的插件选择与版本展示原型
└── prototypes/output/sops-open-plugin-task-plugin-error-state.html
    └── 任务页异常提示原型
```

**Files NOT changed:**
- `docs/specs/2026-04-20-sops-open-plugin-integration-design.md`
- `prototypes/base.html`
- `prototypes/assets/bkflow-prototype.css`
- `prototypes/assets/bkflow-prototype.js`

---

### Task 1: 收敛主计划边界并搭好交付文档骨架

**Files:**
- Modify: `docs/plans/2026-04-20-sops-open-plugin-integration.md`
- Create: `docs/specs/2026-04-20-sops-open-plugin-frontend-interaction-design.md`
- Create: `docs/guide/sops_open_plugin_frontend_contract.md`

- [ ] **Step 1: 复核主实现计划中与前端有关的段落**

检查：

- `File Structure` 中的前端代码文件
- 前端实现任务
- MVP/执行顺序里对前端代码实现的依赖

目标：确认哪些内容要从“前端代码实现”收敛成“前端协作交付包”。

- [ ] **Step 2: 修改主实现计划中的前端范围**

在 `docs/plans/2026-04-20-sops-open-plugin-integration.md` 中：

- 删除或收敛前端代码实现文件清单
- 将前端部分改为“消费原型、需求文档与协议文档”的协作边界
- 保持主计划仍然聚焦后端与跨仓协议能力

- [ ] **Step 3: 创建前端交互说明文档骨架**

在 `docs/specs/2026-04-20-sops-open-plugin-frontend-interaction-design.md` 先写出目录：

- 背景与目标
- 交付范围
- 主流程说明
- 页面原型清单
- 页面关键信息结构
- 页面状态覆盖
- 关键交互说明
- 后续增强态预留
- 非目标

- [ ] **Step 4: 创建前后端协议文档骨架**

在 `docs/guide/sops_open_plugin_frontend_contract.md` 先写出目录：

- 场景范围
- 页面到接口映射
- 核心展示实体
- 页面字段清单
- 状态枚举
- 展示规则
- 错误态与建议动作映射
- 跳转与回退规则
- 增强态预留字段

- [ ] **Step 5: Commit**

```bash
git add docs/plans/2026-04-20-sops-open-plugin-integration.md \
  docs/specs/2026-04-20-sops-open-plugin-frontend-interaction-design.md \
  docs/guide/sops_open_plugin_frontend_contract.md
git commit -m "docs(plan): 补充开放插件前端交付包计划 --story=133658573"
```

---

### Task 2: 产出主流程与空间开放插件管理页原型

**Files:**
- Create: `prototypes/output/sops-open-plugin-main-flow.html`
- Create: `prototypes/output/sops-open-plugin-space-open-plugin-management.html`

- [ ] **Step 1: 启动原型预览服务**

Run:

```bash
cd prototypes && python serve.py
```

Expected: 本地监听 `http://localhost:9080/`

- [ ] **Step 2: 阅读原型基线页面**

读取：

- `prototypes/base.html`
- `prototypes/examples/component-showcase.html`
- `prototypes/examples/list-page.html`
- `prototypes/examples/tab-page.html`

目标：对齐 BKFlow 现有原型风格和可用交互。

- [ ] **Step 3: 生成主流程原型**

在 `prototypes/output/sops-open-plugin-main-flow.html` 中至少覆盖：

- 空间管理员开放插件摘要
- 模板编辑选择插件与显式版本字段
- 任务页结构化错误卡片
- 一条主线和一条异常线说明

- [ ] **Step 4: 生成空间开放插件管理页原型**

在 `prototypes/output/sops-open-plugin-space-open-plugin-management.html` 中至少覆盖：

- 来源卡片 + 插件表格的混合布局
- 默认全部关闭态
- 部分开启态
- 来源不可用/插件下线提示
- 一键全开仅作用于当前已发现插件的提示

- [ ] **Step 5: 预览并记录需要微调的地方**

打开：

- `http://localhost:9080/output/sops-open-plugin-main-flow.html`
- `http://localhost:9080/output/sops-open-plugin-space-open-plugin-management.html`

检查：

- 资源引用无 404
- 页面布局与现有 BKFlow 风格一致
- 关键状态与说明已露出

- [ ] **Step 6: Commit**

```bash
git add prototypes/output/sops-open-plugin-main-flow.html \
  prototypes/output/sops-open-plugin-space-open-plugin-management.html
git commit -m "docs(prototype): 新增开放插件主流程与空间管理原型 --story=133658573"
```

---

### Task 3: 产出模板编辑与任务异常页原型

**Files:**
- Create: `prototypes/output/sops-open-plugin-template-plugin-selection.html`
- Create: `prototypes/output/sops-open-plugin-task-plugin-error-state.html`

- [ ] **Step 1: 复核页面状态清单**

按已确认设计整理最小状态：

- 模板编辑：正常态、单版本态、多版本态、版本不可用态、历史回看态
- 任务页：插件未开放、版本不可用、插件下线、来源不可达、历史只读解释态

- [ ] **Step 2: 生成模板编辑原型**

在 `prototypes/output/sops-open-plugin-template-plugin-selection.html` 中至少覆盖：

- 来源/分类/插件选择区
- 插件摘要区
- 显式 `plugin_version` 字段
- 当前版本不可用时的只读提示
- 参数配置区与版本切换提示

- [ ] **Step 3: 生成任务异常页原型**

在 `prototypes/output/sops-open-plugin-task-plugin-error-state.html` 中至少覆盖：

- 任务基础信息
- 结构化错误卡片
- 建议动作区
- 历史快照说明

- [ ] **Step 4: 预览并确认页面可串成一套体验**

打开：

- `http://localhost:9080/output/sops-open-plugin-template-plugin-selection.html`
- `http://localhost:9080/output/sops-open-plugin-task-plugin-error-state.html`

检查：

- 模板页的版本心智清晰
- 任务页只做解释与引导，不承载原地修复

- [ ] **Step 5: Commit**

```bash
git add prototypes/output/sops-open-plugin-template-plugin-selection.html \
  prototypes/output/sops-open-plugin-task-plugin-error-state.html
git commit -m "docs(prototype): 新增开放插件模板与任务页原型 --story=133658573"
```

---

### Task 4: 完成交互说明文档

**Files:**
- Modify: `docs/specs/2026-04-20-sops-open-plugin-frontend-interaction-design.md`

- [ ] **Step 1: 补充交付范围与主流程说明**

明确：

- 轻量交付包范围
- 主流程与三组独立页面原型
- MVP 与后续增强态都覆盖，但增强态不展开成复杂实施方案

- [ ] **Step 2: 按页面补充信息结构与状态覆盖**

分别写清：

- 空间开放插件管理页
- 模板编辑插件选择与版本展示页
- 任务页异常提示

每页都要包含：

- 页面目标
- 核心信息
- 核心操作
- 正常态/限制态/异常态/历史只读态

- [ ] **Step 3: 补充关键交互说明**

至少写清：

- 一键全开仅作用于当前已发现插件
- 版本字段显式展示
- 失效版本可回看、不可继续新用
- 任务页只提示和引导，不原地修复

- [ ] **Step 4: 自查文档是否与原型一致**

Run:

```bash
rg -n "一键全开|plugin_version|失效版本|任务页" docs/specs/2026-04-20-sops-open-plugin-frontend-interaction-design.md
```

Expected: 关键交互都已写入文档

- [ ] **Step 5: Commit**

```bash
git add docs/specs/2026-04-20-sops-open-plugin-frontend-interaction-design.md
git commit -m "docs(spec): 完成开放插件前端交互说明 --story=133658573"
```

---

### Task 5: 完成前后端协议文档并同步协作信息

**Files:**
- Modify: `docs/guide/sops_open_plugin_frontend_contract.md`

- [ ] **Step 1: 按页面整理接口映射**

分别列出：

- 空间开放插件管理页
- 模板编辑页
- 任务异常页

并说明每个页面需要：

- 哪些接口
- 哪些最小字段
- 哪些状态决定可编辑/只读/禁用

- [ ] **Step 2: 补充错误态与建议动作映射**

至少覆盖：

- 空间未开放
- 版本不可用
- 插件下线
- 来源不可达

明确前端看到这些状态时的展示和引导动作。

- [ ] **Step 3: 补充增强态预留字段**

明确哪些字段是一期先保留、后续增强时再消费，例如：

- 更细粒度错误原因
- 版本差异摘要
- 来源级状态说明

- [ ] **Step 4: 同步到 TAPD story**

将以下内容同步到 TAPD story `133658573`：

- 原型文件清单
- 交互说明文档摘要
- 协议文档摘要
- 预览方式或后续评审说明

建议通过评论分两条同步，避免单条评论过长。

- [ ] **Step 5: Commit**

```bash
git add docs/guide/sops_open_plugin_frontend_contract.md
git commit -m "docs(guide): 完成开放插件前后端协议文档 --story=133658573"
```

---

### Task 6: 统一验收与交付自查

**Files:**
- Modify: `docs/specs/2026-04-20-sops-open-plugin-frontend-interaction-design.md`
- Modify: `docs/guide/sops_open_plugin_frontend_contract.md`
- Modify: `prototypes/output/sops-open-plugin-main-flow.html`
- Modify: `prototypes/output/sops-open-plugin-space-open-plugin-management.html`
- Modify: `prototypes/output/sops-open-plugin-template-plugin-selection.html`
- Modify: `prototypes/output/sops-open-plugin-task-plugin-error-state.html`

- [ ] **Step 1: 逐页打开原型做可用性走查**

至少检查：

- 主流程是否能讲清端到端链路
- 3 组独立页面是否都覆盖关键状态
- 所有原型页面资源都可正常加载

- [ ] **Step 2: 核对文档与原型的一致性**

确保：

- 页面名称一致
- 状态名称一致
- `plugin_version`、来源别名、错误卡片心智一致

- [ ] **Step 3: 运行文档与原型最小校验**

Run:

```bash
git diff --check -- \
  docs/specs/2026-04-20-sops-open-plugin-frontend-interaction-design.md \
  docs/guide/sops_open_plugin_frontend_contract.md \
  prototypes/output/sops-open-plugin-main-flow.html \
  prototypes/output/sops-open-plugin-space-open-plugin-management.html \
  prototypes/output/sops-open-plugin-template-plugin-selection.html \
  prototypes/output/sops-open-plugin-task-plugin-error-state.html
```

Expected: 无空白/冲突类错误

- [ ] **Step 4: Commit**

```bash
git add docs/specs/2026-04-20-sops-open-plugin-frontend-interaction-design.md \
  docs/guide/sops_open_plugin_frontend_contract.md \
  prototypes/output/sops-open-plugin-main-flow.html \
  prototypes/output/sops-open-plugin-space-open-plugin-management.html \
  prototypes/output/sops-open-plugin-template-plugin-selection.html \
  prototypes/output/sops-open-plugin-task-plugin-error-state.html
git commit -m "docs(deliverables): 完成开放插件前端交付包 --story=133658573"
```

---

## Verification Checklist

- [ ] 主实现计划已收敛掉前端代码实现范围
- [ ] 主流程原型可讲清“治理 → 配置 → 任务结果”
- [ ] 空间开放插件管理页已覆盖默认关闭、部分开启、来源异常、插件下线
- [ ] 模板编辑原型已显式展示 `plugin_version`
- [ ] 任务页原型已覆盖结构化错误卡片与历史说明
- [ ] 交互说明文档与协议文档都覆盖 MVP + 后续增强态
- [ ] TAPD story `133658573` 已同步可评审内容

## MVP Cut

本计划中的 MVP 范围为：

- Task 1
- Task 2
- Task 3
- Task 4
- Task 5 的 `Step 1-4`

MVP 不额外展开：

- 额外增强态原型文件拆分
- 更细粒度字段差异稿
- 多轮 TAPD 评审往返整理

## Notes For Executor

- 原型遵循 `prototypes/base.html` 和 `prototypes/examples/` 的现有风格，不引入 Vue/构建流程。
- 这份计划产出的是前端协作交付物，不实现真实前端业务代码。
- 若某个增强态只需要轻量表达，优先在现有原型页面中补状态块，不急于拆新的 `-enhanced.html` 文件。
- 协议文档只保留前端必需字段与展示规则，不重复后端主 spec 的完整协议细节。
