# BKFlow 原型工具包实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一套零配置、AI 驱动的 HTML 原型生成工具包，含 CSS 设计系统（Phase 1 核心组件）、声明式 JS 交互库、预览服务器、应用外壳和 AI Skill。

**Architecture:** 纯 HTML/CSS/JS 原型工具包，CSS 复刻 bk-magic-vue 2.x 组件外观，JS 通过 data-* 属性提供声明式交互，Python 标准库 HTTP 服务器提供预览和自动刷新。

**Tech Stack:** HTML5, CSS3 (CSS Variables), Vanilla JavaScript, Python 3 (标准库)

**Spec:** `docs/specs/2026-03-23-prototype-toolkit-design.md`

**Scope:** 本计划覆盖 Phase 1（18 个核心组件）+ 工具链 + AI Skill。Phase 2-4 组件为后续增量计划。

---

## 文件结构

```
prototypes/
├── assets/
│   ├── bkflow-prototype.css          ← CSS 设计系统（Phase 1: 18 个核心组件）
│   ├── bkflow-prototype.js           ← 声明式交互库
│   └── icons/
│       └── bkflow-logo.svg           ← bkflow logo
├── base.html                         ← bkflow 应用外壳
├── examples/
│   ├── list-page.html                ← 示例：列表页
│   ├── form-slider.html              ← 示例：侧滑表单
│   ├── tab-page.html                 ← 示例：Tab 切换页
│   ├── detail-page.html              ← 示例：详情页
│   ├── composite-page.html           ← 示例：复合布局
│   └── component-showcase.html       ← 全组件展示页
├── output/
│   └── .gitkeep
├── serve.py                          ← 预览服务器
└── README.md
```

AI Skill:
```
.ai/skills/prototype-generator/SKILL.md
```

---

## Task 1: 项目脚手架 + 预览服务器

**Files:**
- Create: `prototypes/serve.py`
- Create: `prototypes/output/.gitkeep`
- Create: `prototypes/assets/` (空目录)
- Create: `prototypes/examples/` (空目录)

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p prototypes/{assets/icons,examples,output}
touch prototypes/output/.gitkeep
```

- [ ] **Step 2: 实现 serve.py**

零依赖 Python HTTP 服务器，功能：
- 服务 `prototypes/` 目录下的静态文件
- 向 HTML 响应注入自动刷新 JS（每 1 秒轮询 `/api/mtime`）
- `/api/mtime` 端点返回 `output/` 目录下最新文件的修改时间
- 访问 `/` 时生成索引页，列出 `output/` 和 `examples/` 下的所有 HTML 文件
- 支持 `--port` 参数，默认 9080
- 支持 `--host` 参数，默认 `0.0.0.0`

```python
#!/usr/bin/env python3
"""BKFlow Prototype Preview Server - Zero dependency."""
import argparse
import json
import os
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).parent

AUTO_RELOAD_SCRIPT = """
<script>
(function() {
  var lastMtime = 0;
  setInterval(function() {
    fetch('/api/mtime').then(function(r) { return r.json(); })
    .then(function(data) {
      if (lastMtime && data.mtime > lastMtime) location.reload();
      lastMtime = data.mtime;
    }).catch(function() {});
  }, 1000);
})();
</script>
"""


class PrototypeHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path == '/api/mtime':
            self._handle_mtime()
        elif self.path == '/':
            self._handle_index()
        else:
            super().do_GET()

    def _handle_mtime(self):
        mtime = 0
        for d in ['output', 'examples']:
            dirpath = ROOT / d
            if dirpath.exists():
                for f in dirpath.glob('*.html'):
                    mtime = max(mtime, f.stat().st_mtime)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(json.dumps({'mtime': mtime}).encode())

    def _handle_index(self):
        html_parts = ['<!DOCTYPE html><html><head><meta charset="UTF-8">',
                       '<title>BKFlow Prototypes</title>',
                       '<style>body{font-family:sans-serif;max-width:800px;margin:40px auto;padding:0 20px}',
                       'h1{color:#333}h2{color:#666;margin-top:32px}',
                       'a{color:#3a84ff;text-decoration:none;display:block;padding:8px 0}',
                       'a:hover{text-decoration:underline}</style></head><body>',
                       '<h1>BKFlow Prototypes</h1>']

        for section, dirname in [('Output', 'output'), ('Examples', 'examples')]:
            dirpath = ROOT / dirname
            files = sorted(dirpath.glob('*.html')) if dirpath.exists() else []
            if files:
                html_parts.append(f'<h2>{section}</h2>')
                for f in files:
                    rel = f'/{dirname}/{f.name}'
                    html_parts.append(f'<a href="{rel}">{f.name}</a>')

        if not (ROOT / 'output').exists() or not list((ROOT / 'output').glob('*.html')):
            html_parts.append('<p style="color:#999">No prototypes yet. Use the prototype-generator skill to create one.</p>')

        html_parts.append('</body></html>')
        content = '\n'.join(html_parts).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(content)

    def end_headers(self):
        if hasattr(self, '_headers_buffer'):
            content_type = ''
            for line in self._headers_buffer:
                if b'Content-Type' in line and b'text/html' in line:
                    content_type = 'html'
                    break
        super().end_headers()

    def send_response_only(self, code, message=None):
        super().send_response_only(code, message)

    def copyfile(self, source, outputfile):
        """Inject auto-reload script into HTML responses."""
        import io
        content = source.read()
        if b'</body>' in content:
            content = content.replace(b'</body>',
                                       AUTO_RELOAD_SCRIPT.encode() + b'</body>')
        outputfile.write(content)


def main():
    parser = argparse.ArgumentParser(description='BKFlow Prototype Preview Server')
    parser.add_argument('--port', type=int, default=9080)
    parser.add_argument('--host', default='0.0.0.0')
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), PrototypeHandler)
    print(f'\033[32m✓ Serving prototypes at http://localhost:{args.port}\033[0m')
    print(f'\033[32m✓ Auto-reload enabled\033[0m')
    print(f'  Press Ctrl+C to stop')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')


if __name__ == '__main__':
    main()
```

- [ ] **Step 3: 验证服务器启动**

```bash
cd prototypes && python serve.py &
sleep 2
curl -s http://localhost:9080/ | head -5
curl -s http://localhost:9080/api/mtime
kill %1
```

Expected: 索引页 HTML 和 `{"mtime": 0}` JSON 响应。

- [ ] **Step 4: Commit**

```bash
git add prototypes/
git commit -m "feat(prototypes): 初始化原型工具包目录结构和预览服务器 --story=<TAPD_ID>"
```

---

## Task 2: CSS 设计系统 — 变量 + 重置 + 基础样式

**Files:**
- Create: `prototypes/assets/bkflow-prototype.css`

- [ ] **Step 1: 创建 CSS 文件，写入变量和重置样式**

CSS 变量从 bkflow 前端 `frontend/src/scss/config.scss` 和 `app.scss` 提取。

内容包括：
- `:root` CSS 变量（主色调、文本、背景、边框、圆角、阴影、字体、布局）
- Box model reset（`*, *::before, *::after { box-sizing: border-box }`）
- Body 基础样式（字体、颜色、背景）
- 基础排版（h1-h6、p、a、code）
- 滚动条样式（匹配 bkflow 的 `mixins/scrollbar.scss`）

所有值必须使用 `var()` 引用 CSS 变量，不允许写死。

写入 `prototypes/assets/bkflow-prototype.css`。

- [ ] **Step 2: 创建临时测试页面验证基础样式**

创建 `prototypes/output/test-base.html`，包含基础排版元素（h1-h6、段落、链接、code），用浏览器打开验证字体和颜色是否与 bkflow 一致。

- [ ] **Step 3: 验证后删除测试页面，Commit**

```bash
rm prototypes/output/test-base.html
git add prototypes/assets/bkflow-prototype.css
git commit -m "feat(prototypes): CSS 设计系统 - 变量、重置和基础排版 --story=<TAPD_ID>"
```

---

## Task 3: CSS 设计系统 — Button + Tag

**Files:**
- Modify: `prototypes/assets/bkflow-prototype.css`

- [ ] **Step 1: 实现 Button 组件样式**

参考 bk-magic-vue 的 Button 组件，实现以下 class：
- `.bk-button` — 基础按钮（白底灰边框）
- `.bk-button-primary` — 主要按钮（蓝底白字）
- `.bk-button-success` — 成功按钮（绿底白字）
- `.bk-button-warning` — 警告按钮（黄底白字）
- `.bk-button-danger` — 危险按钮（红底白字）
- `.bk-button-text` — 文字按钮（无边框）
- `.bk-button-small` — 小尺寸
- `.bk-button-large` — 大尺寸
- `.bk-button-disabled` / `.bk-button[disabled]` — 禁用态
- 包含 hover、active 状态

关键样式值：高度 32px、font-size 14px、padding 0 15px、border-radius `var(--bk-radius)`。

- [ ] **Step 2: 实现 Tag 组件样式**

- `.bk-tag` — 基础标签
- `.bk-tag-success` / `.bk-tag-warning` / `.bk-tag-danger` / `.bk-tag-info` — 状态标签
- `.bk-tag-closable` — 可关闭标签（带 × 图标）

- [ ] **Step 3: 创建测试页面验证，然后 Commit**

创建临时 `prototypes/output/test-button-tag.html` 验证所有按钮和标签变体，确认后删除，commit。

```bash
git add prototypes/assets/bkflow-prototype.css
git commit -m "feat(prototypes): CSS 组件 - Button 和 Tag --story=<TAPD_ID>"
```

---

## Task 4: CSS 设计系统 — Input + Form/FormItem + Search + Switcher

**Files:**
- Modify: `prototypes/assets/bkflow-prototype.css`

- [ ] **Step 1: 实现 Input 组件**

- `.bk-input` — 基础输入框（高度 32px，border `var(--bk-border-form)`）
- `.bk-input-large` / `.bk-input-small` — 尺寸变体
- `.bk-input[disabled]` — 禁用态
- `.bk-input:focus` — 聚焦态（border 变为 `var(--bk-primary)`）
- `.bk-textarea` — 多行文本框
- `.bk-input-group` — 输入框组（前/后缀）

- [ ] **Step 2: 实现 Form/FormItem 组件**

- `.bk-form` — 表单容器
- `.bk-form-item` — 表单项（包含 label + 控件 + 错误提示）
- `.bk-form-item .bk-form-label` — 标签（width 100px，右对齐）
- `.bk-form-item .bk-form-content` — 内容区（margin-left 120px）
- `.bk-form-item .bk-form-error` — 错误提示（红色 12px）
- `.bk-form-item.is-required .bk-form-label::before` — 必填星号
- `.bk-form-item.is-error .bk-input` — 错误态输入框（红色边框）
- `.bk-form-vertical` — 纵向布局变体（label 在上方）

- [ ] **Step 3: 实现 Search 组件**

- `.bk-search-input` — 搜索输入框（带搜索图标占位）

- [ ] **Step 4: 实现 Switcher 组件**

- `.bk-switcher` — 开关（36px × 20px 圆角胶囊）
- `.bk-switcher.is-checked` — 开启态（蓝色背景）
- `.bk-switcher[disabled]` — 禁用态

- [ ] **Step 5: 验证并 Commit**

```bash
git add prototypes/assets/bkflow-prototype.css
git commit -m "feat(prototypes): CSS 组件 - Input, Form, Search, Switcher --story=<TAPD_ID>"
```

---

## Task 5: CSS 设计系统 — Select

**Files:**
- Modify: `prototypes/assets/bkflow-prototype.css`

- [ ] **Step 1: 实现 Select 组件**

- `.bk-select` — 下拉选择框容器
- `.bk-select-trigger` — 触发器（看起来像 Input，右侧带下箭头）
- `.bk-select-dropdown` — 下拉面板（白底，shadow，默认 display:none）
- `.bk-select-dropdown.is-show` — 展开态
- `.bk-select-option` — 选项行（hover 高亮）
- `.bk-select-option.is-selected` — 选中态（蓝色文字 + 勾选图标）
- `.bk-select-option.is-disabled` — 禁用态
- `.bk-select[disabled]` — 整体禁用
- `.bk-select .bk-select-placeholder` — placeholder 文字（灰色）

- [ ] **Step 2: 验证并 Commit**

```bash
git add prototypes/assets/bkflow-prototype.css
git commit -m "feat(prototypes): CSS 组件 - Select --story=<TAPD_ID>"
```

---

## Task 6: CSS 设计系统 — Table + Pagination

**Files:**
- Modify: `prototypes/assets/bkflow-prototype.css`

- [ ] **Step 1: 实现 Table 组件**

- `.bk-table` — 表格容器（width 100%，border-collapse）
- `.bk-table thead` — 表头（背景 `#fafbfc`，字色 `var(--bk-text-secondary)`，font-size 12px）
- `.bk-table th` — 表头单元格（padding 12px 16px，border-bottom）
- `.bk-table td` — 数据单元格（padding 12px 16px，border-bottom `var(--bk-border-light)`）
- `.bk-table tr:hover td` — 行 hover（背景 `var(--bk-bg-hover)`）
- `.bk-table-empty` — 空状态行（居中灰色文字，高度 280px）
- `.bk-table .bk-table-sort` — 排序图标样式
- `.bk-table .bk-table-action` — 操作列链接样式（蓝色文字）

- [ ] **Step 2: 实现 Pagination 组件**

- `.bk-pagination` — 分页容器（右对齐，padding 10px 20px）
- `.bk-pagination-item` — 页码（宽高 32px，居中）
- `.bk-pagination-item.active` — 当前页（蓝底白字）
- `.bk-pagination-item:hover` — hover 态
- `.bk-pagination-prev` / `.bk-pagination-next` — 前/后翻页
- `.bk-pagination-total` — 总数文字（"共 X 条"）

- [ ] **Step 3: 验证并 Commit**

```bash
git add prototypes/assets/bkflow-prototype.css
git commit -m "feat(prototypes): CSS 组件 - Table 和 Pagination --story=<TAPD_ID>"
```

---

## Task 7: CSS 设计系统 — Tab + Card

**Files:**
- Modify: `prototypes/assets/bkflow-prototype.css`

- [ ] **Step 1: 实现 Tab 组件**

- `.bk-tab` — Tab 容器
- `.bk-tab-header` — Tab 头部（底部 border）
- `.bk-tab-item` — Tab 项（padding 8px 16px，cursor pointer）
- `.bk-tab-item.active` — 激活态（蓝色文字 + 底部 2px 蓝色 border）
- `.bk-tab-item:hover` — hover 态
- `.bk-tab-panel` — Tab 面板容器
- `.bk-tab-panel[hidden]` — 隐藏的面板（display: none）

- [ ] **Step 2: 实现 Card 组件**

- `.bk-card` — 卡片容器（白底、border、border-radius、shadow）
- `.bk-card-header` — 卡片头部（底部 border）
- `.bk-card-body` — 卡片内容区（padding）
- `.bk-card-footer` — 卡片底部

- [ ] **Step 3: 验证并 Commit**

```bash
git add prototypes/assets/bkflow-prototype.css
git commit -m "feat(prototypes): CSS 组件 - Tab 和 Card --story=<TAPD_ID>"
```

---

## Task 8: CSS 设计系统 — Dialog + Sideslider

**Files:**
- Modify: `prototypes/assets/bkflow-prototype.css`

- [ ] **Step 1: 实现 Dialog 组件**

- `.bk-dialog` — 弹窗容器（fixed 全屏遮罩，默认 display:none）
- `.bk-dialog.is-show` — 显示态
- `.bk-dialog-mask` — 半透明黑色遮罩
- `.bk-dialog-content` — 弹窗内容（居中白色卡片，max-width 480px）
- `.bk-dialog-header` — 头部（标题 + 关闭按钮，padding 16px 24px，border-bottom）
- `.bk-dialog-body` — 主体内容（padding 24px）
- `.bk-dialog-footer` — 底部按钮区（padding 16px 24px，右对齐）

- [ ] **Step 2: 实现 Sideslider 组件**

- `.bk-sideslider` — 侧滑容器（fixed 全屏遮罩，默认 display:none）
- `.bk-sideslider.is-show` — 显示态
- `.bk-sideslider-mask` — 半透明遮罩
- `.bk-sideslider-content` — 侧滑面板（固定右侧，width 640px，白底，shadow）
- `.bk-sideslider-header` — 头部（深色背景 #333，白色文字，关闭按钮）
- `.bk-sideslider-body` — 主体内容（height calc(100% - header - footer)，overflow-y auto）
- `.bk-sideslider-footer` — 底部按钮区（border-top，padding）
- `.bk-sideslider-close` — 关闭按钮

CSS transition：Dialog 淡入，Sideslider 从右侧滑入。

- [ ] **Step 3: 验证并 Commit**

```bash
git add prototypes/assets/bkflow-prototype.css
git commit -m "feat(prototypes): CSS 组件 - Dialog 和 Sideslider --story=<TAPD_ID>"
```

---

## Task 9: CSS 设计系统 — Navigation + Layout + 辅助组件

**Files:**
- Modify: `prototypes/assets/bkflow-prototype.css`

- [ ] **Step 1: 实现 Navigation 组件**

参考 bkflow 的 `Navigation.vue`（深色侧边栏 `#1f2738`，顶部 header 48px）。

- `.bk-navigation` — 导航容器
- `.bk-navigation-header` — 顶部区域（logo + 产品名，高度 `var(--bk-header-height)`）
- `.bk-navigation-menu` — 菜单列表
- `.bk-navigation-menu-item` — 菜单项（padding，hover 高亮）
- `.bk-navigation-menu-item.active` — 当前激活项（左侧蓝色指示条）

- [ ] **Step 2: 实现布局原语**

- `.bk-layout` — 页面骨架（flex，min-width `var(--bk-min-width)`，height 100vh）
- `.bk-content` — 内容区（flex 1，overflow-y auto，padding 20px，background `var(--bk-bg-body)`）
- `.bk-toolbar` — 操作栏（flex，justify-content space-between，margin-bottom 16px）
- `.bk-aside` — 侧边面板（width 240px，border-right）
- `.bk-split` — 分栏布局（flex）
- `.bk-info-card` — KV 信息卡片
- `.bk-steps-container` — 步骤容器
- `.bk-canvas` — 画布区占位

- [ ] **Step 3: 实现辅助组件**

- `.bk-breadcrumb` — 面包屑容器（flex，gap 8px）
- `.bk-breadcrumb-item` — 面包屑项 + 分隔符
- `.bk-loading` — 加载状态（居中旋转动画）
- `.bk-exception` — 异常/空状态（居中图标 + 文字，高度 280px）
- `.bk-grid-row` / `.bk-grid-col` — 栅格行列（flex，支持 col-1 到 col-24）

- [ ] **Step 4: 验证并 Commit**

```bash
git add prototypes/assets/bkflow-prototype.css
git commit -m "feat(prototypes): CSS 组件 - Navigation, Layout 原语和辅助组件 --story=<TAPD_ID>"
```

---

## Task 10: JS 声明式交互库

**Files:**
- Create: `prototypes/assets/bkflow-prototype.js`

- [ ] **Step 1: 实现核心框架和 open/close 交互**

初始化函数在 DOMContentLoaded 时扫描所有 `data-*` 属性并绑定事件。

实现：
- `data-open="target-id"` — 给目标元素添加 `is-show` class
- `data-close` — 从最近的 `.bk-dialog` 或 `.bk-sideslider` 祖先移除 `is-show` class
- 点击遮罩层（`.bk-dialog-mask` / `.bk-sideslider-mask`）关闭浮层

```javascript
(function() {
  'use strict';
  document.addEventListener('DOMContentLoaded', function() {
    initOpen();
    initClose();
    initTabs();
    initSort();
    initFilter();
    initCollapse();
    initDropdown();
    initSteps();
    initHref();
    initNotify();
    initValidation();
  });

  function initOpen() { /* data-open */ }
  function initClose() { /* data-close + mask click */ }
  // ... 下面各 step 实现
})();
```

- [ ] **Step 2: 实现 Tab 切换交互**

- `data-tab="panel-id"` — 点击时：
  1. 同级 `.bk-tab-item` 移除 `active` class
  2. 当前元素添加 `active` class
  3. 同容器内所有 `.bk-tab-panel` 设为 `hidden`
  4. 目标 panel 移除 `hidden`

- [ ] **Step 3: 实现表格排序交互**

- `data-sortable` 在 `<th>` 上 — 点击时：
  1. 获取该列索引
  2. 读取 `<tbody>` 所有行
  3. 按该列文本内容排序（切换升序/降序）
  4. 重新插入 DOM
  5. 更新排序指示器样式

- [ ] **Step 4: 实现搜索过滤交互**

- `data-filter="table-id"` 在 `<input>` 上 — 输入时：
  1. 获取输入值（小写）
  2. 遍历目标表格的 `<tbody>` 所有行
  3. 行内文本不包含输入值的行设为 `display:none`

- [ ] **Step 5: 实现折叠、下拉、步骤、跳转、通知交互**

- `data-collapse="panel-id"` — toggle 目标的 `is-collapsed` class
- `data-dropdown="menu-id"` — toggle 目标的 `is-show` class + 点击其他区域关闭
- `data-step="step-id"` — 切换步骤面板可见性
- `data-href="page.html"` — `window.location.href` 跳转
- `data-notify="消息"` — 创建一个临时通知元素，3 秒后自动移除
- `data-required` 在 `<input>` / `<textarea>` 上 — 所在 form 提交时，值为空则给输入框添加 `is-error` class 并显示 `.bk-form-error` 提示
- `data-pattern="regex"` 在 `<input>` 上 — 所在 form 提交时，值不匹配正则则标记错误

- [ ] **Step 6: 验证交互功能**

创建临时测试页面 `prototypes/output/test-interactions.html`，包含：
- 一个按钮打开 Sideslider，Sideslider 内有关闭按钮
- 一个 Tab 组件，3 个 Tab 可切换
- 一个带 `data-sortable` 的表格
- 一个搜索框过滤表格

在浏览器中逐一测试所有交互。

- [ ] **Step 7: 删除测试页面，Commit**

```bash
rm prototypes/output/test-interactions.html
git add prototypes/assets/bkflow-prototype.js
git commit -m "feat(prototypes): JS 声明式交互库 --story=<TAPD_ID>"
```

---

## Task 11: 应用外壳 base.html

**Files:**
- Create: `prototypes/base.html`
- Create: `prototypes/assets/icons/bkflow-logo.svg`

- [ ] **Step 1: 创建 bkflow logo SVG**

简单的 SVG logo 占位（或从 `frontend/src/` 中提取现有 logo）。查看 `frontend/src/App.vue` 或 `frontend/src/components/Navigation.vue` 确认 logo 使用方式。

- [ ] **Step 2: 创建 base.html**

完整的 bkflow 应用外壳，包含：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BKFlow 原型</title>
  <link rel="stylesheet" href="assets/bkflow-prototype.css">
</head>
<body>
  <div class="bk-layout">
    <nav class="bk-navigation">
      <div class="bk-navigation-header">
        <img src="assets/icons/bkflow-logo.svg" alt="BKFlow" height="24">
        <span>流程引擎服务</span>
      </div>
      <ul class="bk-navigation-menu">
        <li class="bk-navigation-menu-item active">空间管理</li>
        <li class="bk-navigation-menu-item">模板管理</li>
        <li class="bk-navigation-menu-item">任务管理</li>
        <li class="bk-navigation-menu-item">凭证管理</li>
        <li class="bk-navigation-menu-item">决策表</li>
        <li class="bk-navigation-menu-item">插件管理</li>
        <li class="bk-navigation-menu-item">统计分析</li>
      </ul>
    </nav>
    <main class="bk-content">
      <!-- 内容区：AI 生成的内容放在这里 -->
    </main>
  </div>
  <script src="assets/bkflow-prototype.js"></script>
</body>
</html>
```

菜单项参考 bkflow 的 `frontend/src/router/index.js` 确认实际模块列表。

- [ ] **Step 3: 在浏览器中预览确认外壳效果**

```bash
cd prototypes && python serve.py &
# 打开浏览器访问 http://localhost:9080/base.html
```

确认：深色侧边导航栏、logo、菜单项、灰色内容区背景。

- [ ] **Step 4: Commit**

```bash
git add prototypes/base.html prototypes/assets/icons/
git commit -m "feat(prototypes): bkflow 应用外壳 base.html --story=<TAPD_ID>"
```

---

## Task 12: 示例页面 — list-page + form-slider

**Files:**
- Create: `prototypes/examples/list-page.html`
- Create: `prototypes/examples/form-slider.html`

- [ ] **Step 1: 创建 list-page.html**

基于 `base.html` 外壳，在内容区实现一个典型的列表页（参考 bkflow 的凭证管理页 `views/admin/Space/Credential/index.vue`）：

- 面包屑导航
- 操作栏：搜索框（data-filter）+ 新建按钮（data-open 侧滑）
- 数据表格：5 列（名称、类型、创建人、创建时间、操作），带 data-sortable
- 分页
- Mock 数据：5 行接近真实业务的数据

- [ ] **Step 2: 创建 form-slider.html**

基于 `base.html` 外壳，在内容区实现列表页 + 侧滑表单：

- 与 list-page.html 类似的列表
- 点击"新建"按钮打开侧滑面板（data-open）
- 侧滑内包含表单：名称（Input）、类型（Select）、描述（Textarea）、启用（Switcher）
- 底部：取消（data-close）+ 提交（data-close + data-notify）

- [ ] **Step 3: 在浏览器中预览验证**

验证：
- 列表页搜索过滤可用
- 表头排序可用
- 新建按钮打开侧滑
- 侧滑关闭、提交通知可用

- [ ] **Step 4: Commit**

```bash
git add prototypes/examples/
git commit -m "feat(prototypes): 示例页面 - 列表页和侧滑表单 --story=<TAPD_ID>"
```

---

## Task 13: 示例页面 — tab-page + detail-page + composite-page

**Files:**
- Create: `prototypes/examples/tab-page.html`
- Create: `prototypes/examples/detail-page.html`
- Create: `prototypes/examples/composite-page.html`

- [ ] **Step 1: 创建 tab-page.html**

基于 `base.html` 外壳，实现 Tab 切换页（参考 bkflow 空间配置页）：
- 3 个 Tab：基本信息、权限配置、高级设置
- 每个 Tab 面板包含不同的表单内容
- 使用 data-tab 交互

- [ ] **Step 2: 创建 detail-page.html**

基于 `base.html` 外壳，实现详情页（参考 bkflow 任务详情）：
- 面包屑导航
- 标题 + 状态 Tag
- KV 信息卡片（创建人、创建时间、执行时长等）
- 操作按钮（重新执行、暂停等）

- [ ] **Step 3: 创建 composite-page.html**

基于 `base.html` 外壳，实现复合布局：
- bk-split 左右分栏
- 左侧：分组列表（bk-aside）
- 右侧：操作栏 + 表格 + 分页
- 点击左侧分组可高亮

- [ ] **Step 4: 验证并 Commit**

```bash
git add prototypes/examples/
git commit -m "feat(prototypes): 示例页面 - Tab页、详情页和复合布局 --story=<TAPD_ID>"
```

---

## Task 14: 全组件展示页

**Files:**
- Create: `prototypes/examples/component-showcase.html`

- [ ] **Step 1: 创建 component-showcase.html**

一个完整的页面，按分类展示所有 Phase 1 组件的各种变体和状态。每个组件区域包含：
- 组件名称标题
- 各变体（类型、尺寸、状态）的实例
- 对应的 CSS class 名称注释

分类展示：
1. **基础**：Button（所有变体）、Tag（所有状态）
2. **表单**：Input、Textarea、Select、Search、Switcher、Form/FormItem
3. **数据展示**：Table（含排序）、Pagination
4. **导航**：Tab、Breadcrumb
5. **反馈**：Dialog、Sideslider、Loading、Exception
6. **布局**：Grid、Card
7. **布局原语**：toolbar、aside、split、info-card

- [ ] **Step 2: 在浏览器中预览，逐一对比各组件与 bk-magic-vue 真实样式**

重点对比：Button、Input、Table、Tab、Sideslider 这 5 个最常用组件的样式差异，调整 CSS 直到满意。

- [ ] **Step 3: Commit**

```bash
git add prototypes/examples/component-showcase.html
git commit -m "feat(prototypes): Phase 1 全组件展示页 --story=<TAPD_ID>"
```

---

## Task 15: AI Skill — prototype-generator

**Files:**
- Create: `.ai/skills/prototype-generator/SKILL.md`

- [ ] **Step 1: 编写 SKILL.md**

内容包含：

1. **Skill 元数据**：name、description、触发条件
2. **定位说明**：独立工具，不接入 superpowers 流程链
3. **完整工作流**：
   - 启动 serve.py
   - 检查 base.html（不存在则引导构建）
   - 需求澄清（逐一提问）
   - 读取 base.html 外壳 → 填充内容区 → 保存到 output/
   - 告知预览 URL
   - 迭代循环
4. **生成规则**：
   - 读取 `examples/component-showcase.html` 了解可用组件 class
   - 读取 `base.html` 获取外壳 HTML 结构
   - **路径修正规则**：`base.html` 在 `prototypes/` 根目录，引用 `assets/...`；生成到 `output/` 的文件需要使用 `../assets/...`（多一级目录）。Skill 必须在生成时将 `href="assets/..."` 和 `src="assets/..."` 替换为 `href="../assets/..."` 和 `src="../assets/..."`
   - CSS class 使用 `bk-` 前缀
   - 交互使用 `data-*` 属性
   - Mock 数据接近真实业务
   - 版本管理：xxx.html → xxx-v2.html → xxx-v3.html
5. **后端模型读取规则**（可选）
6. **首次使用引导**（构建 base.html 的流程）

- [ ] **Step 2: 验证 Skill 可被识别**

确认 `.ai/skills/prototype-generator/SKILL.md` 文件路径正确，内容完整。

- [ ] **Step 3: Commit**

```bash
git add .ai/skills/prototype-generator/
git commit -m "feat(prototypes): AI Skill - prototype-generator --story=<TAPD_ID>"
```

---

## Task 16: README + Skill 注册

**Files:**
- Create: `prototypes/README.md`
- Modify: `AGENTS.md` — 添加 prototype-generator skill 条目
- Modify: `.cursor/rules/use-skills.mdc` — 添加 prototype-generator skill 条目

- [ ] **Step 1: 编写 README.md**

内容：
- 工具包介绍和用途
- 快速开始（3 步：启动服务器、触发 skill、预览原型）
- 目录结构说明
- 组件 CSS class 速查表（Phase 1 组件）
- 交互 data-* 属性速查表

- [ ] **Step 2: 注册 Skill**

在 `AGENTS.md` 的技能表格中添加：

```markdown
| prototype-generator | `.ai/skills/prototype-generator/SKILL.md` | 需要快速出产品原型时，如"做个原型"、"设计页面" |
```

在 `.cursor/rules/use-skills.mdc` 的技能表格中添加同样的条目。

- [ ] **Step 3: Commit**

```bash
git add prototypes/README.md AGENTS.md .cursor/rules/use-skills.mdc
git commit -m "docs(prototypes): README 和 Skill 注册 --story=<TAPD_ID>"
```

---

## Checkpoint: Phase 1 完成验证

完成 Task 1-16 后，执行以下验证：

- [ ] **验证 1: 服务器可启动**
```bash
cd prototypes && python serve.py --port 9081 &
curl -s http://localhost:9081/ | grep "BKFlow"
curl -s http://localhost:9081/api/mtime
kill %1
```

- [ ] **验证 2: 所有示例页面可访问且交互正常**

在浏览器中逐一打开：
- `http://localhost:9081/examples/list-page.html` — 搜索、排序、新建按钮可用
- `http://localhost:9081/examples/form-slider.html` — 侧滑打开/关闭/提交可用
- `http://localhost:9081/examples/tab-page.html` — Tab 切换可用
- `http://localhost:9081/examples/detail-page.html` — 页面展示正常
- `http://localhost:9081/examples/composite-page.html` — 左右分栏、分组切换可用
- `http://localhost:9081/examples/component-showcase.html` — 所有组件展示正常

- [ ] **验证 3: AI Skill 可识别**

在 Cursor 中输入"做一个原型"，确认 prototype-generator skill 被触发。
