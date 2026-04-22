# BKFlow Engine Admin Prototype Overhaul Design

> 日期：2026-04-21
> 状态：Draft（方案已确认，已完成人工自审，待书面审阅）
> 目标：重构 `prototypes/` 为“页面类型母版库 + feature 跟进目录”模式，并基于真实 BKFlow 审计结果深度重建 `bkflow_engine_admin` 原型集合

## 1. 背景

当前 `prototypes/` 已能支撑快速生成静态 HTML 原型，但在这次 `bkflow_engine_admin` 原型对齐任务中暴露出三类结构性问题：

1. **目录不可管理**
   `examples/`、`output/`、`base.html` 混杂在同一层，`output/` 又是扁平目录，无法看出某个原型属于哪次需求，也无法表达页面之间的层级关系。
2. **原型基座过于通用**
   `prototypes/base.html` 更接近“单壳 + 简单列表”的演示页，而真实 BKFlow 页面存在显著差异：
   - 顶栏一级导航会整体切换信息架构
   - 页面会混用弹窗、侧滑、独立编辑页、执行详情页、接口调试页
   - 流程编辑页与任务详情页虽然都复用了流程画布，但交互语义完全不同
3. **缺少可持续演进机制**
   每次需求如果直接往 `output/` 堆页面，会导致“临时产物”和“长期母版”混在一起，难以沉淀真正可复用的页面标准。

同时，本次对 `stag` 环境的真实页面审计已经补齐了高复杂链路，包括：

- 流程创建
- 流程查看 / 编辑 / 发布
- 流程调试
- 调试任务执行详情
- 任务详情与流程编辑页的交互差异

审计文档位于：

- `.ai/docs/specs/bkflow-engine-admin-interaction-audit-2026-04-20.md`

这为 `prototypes/` 的重构提供了足够明确的对齐基线。

## 2. 设计目标

本次重构的核心目标如下：

1. **目录清晰**
   任何人第一次进入 `prototypes/`，都能立刻分清：
   - 通用母版在哪里
   - 某次需求的原型在哪里
   - 示例参考在哪里
2. **母版可沉淀**
   形成一组按页面类型组织的母版库，作为长期 `source of truth`。
3. **需求可追溯**
   每次需求都有自己的原型目录，并能显式关联到 `docs/specs/` 与 `docs/plans/`。
4. **页面做深做准**
   不只产出“长得像”的页面，而要把真实 BKFlow 的关键交互状态、容器模式、保存机制和执行态信息表达出来。
5. **支持持续演进**
   新需求可以在 feature 目录里快速落地，同时把通用能力回刷到母版库，而不会再次形成扁平堆积。

## 3. 非目标

本设计明确不做以下事情：

1. 不修改真实业务前端 `frontend/src/views/`。
2. 不把原型工具升级为完整低代码平台或页面搭建器。
3. 不在目录命名中强制携带 TAPD、工单号、负责人等管理信息。
4. 不要求历史所有原型一次性精修到统一标准；优先完成目录治理和主链路高精度重建。

## 4. 设计原则

### 4.1 母版优先

`prototypes/masters/` 是长期真源。  
需求目录允许落具体页面，但通用能力最终必须沉淀回母版。

### 4.2 页面类型优先于业务页面

母版按粗颗粒页面类型组织，而不是按具体业务功能一一复制。  
这样既能复用，也能保留不同业务页面之间的真实差异。

### 4.3 Feature 目录只承接单次需求

`prototypes/features/<slug>/` 只服务于某个需求或专题改造，承载：

- 成套页面入口
- 轻量 README
- 轻量变更记录

它不是长期母版库，不承担通用标准定义职责。

### 4.4 文档以 slug 建立绑定

`docs/specs/`、`docs/plans/` 和 `prototypes/features/` 使用同一个稳定 `slug` 关联，但只有 `docs/specs/` 与 `docs/plans/` 按项目规范带日期前缀。

### 4.5 对齐真实交互，而不是只对齐静态长相

原型需要表达的内容包括但不限于：

- 页面容器类型
- 路由语义
- 保存与发布状态机
- 只读与可编辑的边界
- 执行记录、日志、异常态

## 5. 方案选型

围绕 `prototypes/` 的新组织方式，评估三种方案：

| 方案 | 思路 | 优点 | 缺点 |
|------|------|------|------|
| **A. 页面类型母版库 + feature 跟进目录** | 母版按页面类型组织，需求单独建目录承接实际页面 | 目录清晰、可沉淀、最适合持续演进 | 首次重构量较大 |
| B. 需求目录优先 | 每次需求独立一套页面，再人工抽回母版 | 单次开发快 | 长期容易再次分叉 |
| C. 组件库优先 | 核心是组件展示，页面只是拼装示例 | 复用率高 | 不适合“所有页面做深做准”的目标 |

**最终选择方案 A。**

选择理由：

1. 能同时解决“目录扁平”和“页面难沉淀”两个问题。
2. 最适合本次任务里已经明确的高复杂页面差异。
3. 能兼容后续需求继续沿用同一套目录治理方式。

## 6. 新的目录结构

建议将 `prototypes/` 重构为：

```text
prototypes/
├── assets/
│   ├── bkflow-prototype.css
│   ├── bkflow-prototype.js
│   └── icons/
├── masters/
│   ├── _shared/
│   ├── overlays/
│   ├── list-page/
│   ├── config-page/
│   ├── flow-editor/
│   ├── task-detail/
│   ├── engine-panel/
│   └── decision-editor/
├── features/
│   ├── bkflow-engine-admin-prototype-overhaul/
│   └── _legacy/
├── examples/
│   ├── README.md
│   └── component-showcase.html
├── serve.py
└── README.md
```

### 6.1 各目录职责

| 路径 | 职责 |
|------|------|
| `assets/` | 共享样式、脚本、图标资源，首轮尽量原地保留 |
| `masters/` | 页面类型母版库，长期真源 |
| `features/` | 单次需求目录，承接成套原型 |
| `features/_legacy/` | 历史扁平原型的过渡归档区，仅迁移阶段存在 |
| `examples/` | 组件参考和最小演示，不再承载业务原型输出 |

## 7. 母版库设计

首批母版建议按以下 8 类组织：

### 7.1 `_shared/`

放共享壳子、导航骨架、通用布局片段，不作为对外页面展示。

它需要支持三套真实导航语义：

- `space`
- `system`
- `plugin`

### 7.2 `overlays/`

统一维护浮层模式：

- 确认弹窗
- 业务表单弹窗
- 只读内容弹窗
- 右侧侧滑

### 7.3 `list-page/`

承接中高频列表页，需覆盖：

- 顶部工具栏
- 搜索与筛选
- 固定操作列
- 状态列
- 空态
- 分页
- 危险操作确认

对应真实页面：

- 流程
- 调试任务
- 凭证管理
- 标签管理
- 系统空间配置
- 系统模块配置
- 插件列表

### 7.4 `config-page/`

承接长表单与代码编辑器型页面，需覆盖：

- 单页长滚动
- 代码编辑器区块
- 保存禁用态
- 修改后可保存
- 恢复默认值确认

对应真实页面：

- 空间配置

### 7.5 `flow-editor/`

高复杂度母版，需覆盖：

- 查看流程
- 编辑流程
- 版本徽标
- 画布编排
- 节点悬浮工具条
- 节点配置抽屉
- 全局变量浮层
- 两段式保存
- 发布弹窗
- 调试入口

### 7.6 `task-detail/`

高复杂度母版，需覆盖：

- 执行态页头
- 运行状态徽标
- 模板回链
- 只读画布
- 单击节点打开详情
- `执行记录 / 配置快照 / 操作历史 / 调用日志`
- 成功态 / 失败态 / 空日志态

### 7.7 `engine-panel/`

承接接口调试页，需覆盖：

- 请求区
- 响应区
- 禁用态发送按钮
- 重置按钮
- 参数区域

### 7.8 `decision-editor/`

承接决策表独立编辑页，需覆盖：

- 基础信息
- 规则配置
- 规则空态
- 底部操作区

## 8. Feature 目录设计

每次需求使用：

```text
prototypes/features/<slug>/
├── README.md
├── CHANGELOG.md
├── index.html
└── pages/
```

### 8.1 README 约束

`README.md` 至少包含：

- 对应 spec 路径
- 对应 plan 路径
- 本 feature 的目标
- 使用到的母版列表
- 页面入口清单

建议结构：

```md
# <feature title>

## Related Docs
- Spec: /docs/specs/YYYY-MM-DD-<slug>-design.md
- Plan: /docs/plans/YYYY-MM-DD-<slug>.md

## Purpose
...

## Master Pages Used
- /prototypes/masters/list-page/
- /prototypes/masters/flow-editor/

## Pages
- index.html
- pages/...
```

### 8.2 CHANGELOG 约束

`CHANGELOG.md` 只记录轻量里程碑，例如：

- 初始化需求目录
- 新增页面
- 回刷某类母版

不承担设计文档职责。

## 9. 首个 Feature：`bkflow-engine-admin-prototype-overhaul`

首个 feature 直接覆盖整个 `bkflow_engine_admin` 原型重建。

目录建议：

```text
prototypes/features/bkflow-engine-admin-prototype-overhaul/
├── README.md
├── CHANGELOG.md
├── index.html
└── pages/
    ├── space/
    ├── system/
    └── plugin/
```

### 9.1 页面清单

#### `pages/space/`

- `template-list.html`
- `flow-view.html`
- `flow-edit.html`
- `flow-debug.html`
- `task-list.html`
- `debug-task-list.html`
- `task-detail-complete.html`
- `task-detail-failed.html`
- `decision-list.html`
- `decision-editor.html`
- `space-config.html`
- `credential-list.html`
- `label-list.html`
- `statistics-exception.html`

#### `pages/system/`

- `space-config-list.html`
- `module-config-list.html`

#### `pages/plugin/`

- `plugin-list.html`

### 9.2 页面覆盖原则

这批页面需尽量和真实 BKFlow 审计结论一一对应，重点覆盖：

- 流程编辑页的深度交互
- 任务详情页的运行态信息
- 调试执行链路
- 列表页的真实操作组合
- 异常态与空态

## 10. 同步规则

### 10.1 母版优先

同步规则采用“母版优先”：

1. feature 页面落地前，先识别要用哪些母版。
2. 如果母版能力不足，先补母版。
3. 再基于更新后的母版生成 feature 页面。

### 10.2 Feature 不是长期真源

`features/<slug>/` 用于承接实际需求交付，但不作为长期页面标准定义来源。  
任何可复用结构最终都要回到 `masters/`。

### 10.3 examples 不参与同步

`examples/` 只用于说明原型工具如何用，不再承担业务页面演进职责。

## 11. 迁移策略

迁移按照“先立新结构，再迁旧内容，最后删旧目录”的顺序进行。

### 11.1 首轮保留

以下内容首轮尽量原地保留，降低风险：

- `assets/`
- `serve.py`
- `examples/component-showcase.html`

### 11.2 示例页迁移

| 旧文件 | 新去向 |
|--------|--------|
| `examples/list-page.html` | `masters/list-page/template.html` |
| `examples/flow-edit.html` | `masters/flow-editor/template.html` |
| `examples/task-detail.html` | `masters/task-detail/template.html` |
| `examples/form-slider.html` | `masters/overlays/sidesliders.html` |
| `examples/detail-page.html` | 拆分吸收或淘汰 |
| `examples/tab-page.html` | 拆分吸收或淘汰 |
| `examples/composite-page.html` | 拆分吸收或淘汰 |

### 11.3 历史 output 迁移

历史页面迁移规则：

- 有明确主题和延续价值的，迁入对应 `features/<slug>/`
- 暂时找不到明确归属的，迁入 `features/_legacy/<slug>/`

建议首批迁移：

- `output/sops-open-plugin-*.html` -> `features/sops-open-plugin/`
- `output/space-variable-manage.html` -> `features/space-variable-manage/`
- `output/node-output-viewer-proposal-v1.html` -> `features/node-output-viewer/`

## 12. 实施任务拆分

建议拆成 7 个任务顺序推进：

### Task 01：目录骨架重构

- 建立 `masters/`、`features/`、新 `examples/`
- 调整 `README.md`
- 迁移基础资源引用

### Task 02：共享壳子与浮层体系

- 建立 `_shared/`
- 建立 `overlays/`
- 抽出 `space / system / plugin` 三套导航骨架

### Task 03：中复杂度母版

- `list-page`
- `config-page`
- `engine-panel`
- `decision-editor`

### Task 04：流程编辑深度母版

- `flow-editor`
- 两段式保存
- 节点抽屉 / 全局变量 / 发布

### Task 05：任务详情深度母版

- `task-detail`
- 成功态 / 失败态
- 日志与快照视图

### Task 06：首个 feature 落地

- 完成 `bkflow-engine-admin-prototype-overhaul`
- 用母版拼出整套 `space / system / plugin` 页面

### Task 07：历史内容归档与清理

- 清理旧 `output/`
- 将历史原型归位到 `features/` 或 `_legacy/`
- 收口旧示例页职责

## 13. 完成标准

### 13.1 目录治理

- `prototypes/` 新结构落地
- 扁平 `output/` 不再作为主产出目录
- 任意 feature 目录都具备 `README.md`、`CHANGELOG.md`、`index.html`

### 13.2 母版能力

- 首批母版均可单独预览
- `flow-editor` 与 `task-detail` 明确分离
- 母版不是空骨架，而是带真实状态示例

### 13.3 首个 feature

- `features/bkflow-engine-admin-prototype-overhaul/` 能覆盖：
  - 空间管理
  - 系统管理
  - 我的插件
- 打开 `index.html` 能浏览整套原型

### 13.4 真实交互还原

- 流程编辑页必须覆盖：
  - 画布
  - 节点工具条
  - 配置抽屉
  - 全局变量
  - 两段式保存
  - 发布弹窗
- 任务详情页必须覆盖：
  - 执行态页头
  - 模板回链
  - 执行记录
  - 配置快照
  - 操作历史
  - 调用日志
- 调试执行链路必须体现：
  - Mock 数据配置
  - 执行前确认
  - 成功或异常态

## 14. 风险与约束

1. `运营统计` 在当前 `stag` 环境下未稳定渲染，因此首轮原型应保留异常态页面，不应伪造成正常列表页。
2. 调试执行链路在某些路径下会出现全局异常弹层，原型需要明确覆盖异常路径。
3. 当前工作区已有较多未归类历史文件，因此迁移过程中应避免一次性硬删，优先完成新结构落地后再清理旧目录。
