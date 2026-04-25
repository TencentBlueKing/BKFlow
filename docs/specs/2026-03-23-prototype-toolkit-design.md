# BKFlow 原型工具包设计文档

> **日期**：2026-03-23
> **状态**：Reviewed
> **目标**：构建一套零配置、AI 驱动的原型生成工具，让后端开发者能快速产出高保真可交互的 HTML 原型

## 1. 背景与动机

BKFlow 的前端基于 Vue 2.7 + bk-magic-vue + Webpack 构建，搭建开发环境需要 Node.js、npm install、后端 API 等一系列依赖。对于不熟悉前端的后端开发者，仅仅为了产出原型就搭建完整前端环境成本过高，且很多页面交互依赖真实后端接口。

我们需要一套独立的原型工具，满足以下核心需求：

- **零配置**：不需要 Node.js、npm、webpack，不依赖任何后端接口
- **AI 驱动**：用自然语言描述需求，AI 澄清后自动生成可交互原型
- **高保真**：视觉上贴近 bkflow 现有页面风格（bk-magic-vue 组件外观）
- **可交互**：Tab 切换、侧滑打开/关闭、弹窗、搜索过滤等原型级交互可用
- **易分享**：产出的原型能直接给产品/设计在浏览器中查看和体验

## 2. 方案选型

评估了三种方案：

| 方案 | 思路 | 优点 | 缺点 |
|------|------|------|------|
| **A. 纯 HTML 原型工具包** | CSS 设计系统 + Vanilla JS 交互库 | 零依赖、AI 生成最可靠、离线可用 | 复杂交互需额外 JS |
| B. CDN Vue 3 + 组件库 | 通过 CDN 加载 Vue 3 运行时 | 交互能力强 | AI 生成易出错、需联网或下载运行时 |
| C. Python Flask 服务器 | Flask + Jinja2 模板渲染 | Python 原生技术栈 | 架构偏重、前端交互仍需 JS |

**选择方案 A**，理由：
1. 对 AI 生成最友好——纯 HTML/CSS 结构简单，出错率最低
2. 真正零依赖——只需 Python 标准库起 HTTP 服务
3. 可渐进增强——未来需要更复杂交互时可引入 Vue 3 CDN，不冲突

## 3. 整体架构

工具包放在仓库根目录下 `bkflow-prototype/`，与 `bkflow/`、`frontend/` 并列：

```
bk-flow/                              ← 仓库根目录
├── bkflow/                           ← 后端代码
├── frontend/                         ← 前端代码
├── prototypes/                       ← 原型工具包（本文档的产物）
└── ...

prototypes/                           ← 原型工具包根目录
├── assets/                           ← 静态资源
│   ├── bkflow-prototype.css          ← CSS 设计系统（复刻 bk-magic-vue 60+ 组件）
│   ├── bkflow-prototype.js           ← 声明式交互库
│   └── icons/                        ← SVG 图标集
├── base.html                        ← 预制的 bkflow 应用外壳（导航栏+菜单+空内容区）
├── examples/                         ← 常见页面模式示例（参考用，不做约束）
│   ├── list-page.html                ← 示例：列表页
│   ├── form-slider.html              ← 示例：侧滑表单
│   ├── tab-page.html                 ← 示例：Tab 切换
│   ├── detail-page.html              ← 示例：详情页
│   ├── composite-page.html           ← 示例：复合布局
│   └── component-showcase.html       ← 全组件展示页（样式参考）
├── output/                           ← AI 生成的原型存放处
│   └── (*.html)
├── serve.py                          ← 预览服务器（零依赖 Python）
└── README.md                         ← 使用说明
```

五个核心模块：

| 模块 | 职责 |
|------|------|
| **CSS 设计系统** (`bkflow-prototype.css`) | 复刻 bk-magic-vue 全部组件的视觉外观，通过 CSS class 使用 |
| **JS 交互库** (`bkflow-prototype.js`) | 提供声明式交互能力，通过 HTML data-* 属性驱动 |
| **示例文件** (`examples/`) | 常见页面模式的示例，供 AI 学习参考，不限制生成结果 |
| **预览服务器** (`serve.py`) | 零依赖 Python HTTP 服务，支持自动刷新 |
| **AI Skill** (`.ai/skills/prototype-generator/SKILL.md`) | 独立的 Cursor skill，定义 AI 如何使用工具包生成原型。与现有 `ui-prototype` skill 并存 |

## 4. CSS 设计系统

### 4.1 设计变量

从 bkflow 前端代码（`frontend/src/scss/config.scss`、`app.scss`）提取，确保配色完全一致：

```css
:root {
  /* 主色调 */
  --bk-primary: #3a84ff;
  --bk-success: #2dcb56;
  --bk-warning: #f8b53f;
  --bk-danger: #ff5757;

  /* 文本 */
  --bk-text-primary: #333333;
  --bk-text-secondary: #666666;
  --bk-text-tertiary: #999999;
  --bk-text-disabled: #cfcccc;

  /* 背景 */
  --bk-bg-default: #ffffff;
  --bk-bg-main: #f5f5f5;
  --bk-bg-body: #f4f7fa;
  --bk-bg-hover: #edf4fd;
  --bk-bg-nav: #f0f7ff;

  /* 边框 */
  --bk-border: #dcdee5;
  --bk-border-form: #c3cdd7;
  --bk-border-light: #ebebeb;

  /* 圆角 */
  --bk-radius: 2px;
  --bk-radius-md: 4px;
  --bk-radius-lg: 6px;

  /* 阴影 */
  --bk-shadow: 0 0 5px 0 rgba(0, 0, 0, 0.09);
  --bk-shadow-lg: 0 0 20px 0 rgba(0, 0, 0, 0.15);

  /* 字体 */
  --bk-font: 'Microsoft YaHei', 'PingFang SC', 'Hiragino Sans GB', sans-serif;
  --bk-font-size: 14px;
  --bk-font-size-sm: 12px;
  --bk-font-size-lg: 16px;
  --bk-font-size-xl: 20px;

  /* 布局 */
  --bk-header-height: 48px;
  --bk-nav-bg: #1f2738;
  --bk-min-width: 1366px;
}
```

### 4.2 组件覆盖范围

完整覆盖 bk-magic-vue 2.5 全部组件 + 3 个 bkflow 特有组件。**以下方 Phase 表为唯一完整清单**，本节按分类列出便于查阅。

CSS class 命名与 bk-magic-vue 组件名保持一致，使用 `bk-` 前缀。

#### 基础 (6)
Color、Icon、Button、Link、Transition、Font

#### 布局 (2)
Grid、ResizeLayout

#### 导航 (9)
Navigation、Tab、Steps、Process、Breadcrumb、Divider、FixedNavbar、BackTop、Affix

#### 表单 (16)
Form/FormItem、Input、Radio、Checkbox、Select、Cascade、Switcher、ColorPicker、DatePicker、TimePicker、TagInput、Upload、Search、Slider、Transfer、Rate

#### 数据展示 (16)
Table、Pagination、Tag、Badge、Tree、BigTree、Collapse、DropdownMenu、Timeline、Progress、RoundProgress、Swiper、AnimateNumber、Diff、VirtualScroll、Image

#### 反馈 (12)
Dialog、Sideslider、Loading、Alert、Exception、Message、Notify、Popover、Popconfirm、Tooltips、Card、Spin

#### BKFlow 特有 (3)
FlowNode（流程节点静态展示）、FlowConnection（节点连线）、CodeEditor（代码编辑器占位）

### 4.3 分 Phase 实现

| Phase | 组件 | 数量 | 说明 |
|-------|------|------|------|
| Phase 1 | Button、Input、Select、Switcher、Form/FormItem、Table、Pagination、Tab、Dialog、Sideslider、Search、Tag、Breadcrumb、Loading、Exception、Navigation、Grid、Card | 18 | 核心骨架，完成即可出原型 |
| Phase 2 | Radio、Checkbox、DatePicker、TimePicker、TagInput、Upload、Cascade、ColorPicker、Slider、Transfer、Rate | 11 | 表单增强 |
| Phase 3 | Tree、BigTree、Collapse、DropdownMenu、Timeline、Progress、RoundProgress、Badge、Alert、Message、Notify、Popover、Popconfirm、Tooltips | 14 | 数据展示 + 反馈 |
| Phase 4 | Steps、Process、ResizeLayout、Divider、FixedNavbar、BackTop、Affix、Swiper、AnimateNumber、Diff、VirtualScroll、Image、Spin、Icon、Color、Font、Link、Transition、FlowNode、FlowConnection、CodeEditor | 21 | 导航 + 基础补全 + 高级 + bkflow 特有 |

> **合计 64 个组件**：Phase 1 (18) + Phase 2 (11) + Phase 3 (14) + Phase 4 (21) = 64

## 5. JS 交互库

### 5.1 设计原则

**声明式交互**：通过 HTML `data-*` 属性声明交互行为，生成原型时无需编写任何 JavaScript 代码。`bkflow-prototype.js` 在页面加载时自动扫描这些属性并绑定事件。

### 5.2 支持的交互

| 交互 | HTML 属性 | 效果 |
|------|-----------|------|
| 打开侧滑/弹窗 | `data-open="target-id"` | 打开 id 对应的侧滑面板或弹窗 |
| 关闭浮层 | `data-close` | 关闭当前所在的侧滑/弹窗 |
| Tab 切换 | `data-tab="panel-id"` | 切换显示对应 Tab 面板 |
| 表头排序 | `data-sortable` | 点击表头列排序（切换升序/降序） |
| 搜索过滤 | `data-filter="table-id"` | 输入时实时过滤指定表格的行 |
| 折叠展开 | `data-collapse="panel-id"` | 折叠/展开指定面板 |
| 下拉菜单 | `data-dropdown="menu-id"` | 展开/收起下拉菜单 |
| 表单校验提示 | `data-required` / `data-pattern="regex"` | 提交时显示校验错误样式 |
| 步骤切换 | `data-step="step-id"` | 点击进入下一步/上一步 |
| 页面跳转 | `data-href="other-page.html"` | 原型间页面跳转 |
| 通知消息 | `data-notify="成功信息"` | 点击后弹出通知提示 |

### 5.3 用法示例

```html
<!-- 点击按钮打开侧滑 -->
<button class="bk-button bk-button-primary" data-open="create-slider">
  新建
</button>

<!-- 侧滑面板 -->
<div id="create-slider" class="bk-sideslider">
  <div class="bk-sideslider-header">
    <span>新建凭证</span>
    <span class="bk-sideslider-close" data-close>&times;</span>
  </div>
  <div class="bk-sideslider-body">
    <!-- 表单内容 -->
  </div>
  <div class="bk-sideslider-footer">
    <button class="bk-button" data-close>取消</button>
    <button class="bk-button bk-button-primary" data-close data-notify="创建成功">提交</button>
  </div>
</div>
```

## 6. 布局原语

不使用固定页面模板，而是提供一组可自由组合的布局原语。AI 根据具体需求即时构造最合适的页面结构。

| 布局原语 | CSS class | 说明 |
|----------|-----------|------|
| 页面骨架 | `bk-layout` | 导航 + 侧边栏 + 内容区 |
| 操作栏 | `bk-toolbar` | 搜索 + 筛选 + 操作按钮的水平容器 |
| 数据表格区 | `bk-table` + `bk-pagination` | 表格 + 分页组合 |
| 侧边面板 | `bk-aside` | 可放树形导航或分组列表 |
| 侧滑层 | `bk-sideslider` | 从右侧滑出的面板 |
| 弹窗层 | `bk-dialog` | 居中弹窗 |
| Tab 容器 | `bk-tab` | 可嵌套任意内容的标签页 |
| 表单区 | `bk-form` | 字段组 + 校验 |
| 信息卡片区 | `bk-info-card` | KV 键值对展示 |
| 步骤容器 | `bk-steps-container` | 分步表单 / 向导 |
| 画布区 | `bk-canvas` | 流程图静态展示 |
| 分栏布局 | `bk-split` | 左右或上下分栏 |

这些原语可以自由嵌套组合，例如：
- 左侧树 + 右侧（操作栏 + 表格 + 侧滑表单）
- 步骤容器里嵌套三个表单区
- Tab 容器内每个面板是独立的列表页

`examples/` 目录下的示例文件展示常见组合模式，供 AI 生成时参考学习，但不限制生成结果。

## 7. 预览服务器

### 7.1 技术实现

`serve.py` 是一个零依赖的 Python 脚本，仅使用标准库 (`http.server`)。

功能：
- **静态文件服务**：服务 `prototypes/` 目录下的所有文件
- **自动刷新**：向 HTML 响应中注入一小段 JS，每 1 秒轮询服务端 `/api/mtime` 端点检测文件变化，变化时自动刷新浏览器
- **原型索引页**：访问根路径 `/` 时展示 `output/` 下所有原型的列表页，点击即可进入
- **端口可配**：`python serve.py --port 9080`，默认 9080

### 7.2 使用方式

```bash
cd prototypes
python serve.py
# ✓ Serving prototypes at http://localhost:9080
# ✓ Auto-reload enabled
```

如果通过 SSH 远程开发，需要做端口转发：
```bash
ssh -L 9080:localhost:9080 your-devcloud-host
```

## 8. AI Skill：prototype-generator

### 8.1 定位

这是一个**独立的 Cursor skill**，存放在 `.ai/skills/prototype-generator/SKILL.md`。它不属于 superpowers 研发流程，不会链接到 writing-plans、TDD 等其他 skill。它自己完成从需求澄清到原型生成的全流程。

与现有的 `.ai/skills/ui-prototype/SKILL.md`（面向前端开发者，在 Vue 代码中迭代）并存，各有各的适用场景：

| Skill | 适用场景 | 产出物 | 依赖 |
|-------|---------|--------|------|
| `ui-prototype` | 前端开发者在真实代码中迭代 UI | Vue 组件 | Node.js + 前端环境 |
| `prototype-generator` | 后端开发者/产品经理快速出原型 | 自包含 HTML 文件 | 仅 Python |

### 8.2 触发条件

用户说以下类似的话时触发：
- "做一个 xxx 的原型"
- "设计一下 xxx 页面"
- "帮我出一个 xxx 的交互稿"
- "prototype xxx"

### 8.3 完整工作流

Skill 自身包含完整的工作循环，不依赖外部 skill：

1. **启动预览服务器** — 检查 `serve.py` 是否已在运行，没有则启动
2. **检查外壳** — 检查 `base.html` 是否存在，不存在则进入外壳构建引导（见 8.5）
3. **需求澄清** — 逐一提问确认：
   - 页面要展示什么信息？有哪些数据字段？
   - 需要什么操作？新建、编辑、删除、启用/停用？
   - 交互方式？搜索、筛选、侧滑编辑、弹窗确认？
   - 多个页面之间有关联吗？
   - （可选）用户显式提供后端文件路径时，读取 Model/Config/Serializer 提取字段
4. **生成原型** — 复制 `base.html` 作为基础，在其内容区（`<main class="bk-content">`）中填充具体页面内容，保存到 `output/`
5. **告知用户预览** — 给出预览 URL
6. **迭代循环** — 用户反馈 → AI 增量修改 → 生成新版本文件（`xxx-v2.html`）→ 再预览 → 循环直到满意

### 8.4 AI Skill 能力

| 能力 | 说明 |
|------|------|
| 需求澄清 | 逐一提问确认页面类型、字段、操作、交互 |
| 布局组合 | 根据需求自由组合布局原语，不限于固定模板 |
| 生成原型 | 复制 `base.html` 外壳，在内容区填充具体页面内容（布局原语 + 组件 + Mock 数据 + 声明式交互） |
| 多页面关联 | 支持生成多个关联页面（如列表页 + 编辑侧滑），页面间可跳转 |
| 读取后端模型 | 用户显式提供后端文件路径时，读取 `bkflow/` 下的 Model/Config/Serializer，提取字段名、类型、choices、默认值，输出字段-控件映射表。不连接真实数据库或后端服务，仅做静态代码分析。如果后端代码不存在则跳过，基于用户描述推断字段 |
| 增量迭代 | 只改反馈提到的部分。版本历史通过文件名后缀管理：`plugin-management.html`（初版）→ `plugin-management-v2.html` → `plugin-management-v3.html`，旧版本保留在 `output/` 目录中供回溯 |
| 全组件参考 | 读取 `component-showcase.html` 了解所有可用组件的 class 写法 |

### 8.5 页面外壳 (`base.html`)

`base.html` 是预先打磨好的应用外壳，包含：
- 顶部导航栏（产品 logo、产品名、用户头像）
- 左侧菜单（各功能模块菜单项，可点击高亮）
- 空的内容区（`<main class="bk-content"></main>` 占位）
- CSS/JS 引用

外壳打磨一次，确保高保真。AI 生成原型时**只负责填充内容区**。

**首次使用引导**：当 `base.html` 不存在时（如另一个项目首次使用此工具），skill 进入外壳构建引导流程：

1. 询问产品名称（显示在导航栏）
2. 询问左侧菜单有哪些模块
3. 询问主色调（默认蓝鲸蓝 `#3a84ff`，如需自定义可修改 CSS 变量）
4. 询问是否有 logo 图片（可选，放入 `assets/icons/`）
5. 生成 `base.html` → 用户在浏览器预览确认
6. 确认后回到正常的原型生成流程

对于 bkflow 项目，`base.html` 会随工具包一起预制好，不需要走引导流程。

### 8.6 生成的 HTML 文件结构

以 `base.html` 为基础，AI 填充 `bk-content` 区域：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>插件管理 - BKFlow 原型</title>
  <link rel="stylesheet" href="../assets/bkflow-prototype.css">
</head>
<body>
  <div class="bk-layout">
    <!-- ↓ 以下来自 base.html，AI 不需要生成 ↓ -->
    <nav class="bk-navigation">
      <div class="bk-navigation-header">BKFlow</div>
      <ul class="bk-navigation-menu">
        <li class="active">插件管理</li>
        <li>模板管理</li>
        <li>任务管理</li>
        ...
      </ul>
    </nav>
    <!-- ↑ 外壳部分结束 ↑ -->

    <main class="bk-content">
      <!-- ↓ AI 只生成这里面的内容 ↓ -->
      <div class="bk-toolbar">...</div>
      <div class="bk-table">...</div>
      <!-- ↑ AI 生成的内容结束 ↑ -->
    </main>
  </div>
  <!-- 侧滑/弹窗等浮层放在 body 末尾 -->
  <script src="../assets/bkflow-prototype.js"></script>
</body>
</html>
```

关键约束：
- CSS class 使用 `bk-` 前缀，与 bk-magic-vue 组件名一致
- 交互通过 `data-*` 属性声明
- Mock 数据直接写在 HTML 中，使用接近真实业务的数据
- 每个原型是自包含的 HTML 文件，只依赖 `assets/` 下的共享资源
- **原型文件仅允许扁平存放在 `output/` 一级目录下**（即 `prototypes/output/<name>.html`），不允许子目录嵌套。静态资源统一用 `../assets/` 相对路径引用，`serve.py` 以 `prototypes/` 为根目录服务

## 9. 扩展性：bk-magic-vue 版本兼容

当前实现目标是 bk-magic-vue 2.x，但蓝鲸生态内有些产品使用 bk-magic-vue 3.x（bkui-vue3），两个版本在配色、圆角、阴影、部分组件结构上有差异。设计上预留以下扩展能力：

### 9.1 CSS 变量集中管理

所有组件样式必须引用 CSS 变量，不允许在组件 class 中写死颜色、尺寸等值。这样切换 v2/v3 只需替换变量层。

```css
/* ✅ 正确：引用变量 */
.bk-button { border-radius: var(--bk-radius); }

/* ❌ 错误：写死值 */
.bk-button { border-radius: 2px; }
```

### 9.2 未来 v3 支持方式

不需要现在实现，但架构上预留路径：在 `assets/` 下放置可选的版本覆盖文件。

```
assets/
├── bkflow-prototype.css       ← 基础样式（默认 v2）
├── bkflow-prototype.js        ← 交互库（版本无关）
└── theme-v3-override.css      ← （未来）v3 变量覆盖 + 组件差异
```

使用时只需多引一行 CSS 即可切换到 v3 风格：
```html
<link rel="stylesheet" href="../assets/bkflow-prototype.css">
<link rel="stylesheet" href="../assets/theme-v3-override.css"> <!-- 可选 -->
```

### 9.3 实现约束

- CSS 变量全部定义在 `:root` 中，组件样式只用 `var()` 引用
- 组件 class 命名保持 `bk-` 前缀，v2 和 v3 共用
- 同一个组件如果 v2/v3 结构差异大（如 Navigation），在 override 文件中用相同 class 名覆盖

## 10. 组件展示页

`examples/component-showcase.html` 是一个特殊的示例文件，展示所有组件的样式和用法。它同时承担两个职责：

1. **AI 参考**：AI 生成原型前可以读取此文件，了解每个组件的 CSS class 写法
2. **人工验证**：开发者可以在浏览器中打开此文件，验证组件样式是否与 bk-magic-vue 一致

## 11. 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| CSS 复刻精度不够 | 原型与真实页面有视觉差异 | 以 bk-magic-vue 源码为参考，关键组件逐像素对比；接受原型级别的近似 |
| 复杂交互超出声明式能力 | 如拖拽排序、联动表单无法实现 | 在 JS 库中预留 `data-custom` 扩展点；极端场景可在原型中内联 JS |
| 60+ 组件开发量大 | 初期投入较高 | 分 Phase 实现，Phase 1 完成即可覆盖大部分原型需求 |
| AI 生成的 HTML 质量不稳定 | 偶尔生成不正确的结构 | `component-showcase.html` 作为参考减少错误；提供清晰的 class 命名规范 |
