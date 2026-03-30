---
name: prototype-generator
description: 独立的原型生成工具。用自然语言描述需求，AI 澄清后生成高保真可交互的 HTML 原型。触发条件："做个原型"、"设计页面"、"出个交互稿"、"prototype xxx"
---

# Prototype Generator（BKFlow 原型工具包）

## 工具介绍

本技能指导 AI 使用仓库根目录下的 **BKFlow Prototype Toolkit**（`prototypes/`）：纯 **HTML / CSS / Vanilla JS**，视觉风格对齐 **bk-magic-vue**，**零 Node / 零构建**。产出为可本地预览、可交互的静态 HTML 原型，适合产品与研发对齐页面结构与交互，不替代真实前端工程。

## 触发条件

当用户表达类似意图时使用本技能，例如：

- 「做个原型」「帮我画个页面」
- 「设计一下页面」「出个交互稿」
- 「prototype xxx」「用原型工具包生成 …」

> 本技能为**独立** Cursor Skill，不纳入 superpowers 计划执行流程；与 `ui-prototype` 等技能可并存，按用户意图选用。

## 完整工作流

1. **启动预览服务器**  
   - 检查是否已有 `prototypes/serve.py` 在运行（可查看 Cursor 的 **terminals** 状态或本机进程是否监听默认端口 **9080**）。  
   - 若未运行，在仓库根下执行：
     ```bash
     cd prototypes && python serve.py &
     ```
   - 默认地址：`http://localhost:9080/`（根目录即 `prototypes/`）。

2. **检查 `base.html`**  
   - 读取 `prototypes/base.html`。  
   - **若不存在**：进入「首次使用引导」（见下文），向用户确认后生成 `base.html`，保存到 `prototypes/base.html`，并让用户在浏览器中打开 `http://localhost:9080/base.html` 预览确认。

3. **需求澄清**（生成或大幅改版前必须完成，勿跳过）  
   逐项提问并记录答案，例如：  
   - 这个页面要展示什么信息？  
   - 有哪些数据字段？（表格列 / 表单字段）  
   - 需要哪些操作？（新建、编辑、删除、启用/停用等）  
   - 交互方式？（搜索、筛选、侧滑编辑、弹窗确认、Tab 切换等）  
   - 多个页面之间是否有关联、如何跳转？  
   - （可选）后端是否已有 Model / Serializer？若用户**主动提供**文件路径，可按「后端模型读取」一节做字段提取；否则仅凭描述推断。

4. **生成原型**  
   - 先阅读 `prototypes/examples/component-showcase.html`（组件与 class 参考）和当前 `prototypes/base.html`（外壳）。  
   - 复制 `base.html` 结构，在 `<main class="bk-content">` … `</main>` 内填充页面主体；**不要**把侧滑、弹窗等浮层塞进 `main` 内部（见「生成规则」）。  
   - 将完整 HTML 保存到 **`prototypes/output/<name>.html`**。  
   - **路径修正**：`base.html` 位于 `prototypes/` 根目录，资源用 `assets/...`；`output/` 下页面多一层目录，**必须**改为 `../assets/bkflow-prototype.css`、`../assets/bkflow-prototype.js` 及 `../assets/icons/...` 等。

5. **告知预览**  
   - 告诉用户打开：  
     `http://localhost:9080/output/<name>.html`

6. **迭代**  
   - 根据反馈修改；新版本命名为 `<name>-v2.html`、`<name>-v3.html` … 保留旧文件便于对比（与「版本管理」规则一致）。

## 生成规则（MUST）

- **先读** `prototypes/examples/component-showcase.html`，了解可用样式与结构模式。  
- **先读** `prototypes/base.html`，保持导航、布局与资源引用方式一致（再在 output 中做 `../assets/` 修正）。  
- **CSS class** 一律使用工具包约定的 **`bk-` 前缀**（见下方速查表）。  
- **交互** 仅通过 **`data-*` 属性** 声明，由 `assets/bkflow-prototype.js` 驱动；支持的属性与用法如下（实现以仓库内 JS 为准）：  

  | 属性 | 用法说明 |
  |------|----------|
  | `data-open="<id>"` | 点击打开对应 `id` 的侧滑（`.bk-sideslider`）或弹窗（`.bk-dialog`）；目标元素需带 `id` 且通过 `.is-show` 控制显示（脚本会添加该类）。 |
  | `data-close` | 点击后关闭最近的侧滑/弹窗；点击 `.bk-sideslider-mask` / `.bk-dialog-mask` 也会关闭。 |
  | `data-tab="<panelId>"` | 放在 `.bk-tab` 内的 `.bk-tab-item` 上；切换对应 `id` 的 `.bk-tab-panel` 可见性，并切换 `active` 样式。 |
  | `data-sortable` | 放在表头 `th` 上；点击按该列文本排序（中英文数字），并切换升序/降序指示类。 |
  | `data-filter="<tableId>"` | 放在输入框等元素上；`input` 时用输入值对 `id` 为 `tableId` 的表格 `tbody` 行做包含匹配过滤。 |
  | `data-collapse="<panelId>"` | 点击切换 `id` 对应元素的 `hidden` 状态。 |
  | `data-dropdown="<menuId>"` | 点击切换 `id` 对应下拉容器（如 `.bk-select-dropdown`）的 `is-show`。 |
  | `data-href="<url>"` | 点击后 `window.location.href` 跳转（如 `../output/other.html`）。 |
  | `data-notify="<msg>"` | 点击后顶部绿色 Toast 提示，约 2 秒消失。 |
  | `data-required` | 在表单控件上；提交 `.bk-form` 时若为空则给 `.bk-form-item` 加 `is-error` 并阻止提交。 |
  | `data-pattern="<regex>"` | 同上，用正则校验控件值。 |
  | `data-step="<panelId>"` | 在 `.bk-steps-container` 内切换 `.bk-step-panel` 的显示（`hidden`），用于步骤条/向导式布局。 |

- **Mock 数据** 应贴近真实业务语义（流程名、空间、任务状态等），避免「测试1」「aaa」「foo」等占位。  
- **版本文件**：`xxx.html` → `xxx-v2.html` → `xxx-v3.html`。  
- **浮层位置**：所有侧滑、弹窗等**必须**放在 `</main>` 之后、`</div>`（闭合 `.bk-layout`）之前或按 `base.html` 同级结构闭合前，且**在** `<script src="../assets/bkflow-prototype.js">` **之前**，保证 DOM 顺序清晰、与示例一致。

## 可用组件速查

| 类型 | 主要 class |
|------|------------|
| 按钮 | `.bk-button`, `.bk-button-primary`, `.bk-button-text`, `.bk-button-danger` 等 |
| 输入 | `.bk-input`, `.bk-textarea` |
| 表单 | `.bk-form`, `.bk-form-item` |
| 搜索框 | `.bk-search-input` |
| 开关 | `.bk-switcher`（点击切换 `is-checked`） |
| 下拉 | `.bk-select`, `.bk-select-trigger`, `.bk-select-dropdown`, `.bk-select-option` |
| 表格 | `.bk-table`, `.bk-pagination` |
| 标签页 | `.bk-tab`, `.bk-tab-item`, `.bk-tab-panel` |
| 标签 | `.bk-tag` |
| 弹窗 | `.bk-dialog`, `.bk-dialog-mask` |
| 侧滑 | `.bk-sideslider`, `.bk-sideslider-mask` |
| 面包屑 | `.bk-breadcrumb` |
| 加载 / 空状态 | `.bk-loading`, `.bk-exception` |
| 卡片 | `.bk-card` |
| 布局 / 工具栏 | `.bk-layout`, `.bk-toolbar`, `.bk-aside`, `.bk-split`, `.bk-info-card` |

## 可用交互速查

| 写法 | 作用 |
|------|------|
| `data-open="id"` | 打开侧滑/弹窗 |
| `data-close` | 关闭当前浮层 |
| `data-tab="id"` | Tab 切换 |
| `data-sortable` | 表头排序 |
| `data-filter="table-id"` | 输入过滤表格行 |
| `data-collapse="id"` | 折叠/展开 |
| `data-dropdown="id"` | 下拉展开/收起 |
| `data-href="page.html"` | 页面跳转 |
| `data-notify="msg"` | 通知提示 |
| `data-required` / `data-pattern` | 表单校验（需 `.bk-form` 提交） |
| `data-step="id"` | 步骤面板切换（需在 `.bk-steps-container` 内） |

## 后端模型读取（条件触发）

- **仅当用户明确提供**后端文件路径（如 Model、Config、Serializer）时执行。  
- 静态阅读源码：提取字段名、类型、`choices`、默认值等；**不**连接数据库、**不**执行 Django。  
- 粗略映射建议：`BooleanField` → `.bk-switcher`；`choices` → `.bk-select`；短文本 → `.bk-input`；长文本/JSON → `.bk-textarea`。  
- 若文件不存在或用户未提供路径，**跳过**本节，完全依据澄清结果推断字段与控件。

## 首次使用引导（条件触发）

当 **`prototypes/base.html` 不存在** 时：

1. 询问**产品/应用名称**（展示在侧栏或标题区域）。  
2. 询问**侧栏菜单模块列表**（文案与顺序）。  
3. 询问**主色调**（默认 `#3a84ff`，写入 `:root` 或内联样式覆盖 `--bk-primary` 若工具包支持）。  
4. 询问是否有 **logo**（路径或先用占位图；放入 `prototypes/assets/icons/` 或用户指定）。  
5. 按现有工具包结构生成 `prototypes/base.html`（引用 `assets/bkflow-prototype.css` / `assets/bkflow-prototype.js`，包含 `bk-layout`、`bk-navigation`、`main.bk-content` 空槽）。  
6. 请用户在 `http://localhost:9080/base.html` 预览确认后再进入页面级原型生成。

## 反模式（禁止）

- **不要**引入 Vue / React / Angular 等前端框架。  
- **不要**使用 Tailwind、Bootstrap 等**外部** CSS 框架或 CDN 大型 UI 库（仅用本工具包 `assets/`）。  
- **不要**在原型中编写真实 API 请求、鉴权或与后端对接的生产逻辑（可为按钮加 `data-notify` 等示意）。  
- **不要**跳过需求澄清直接生成页面。  
- **不要**在 `output/` 页面中继续使用 `assets/...` 而不加 `../`（会导致 404）。
