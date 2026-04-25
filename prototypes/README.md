# BKFlow 原型工具包

## 简介

BKFlow 原型工具包是一套**零 Node 依赖**的静态 HTML/CSS/JS 工具：用蓝鲸风格的设计系统（`bkflow-prototype.css`）和声明式交互（`bkflow-prototype.js`），在浏览器里快速做出可点击、可演示的页面原型。适合后端、产品或任何需要在**不搭前端工程**的前提下产出高保真交互稿的人；当前推荐把长期页面类型沉淀到 `masters/`，把单次需求页面放到 `features/`，把历史扁平页面迁入 `features/_legacy/`，而 `examples/` 只保留组件参考。根路径 `/` 是中文「BKFlow 原型展厅」首页，不再把根首页描述成简单目录索引。

## 快速开始

1. **启动预览服务器**：`cd prototypes && python serve.py`
2. **在 Cursor 中触发**：对 AI 说「做一个 xxx 的原型」或遵循 `.ai/skills/prototype-generator/SKILL.md`
3. **浏览器预览**：打开 `http://localhost:9080`（根路径就是展厅首页，优先展示 `features/`）

## 首页展示来源

- `feature.meta.json` 是仓库内 active feature 的首页展示来源；运行时仍保留容错回退，所以缺失或损坏时会退到目录中的可展示 HTML 页面。
- `title`、`summary`、`status`、`tags`、`coverTheme`、`order` 和 `featuredPages` 会共同决定首页卡片与代表页。
- `README.md` 负责背景说明，HTML 页面负责实际预览。
- 当 feature 缺少 `feature.meta.json` 时，首页会回退到目录中的可展示 HTML 页面。

### 首页元数据

```json
{
  "title": "页面标题",
  "summary": "一句话简介",
  "status": "可评审",
  "tags": ["流程编辑", "任务详情"],
  "coverTheme": "mixed-admin",
  "order": 10,
  "featuredPages": [
    {
      "path": "pages/space/flow-edit.html",
      "title": "流程编辑页",
      "summary": "画布编排和节点抽屉",
      "pageType": "流程编辑"
    }
  ]
}
```

首页只认这些元数据字段来排序、分组和挑选代表页，不需要再回头依赖旧的扁平首页目录认知。

## 目录结构

| 路径 | 说明 |
|------|------|
| `assets/bkflow-prototype.css` | 设计系统样式（Phase 1 起覆盖核心组件） |
| `assets/bkflow-prototype.js` | 声明式交互（`data-*` 属性驱动） |
| `assets/icons/` | 图标等静态资源（如 logo） |
| `masters/` | 长期页面类型真源，按母版类别组织 |
| `masters/_shared/` | 共享壳子与导航骨架，供各类母版复用 |
| `features/` | 单次需求目录，承接某个 slug 下的成套页面 |
| `features/_legacy/` | 历史扁平原型的过渡归档区 |
| `examples/` | 页面模式示例，仅保留 `component-showcase.html` 组件参考 |
| `serve.py` | 基于标准库的静态服务与简单自动刷新 |

## 组件 CSS Class 速查表（Phase 1）

| 组件 | 常用 class |
|------|------------|
| **Button** | `.bk-button`、`.bk-button-primary`、`.bk-button-success`、`.bk-button-warning`、`.bk-button-danger`、`.bk-button-text`、`.bk-button-small`、`.bk-button-large`、`.bk-button-disabled` |
| **Tag** | `.bk-tag`、`.bk-tag-success`、`.bk-tag-warning`、`.bk-tag-danger`、`.bk-tag-info` |
| **Input** | `.bk-input`、`.bk-textarea`、`.bk-input-small`、`.bk-input-large`、`.bk-input-group`、`.bk-input-group-addon` |
| **Search** | `.bk-search-input` |
| **Switcher** | `.bk-switcher`、`.is-checked` |
| **Select** | `.bk-select`、`.bk-select-trigger`、`.bk-select-placeholder`、`.bk-select-dropdown`、`.bk-select-option`、`.is-show`、`.is-selected`、`.is-disabled` |
| **Form** | `.bk-form`、`.bk-form-item`、`.bk-form-label`、`.bk-form-content`、`.bk-form-error`、`.bk-form-vertical`、`.is-required`、`.is-error` |
| **Table** | `.bk-table`、`.bk-table-sort`、`.bk-table-empty`、`.bk-table-action`、表头 `.is-asc` / `.is-desc` |
| **Pagination** | `.bk-pagination`、`.bk-pagination-item`、`.bk-pagination-total`、`.active` |
| **Tab** | `.bk-tab`、`.bk-tab-header`、`.bk-tab-item`、`.bk-tab-panel`、`.active`、`[hidden]` 控制面板 |
| **Card** | `.bk-card`、`.bk-card-header`、`.bk-card-body`、`.bk-card-footer` |
| **Dialog** | `.bk-dialog`、`.bk-dialog-mask`、`.bk-dialog-content`、`.bk-dialog-header`、`.bk-dialog-body`、`.bk-dialog-footer`、`.bk-dialog-close`、`.is-show` |
| **Sideslider** | `.bk-sideslider`、`.bk-sideslider-mask`、`.bk-sideslider-content`、`.bk-sideslider-header`、`.bk-sideslider-body`、`.bk-sideslider-footer`、`.bk-sideslider-close`、`.is-show` |
| **Navigation / 布局** | `.bk-layout`、`.bk-navigation`、`.bk-navigation-header`、`.bk-navigation-menu`、`.bk-navigation-menu-item`、`.bk-content`、`.active` |
| **工具栏与扩展布局** | `.bk-toolbar`、`.bk-toolbar-left`、`.bk-toolbar-right`、`.bk-aside`、`.bk-split`、`.bk-info-card`、`.bk-info-card-item`、`.bk-info-card-label`、`.bk-info-card-value` |
| **Breadcrumb** | `.bk-breadcrumb`、`.bk-breadcrumb-item` |
| **Loading** | `.bk-loading` |
| **Exception** | `.bk-exception` |
| **Grid** | `.bk-grid-row`、`.bk-grid-col-1` … `.bk-grid-col-24` |

更完整的示例见 `examples/component-showcase.html`。

## 交互 `data-*` 属性速查表

| 属性 | 用法 | 效果 |
|------|------|------|
| `data-open` | `data-open="浮层元素 id"` | 打开对应侧滑或弹窗（需与 `.bk-sideslider` / `.bk-dialog` 等结构配合） |
| `data-close` | 置于关闭按钮等元素上 | 关闭当前侧滑/弹窗 |
| `data-tab` | `data-tab="面板 id"` | 切换 Tab 对应面板显示 |
| `data-sortable` | 表头 `th` 上声明 | 点击表头列切换升序/降序排序 |
| `data-filter` | 输入框等，`data-filter="表格 id"` | 按输入内容过滤表格行 |
| `data-collapse` | `data-collapse="面板 id"` | 折叠/展开指定面板 |
| `data-dropdown` | `data-dropdown="菜单 id"` | 展开/收起下拉菜单 |
| `data-required` | 表单项控件上 | 提交时校验必填，错误时展示表单错误态 |
| `data-pattern` | `data-pattern="正则字符串"` | 提交时用正则校验值 |
| `data-href` | `data-href="其它页面.html"` | 原型页间跳转 |
| `data-notify` | `data-notify="提示文案"` | 点击后弹出通知提示 |
| `data-step` | `data-step="步骤面板 id"` | 步骤/向导面板切换 |

## 远程开发

通过 SSH 连接远端开发机时，把本机浏览器指向远端 `serve.py` 端口，可在本地执行：

```bash
ssh -L 9080:localhost:9080 your-user@your-dev-host
```

然后在本地浏览器访问 `http://localhost:9080` 即可预览远端 `prototypes` 服务。
