# BKFlow 原型工具 `bk-standard` 设计文档

> 日期：2026-04-10
> 状态：Draft（设计基线已确认，待书面评审）
> 目标：将 `prototypes/` 从纯静态 HTML 原型工具升级为以蓝鲸标准为主、动态引用 `@blueking/bkui-knowledge` 规范与模板资产的原型编排层

## 1. 背景

BKFlow 当前已经有一套可用的原型工具链：

- `prototypes/`：纯 HTML / CSS / Vanilla JS 的静态原型工具包，适合快速出稿和分享
- `.ai/skills/prototype-generator`：驱动 AI 基于上述工具包生成原型

这套方案解决了“零构建、快出稿”的问题，但也有明显边界：

- 页面视觉主要依赖本地复刻样式，而不是真实蓝鲸组件
- 蓝鲸规范的更新需要手工同步到本地 skill / 样式 / 模板
- 原型能做到“像蓝鲸”，但很难做到“直接跑出真实蓝鲸组件效果”
- 页面骨架和交互模式更接近 BKFlow 当前静态实现，难以持续向更新的蓝鲸标准收敛

与此同时，`@blueking/bkui-knowledge` 已经提供了一套可动态消费的蓝鲸前端知识能力：

- 组件 API
- 设计规范与反模式
- 页面模板与布局资产
- 真实预览模板
- MCP 工具接口与 skills 同步机制

BKFlow 本身处于蓝鲸生态内，且前端原型能力未来希望逐步走向更标准、更可复用的方向。因此新的原型工具主目标不再是“复刻当前项目页面”，而是：

1. 优先遵循蓝鲸标准
2. 尽量使用真实蓝鲸组件效果
3. 在此基础上保留 BKFlow 项目级覆盖能力

## 2. 设计目标

本次设计的核心目标如下：

- **蓝鲸标准优先**：原型生成时优先遵循 `bkui-knowledge` 中的设计规范，而不是仅复用组件 API
- **动态引用**：尽量不在本地 skill 中硬编码蓝鲸规范文本，包更新后原型工具应能自动吃到最新知识
- **真实组件效果**：默认输出真实 BK 组件预览，而不是仅靠本地 CSS 复刻
- **保留可降级能力**：当动态知识、真实预览或运行时不可用时，仍保留静态原型兜底
- **可追踪**：每个原型产物都能追溯其使用的蓝鲸知识版本、模板来源与降级原因

## 3. 非目标

本设计明确不做以下事情：

- 不把 `@blueking/bkui-knowledge` 当作业务运行时依赖直接嵌入 BKFlow 主前端工程
- 不把 `bkui-knowledge` 的 skill / reference / example 整体复制到仓库里长期维护
- 不要求第一版就支持任意复杂多路由原型应用
- 不把 BKFlow 当前 Vue2 + `bk-magic-vue` 的页面实现细节作为主设计来源

## 4. 方案选型

围绕新原型工具的主方向，评估了三条路线：

| 方案 | 思路 | 优点 | 缺点 |
|------|------|------|------|
| A. 静态增强 | 继续使用当前 HTML 工具，只在生成前动态查询 `bkui-knowledge` 约束输出 | 接入最轻，迁移最稳 | 只能“更像蓝鲸”，无法默认获得真实组件效果 |
| B. 完全替换为真实预览工程 | 放弃当前 `prototypes/` 静态能力，全面转向真实 BK 组件预览 | 保真度最高 | 迁移成本大，失去现有静态工具的兜底能力 |
| **C. 原型编排层 + `bk-standard` 主模式** | 保留 `prototypes/` 作为统一入口，新增 `bk-standard` 渲染器，静态原型降级为 fallback | 兼顾标准化、动态更新和降级能力 | 实现复杂度高于单一路线 |

**最终选择方案 C。**

选择理由：

1. 用户优先级已经明确为“尽量使用真实蓝鲸组件效果”
2. 项目长期目标是逐步走向蓝鲸更标准的页面结构与交互规范
3. 现有 `prototypes/` 已经能覆盖静态兜底场景，不应完全丢弃
4. `bkui-knowledge` 提供的是“知识服务 + 模板资产”，最适合作为新主模式的动态规范源

## 5. 总体架构

新的 `prototypes/` 不再等同于“纯静态 HTML 工具”，而是升级为一个**原型编排层**。其职责是：

- 解析用户原型意图
- 动态拉取蓝鲸知识
- 编译页面规范合同
- 选择合适的渲染器输出原型
- 校验原型是否符合蓝鲸规范
- 记录产物元数据

### 5.1 核心模块

| 模块 | 职责 |
|------|------|
| `intent-parser` | 将用户描述整理为页面意图：页面类型、关键任务、交互、保真等级 |
| `knowledge-adapter` | 动态读取 `bkui-knowledge` 的规范、组件 API、模板与示例 |
| `contract-compiler` | 将知识与项目覆盖项编译成结构化 `prototype contract` |
| `bk-standard-renderer` | 按合同生成蓝鲸标准原型，默认输出真实 BK 组件预览 |
| `validator` | 校验知识加载、合同完整性、渲染结果和规范一致性 |
| `artifact-recorder` | 为产物记录版本、知识来源、模板来源和降级原因 |

### 5.2 数据流

```text
用户需求
  -> intent-parser
  -> knowledge-adapter
  -> contract-compiler
  -> bk-standard-renderer
  -> validator
  -> output + metadata
```

### 5.3 主模式与降级模式

新的原型工具保留多个输出模式，但主模式固定为：

- **主模式：`bk-standard`**
  - 蓝鲸标准优先
  - 真实 BK 组件预览优先
  - 动态引用 `bkui-knowledge`
- **降级模式：`static-fallback`**
  - 保留当前 `bkflow-prototype.css/js` 静态能力
  - 仅作为最后一级兜底

## 6. 动态知识接入

### 6.1 核心原则

`bkui-knowledge` 在本设计中不是“组件素材包”，而是**动态规范源**。原型工具必须同时消费：

- 设计规范
- 组件契约
- 模板资产
- 参考示例

### 6.2 知识分层

`knowledge-adapter` 应按以下层次消费 `bkui-knowledge`：

1. **设计规范层**
   - 来源：`bkui-builder`、`bkui-cheatsheet`、`bkui-quick-start`、`bkui-demo`
   - 用途：约束页面骨架、布局结构、组件组合、常见反模式
2. **组件契约层**
   - 来源：`knowledge/component-apis/vue3/*.json`
   - 用途：校验组件 Props / Events / Slots / 使用禁忌
3. **参考实现层**
   - 来源：`knowledge/examples/`、`bkui-builder/assets/layouts/`、`bkui-builder/assets/pages/`、`bkui-demo/assets/`
   - 用途：为列表页、详情页、向导页等页面选择标准骨架与预览模板
4. **项目覆盖层**
   - 来源：BKFlow 本地配置
   - 用途：补充项目名称、模块文案、少量视觉 token、状态语义等轻量覆盖

### 6.3 接入优先级

动态引用应采用固定优先级，避免将上游内容写死到本地 skill 中：

1. **MCP 主通道**
   - 优先调用稳定工具接口：
     - `get_knowledge_index`
     - `recommend_skills`
     - `get_skill`
     - `get_component_api`
     - `batch_load`
2. **npm fallback 通道**
   - 当 MCP 不可用时，临时拉取并解析 `@blueking/bkui-knowledge`
   - 读取 `knowledge/manifest.json`、skill 目录、组件 API、模板和示例
3. **本地缓存通道**
   - 使用最近一次成功解析的版本
4. **静态兜底通道**
   - 真实标准链路无法建立时，退回 `static-fallback`

### 6.4 版本策略

为兼顾“动态更新”和“可回退、可复现”，建议采用以下策略：

- 默认跟随 `@blueking/bkui-knowledge` 当前可用版本
- 每次生成原型时记录实际使用的知识版本
- 本地缓存最近一次成功解析的版本
- 新版本解析失败时，自动回退到最近成功版本
- 提供显式刷新能力，用于手动强制更新知识缓存

## 7. `prototype contract`

### 7.1 角色

`prototype contract` 是新工具链的稳定中间层。后续的 renderer 和 validator 只依赖 contract，而不直接依赖上游 markdown 文本或本地 prompt。

### 7.2 最小结构

建议 contract 至少包含以下字段：

```json
{
  "mode": "bk-standard",
  "layout_pattern": "table-page",
  "preview_strategy": "preview-html",
  "component_plan": ["navigation", "table", "pagination", "form", "dialog"],
  "design_rules": [],
  "anti_patterns": [],
  "project_overrides": {},
  "fallback_policy": {
    "allow_static_fallback": true
  },
  "knowledge_context": {
    "version": "0.0.1-beta.32",
    "skills": ["bkui-builder", "bkui-cheatsheet", "bkui-quick-start", "bkui-demo"],
    "components": ["navigation", "table", "pagination", "dialog"]
  }
}
```

### 7.3 编译规则

`contract-compiler` 需要在生成前强制补齐以下信息：

- 页面骨架：列表页、详情页、向导页、工作台页等
- 布局约束：导航、筛选区、表格区、详情区、弹层区如何组织
- 组件计划：优先使用哪些 BK 组件
- 反模式：明确禁止出现的布局或组件组合
- 预览策略：`preview-html` 或 `preview-app`
- 项目覆盖项：BKFlow 本地命名与轻量品牌化信息

若 contract 缺失上述关键字段，则不允许进入最终渲染。

## 8. `bk-standard` 渲染器

### 8.1 默认输出形态

`bk-standard` 应优先输出**真实 BK 组件预览页**，而不是仅由本地 CSS 复刻。

默认形态为：

- **`preview-html`**
  - 生成可直接打开的独立预览 HTML
  - 页面中的组件应来自真实 BK 组件运行时
  - 预览外壳优先复用 `bkui-demo` 模板资产

复杂场景可扩展：

- **`preview-app`**
  - 用于跨页流程较多或需要更完整状态管理的场景
  - 第一版不作为默认路径

### 8.2 模板与页面骨架来源

`bk-standard-renderer` 不应再以当前 `prototypes/base.html` 作为标准主壳，而应优先消费上游模板资产：

- 布局骨架：`bkui-builder/assets/layouts/`
- 页面模板：`bkui-builder/assets/pages/`
- 预览模板：`bkui-demo/assets/preview-template*.html`
- 视觉映射：`bkui-builder/references/visual-mapping.md`

生成策略应为：

1. 先判断页面属于何种模式，例如 `table-page`、`detail-page`、`wizard-form`
2. 再选择最接近的蓝鲸标准骨架
3. 最后注入字段、操作、文案与 mock 数据

### 8.3 BKFlow 项目覆盖

BKFlow 当前项目不再提供“主渲染模式”，而只作为 `project-overrides` 输入层，补充：

- 模块名与菜单命名
- 常见业务状态文案
- 导航分组习惯
- 少量项目级 token 与语义配置

设计优先级应固定为：

`运行时可实现性 > 蓝鲸组件硬约束 > 蓝鲸设计规范 > BKFlow 项目覆盖 > 本地默认值`

## 9. 目录职责调整

建议将 `prototypes/` 重构为如下职责：

```text
prototypes/
├── renderers/
│   ├── bk-standard/
│   └── static-fallback/
├── cache/
│   └── bkui-knowledge/
├── output/
│   └── ...
├── metadata/
│   └── ...
├── assets/                         # 仅服务 static-fallback
├── base.html                       # 降级为 legacy fallback 壳
└── serve.py
```

其中：

- `assets/`、`base.html` 继续保留，但只服务 `static-fallback`
- 标准模式的壳子与页面骨架主要由 `bkui-knowledge` 动态提供

## 10. 校验与回退机制

### 10.1 四层校验

新工具链至少需要四层校验：

1. **知识解析校验**
   - 是否成功加载关键 skills、组件 API、模板资产
2. **合同完整性校验**
   - `prototype contract` 是否完整且可执行
3. **渲染结果校验**
   - 是否真的生成了目标 BK 组件预览，而非静态伪装
4. **规范一致性校验**
   - 是否违反 `bkui-builder` / `bkui-cheatsheet` / `bkui-quick-start` 中的强规范与反模式

### 10.2 回退顺序

发生异常时应按固定顺序回退：

1. `bk-standard / MCP 实时读取`
2. `bk-standard / 本地缓存版本`
3. `bk-standard / npm fallback`
4. `static-fallback`

任何降级都必须被记录，且不允许在无标记情况下静默退回手写 DOM。

## 11. 产物元数据

为保证动态知识链路的可追踪性，建议每个产物都附带一份元数据，至少记录：

- 本次使用的 `bkui-knowledge` 版本
- 实际加载的 skills 列表
- 实际加载的组件 API 列表
- 选中的布局模板与预览模板
- 项目覆盖项
- 是否发生降级
- 降级原因

元数据是内部工具链资产，不要求直接展示给最终评审者，但必须可供后续排查与复现。

## 12. 迁移策略

建议采用渐进迁移，而不是一次性推翻当前工具：

### Phase 1：建立标准主链路

- 引入 `knowledge-adapter`
- 建立 `prototype contract`
- 实现 `bk-standard` 的 `preview-html`
- 跑通 `MCP -> fallback -> cache` 读取链路

### Phase 2：加入规则校验与元数据

- 增加知识加载校验
- 增加规范一致性校验
- 记录产物元数据

### Phase 3：静态链路收口

- 将现有 `assets/`、`base.html` 明确降级为 `static-fallback`
- 调整 `prototype-generator` skill，使其默认进入 `bk-standard`

### Phase 4：复杂场景增强

- 支持 `preview-app`
- 增加更复杂的多页面、流程类原型能力

## 13. 最终结论

本设计确认以下基线：

1. `prototypes/` 将升级为原型编排层，而不再只是纯静态 HTML 工具
2. 新的主模式为 `bk-standard`
3. `bk-standard` 默认输出真实 BK 组件预览页
4. `@blueking/bkui-knowledge` 是动态规范源，重点消费设计规范、组件契约和模板资产
5. 原型生成必须先形成 `prototype contract`，再进入渲染
6. `static-fallback` 保留，但仅作为最后一级兜底
7. BKFlow 项目元素通过 `project-overrides` 注入，而不再主导页面骨架
8. 每次生成都必须经过校验，并记录来源元数据

这套方案的核心价值，不是简单“把旧原型工具接上一个新包”，而是将原型能力从“本地静态复刻”升级为“可动态追随蓝鲸规范演进的标准化原型系统”。
