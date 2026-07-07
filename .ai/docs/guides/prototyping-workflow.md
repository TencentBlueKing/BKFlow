# 原型产出与提设计需求 · 操作指南

面向开发者与 AI Agent。BKFlow 统一用 **wiremd 线框 + Mermaid 流程图 + 全页截图**产出低保真原型，交给设计师出高保真设计稿。流程规范见 `.ai/skills/prototype-wireframe/SKILL.md`，本文档只讲**怎么做**：工具链、语法、渲染、截图、Figma 导出、提设计需求。

## 为什么是这套

| 诉求 | wiremd + Mermaid 如何满足 |
|------|---------------------------|
| 完整表达交互细节 | wiremd 的 `<!-- -->` callout 逐元素标注交互 |
| 低保真、不纠结视觉 | sketch 手绘风，只表达结构，视觉留给设计师 |
| 可评审、可版本化 | 纯文本源，可 diff、可 code review、可 AI 迭代 |
| 能交给设计师继续 | wiremd 可导出 Figma JSON，用官方插件导入为可编辑 frames |
| 零环境负担 | 全程 `npx`，无需全局安装 |

## 工具链

全部通过 `npx` 免安装运行：

| 用途 | 命令 |
|------|------|
| 渲染 / 预览线框 | `npx -y @eclectic-ai/wiremd` |
| 全页截图 | `npx playwright screenshot` |
| 流程图 | Mermaid，直接写在 README 的 ```` ```mermaid ```` 代码块里，GitHub / 多数预览器可渲染 |

**一次性准备**（截图需要 headless 浏览器）：

```bash
npx playwright install chromium-headless-shell
```

> **npm cache 权限坑**：若 `npx` 报 npm 缓存权限错误（cache 目录被 root 占用），临时指定缓存目录再跑：
> ```bash
> export npm_config_cache=/tmp/npm-cache-wiremd
> ```

## wiremd 语法速查

线框源文件是普通 Markdown + wiremd 扩展。核心语法：

| 写法 | 作用 |
|------|------|
| `::: sidebar` … `:::` | 侧边栏容器 |
| `::: card` … `:::` | 卡片容器 |
| `::: row` / `::: row {right}` | 横向排列（`{right}` 右对齐，常用于底部操作条） |
| `#### 标题` / `### 标题` | 分区标题 |
| `[按钮]` | 普通按钮 |
| `[按钮]*` | 主按钮（primary） |
| `[按钮]{secondary}` / `{danger}` | 次级 / 危险按钮 |
| `[占位文本___]` | 输入框（下划线示意宽度） |
| `[占位文本]{type:search}` / `{type:url}` | 指定输入类型（搜索 / URL） |
| `[[链接文本](#)]` | 侧栏 / 列表里的可点击项 |
| `[[ 面包屑文本 ]]` | 面包屑 |
| `((徽标))` | 徽标 / 状态标记 |
| `((徽标)){success}` / `{error}` / `{primary}` | 带颜色的徽标 |
| `- (*) 选项` / `- ( ) 选项` | 单选（选中 / 未选） |
| `\| 列 \| 列 \|` 表格语法 | 渲染为表格 |
| `> 文本` | 备注 / 媒体位占位说明 |
| `<!-- ❶ 交互说明 -->` | 交互标注 callout（渲染时用 `--show-comments` 显示） |

### 已知坑与规避

这些是实际踩过的解析坑，按"规避写法"来写：

| 坑 | 规避写法 |
|----|----------|
| 徽标 `((...))` 放在标题行里可能渲染成字面量 | 把徽标**单独放一行**，写在标题下方 |
| 按钮和徽标写在同一行会解析异常 | 按钮、徽标**分行**，或分别包进 `::: row` |
| URL 占位里出现 `://` 会打断解析 | 占位文本只写纯描述（如「apigw meta 接口地址」），**不写** `://`；类型交给 `{type:url}` |
| 想标注交互又不想污染结构 | 一律用 `<!-- ❶ ... -->` 注释，渲染时 `--show-comments` 才显示 |

### 最小屏模板

```markdown
# 页面名 · 说明

[[ 一级 > 二级 > 当前页 ]]

::: card
#### 用途
一句话说明这屏是干什么的。

#### 影响
改动会影响什么。

[查看文档](#)
:::

::: card
#### 配置
展示名称
[请输入名称___]

开关项
- (*) 开启（默认）
- ( ) 关闭
:::

<!-- ❶ 说明这个控件的保存时机 / 校验规则 / 状态指示。 -->

::: row {right}
[恢复默认值]{secondary} [取消] [保存]*
:::

<!-- ❷ 说明底部操作：危险操作二次确认、保存成功 toast 等。 -->
```

## 渲染与预览

```bash
cd prototypes/output/<feature-name>

# 热更迭代：起本地服务，改 screens/*.md 自动刷新
npx -y @eclectic-ai/wiremd screens/ --serve 3000 --watch --show-comments

# 批量渲染为 HTML（sketch 手绘风；可换 --style wireframe/clean）
mkdir -p html
for f in screens/*.md; do
  npx -y @eclectic-ai/wiremd "$f" --style sketch --show-comments -o "html/$(basename "$f" .md).html"
done
```

> `html/` 只是临时产物，**不提交进仓库**（现渲染即可）。

## 全页截图

渲染出 HTML 后，用 Playwright 对每屏截全页图存入 `shots/`：

```bash
mkdir -p shots
for f in html/*.html; do
  name=$(basename "$f" .html)
  npx playwright screenshot --full-page "file://$(pwd)/$f" "shots/$name.png"
done
```

截图用于 README 内嵌展示；README 里用相对路径引用，如 `![xxx](shots/01-xxx.png)`。

## 导出 Figma

wiremd 可导出 JSON，用官方 Figma 插件导入为可编辑 frames，方便设计师直接接手：

```bash
npx -y @eclectic-ai/wiremd screens/04-xxx.md --format json -o xxx.json
```

## 汇总 README

`prototypes/output/<feature-name>/README.md` 结构：

1. 标题 + 关联 spec / plan 链接（回链 `docs/specs/`、`docs/plans/`）+ 工具与风格说明。
2. 目录表（`screens/*.md` 源、`shots/*.png` 截图）。
3. 预览与渲染命令（复制本指南对应命令）。
4. 全局交互流程：Mermaid `flowchart` / `stateDiagram-v2`。
5. 每屏一节：一句话场景 + `![](shots/NN.png)` 截图 + 编号交互说明表。
6. 补充说明：媒体位待补、视觉以 bk-magic-vue 为准、全状态覆盖情况、可迭代提示。

编号交互说明表格式：

```markdown
| 编号 | 元素 | 交互说明 |
|------|------|----------|
| ❶ | 左栏分组列表 | 按分组分区 + 顶部搜索；每项状态徽标：已配置 / 默认 / 异常标红。 |
| ❷ | 保存按钮 | 保存成功后顶部 toast，左栏徽标转「已配置」。 |
```

## 提设计需求（TAPD）

产出原型后，必须在 TAPD 建单交付设计师，形成闭环：

1. **确定父需求单**：用 `tapd-workitem-sync` skill 获取 / 确认本次功能对应的父需求单 ID（bk-flow → `workspace_id = 70120217`）。
2. **建子需求单**：在父单下 `create_story_or_task`（`entity_type: "stories"`），指派给设计师，`description` 包含：
   - 方案一句话背景。
   - **链接**：`docs/specs/…-design.md`、`docs/plans/….md`、`prototypes/output/<feature-name>/README.md`。
   - 关键交互要点（从各屏 callout 提炼）。
   - 期望产出：高保真设计稿 / 交互稿，遵循蓝鲸 bk-magic-vue 设计系统。
3. TAPD MCP 工具的具体用法见 `.ai/skills/tapd-workitem-sync/SKILL.md` 与其 `reference.md`。

## 完整样例

已跑通的参考：`prototypes/output/space-config-redesign/`（5 屏线框 + Mermaid 流程 + 截图 + 交互表）。
