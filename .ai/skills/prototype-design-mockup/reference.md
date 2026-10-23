# 蓝鲸设计稿 · 参考手册

供 `prototype-design-mockup` 在生成图像时查阅。主流程见 [SKILL.md](SKILL.md)。  
**通用约束（必读）**：[design-constraints.md](design-constraints.md)  
**选现网截图**：先查 [visual-baseline-index.md](visual-baseline-index.md)，再写 prompt。

## 蓝鲸视觉 Token（BKFlow 管理端）

| Token | 值 | 用途 |
|-------|-----|------|
| Primary | `#3a84ff` | 主按钮、选中态、链接、已配置徽标 |
| Primary light bg | `#e1ecff` / `#edf4ff` | 列表选中行、浅蓝徽标底 |
| Text primary | `#313238` | 标题、主文案 |
| Text secondary | `#63656e` | 正文、说明 |
| Text tertiary | `#979ba5` | 次要说明、占位、分组标题 |
| Border | `#dcdee5` | 卡片边、分割线 |
| Border strong | `#c4c6cc` | 输入框边框 |
| Page bg | `#f5f7fa` | 内容区背景 |
| Hover / tag gray bg | `#f0f1f5` | 悬停、默认徽标底 |
| Success | `#2dcb56` | 成功 toast / 成功态 |
| Warning | `#ff9c01` | 警告 |
| Danger | `#ea3636` | 错误边框、异常徽标、危险操作 |
| Danger bg | `#fdeeee` | 异常行 / 异常徽标底 |
| Top bar / Sidebar dark | `#1e2430` 左右 | **深色顶栏** + 应用侧栏 |
| Radius | `2px` | 按钮、输入、卡片 |
| Spacing | `8 / 12 / 16 / 24` | 间距网格 |

## 外壳布局（与现网一致）

以 `output/playwright/bkflow-engine-admin/00-space-template-home.png` 为准：

1. **顶栏（深色，非白）**：左白字 `BKFlow`；中 Tab（`空间管理` / `系统管理` / `我的插件`）；右用户 `admin`
2. **应用侧栏（深色）**：顶部空间选择器 `演示空间 (100)`；菜单项图标+文案；当前模块高亮蓝底 `#3a84ff`
3. **内容区（浅灰底）**：按页面类型切换——列表页 / 流程编辑工具栏 / 任务详情等，形态以索引选中的基准图为准

流程编辑页另见 `90-template-edit-node-selected.png`：内容顶为「← 编辑流程 + 流程名」，右上 保存 / 调试 / 发布。

## 状态徽标约定

| 状态 | 样式 |
|------|------|
| 已配置 | 蓝字 `#3a84ff` + 浅蓝底 |
| 默认 | 灰字 `#979ba5` + 灰底 `#f0f1f5` |
| 异常 | 红字 `#ea3636` + 浅红底 `#fdeeee` |
| 成功/通过 | 绿字或绿底 `#2dcb56` |

## 交互标注样式与落点

### 样式

- 红色实心圆，白字编号 ❶❷❸…
- 细红引线 / 箭头指向目标控件
- 旁注：白底、红边或红字、短中文（1–2 句）
- 文案来源：README「编号 \| 元素 \| 交互说明」表；可压缩，不可删关键规则

### 落点（强制）

| 要求 | 说明 |
|------|------|
| 一一对应 | 编号 N 的引线终点 = README 第 N 行「元素」所指控件 |
| 贴目标 | 圆点优先画在目标旁；短引线；避免全部 callout 堆在远离目标的右栏 |
| 文案含位置词 | 写「弹窗内」「实时校验」「下拉」「底栏」时，必须指到该区域内，禁止指到无关表或画布空白 |
| 生成后核对 | 目视：文案描述的控件 ↔ 箭头终点；不一致则重出 |

反例：文案「弹窗内静态分析 / 实时校验」，箭头却指到「影响范围」表或弹窗外 → 不合格。

## GenerateImage Prompt 模板

生成时把 `<...>` 换成该屏具体内容；**务必保留脱敏、现网基准与标注落点段落**。

```text
CRITICAL: Photorealistic BKFlow UI matching the provided production screenshots
as closely as possible. Copy chrome, colors, spacing, component shapes from
references. NOT a generic admin redesign. NOT a white top bar.

PRIVACY (mandatory):
- Top-right user name MUST be exactly "admin" (never copy names from references).
- Space selector MUST be exactly "演示空间 (100)".
- No internal usernames, no real person names in any UI text.

Chrome (from baseline screenshots):
- DARK top bar: BKFlow logo, tabs 空间管理/系统管理/我的插件, user admin
- Dark navy left sidebar: space 演示空间 (100), current module active in #3a84ff
- Main content matching wireframe + baseline container pattern below

Main content (from wireframe):
<粘贴该屏结构要点：选中项、表单字段、成功/失败态、底栏按钮>
<写明容器类型：居中 Dialog / 右侧侧滑 / 流程编辑+节点配置 / 任务详情…>

Interaction annotations (mandatory, precise targeting):
- Red filled circles with white numbers ❶❷❸… and thin red leader lines
- Each circle/line end MUST touch the exact control described by its text
- Short Chinese callout boxes (white bg, red border); place near targets, not a vague right stack
- Mapping (must match):
  ❶ <元素> → <具体控件位置，如：输出表 result 行的 ${x} 按钮>
  ❷ <元素> → <具体控件位置>
  …

Style: primary #3a84ff, text #313238/#63656e/#979ba5, borders #dcdee5,
radius 2px, flat, no purple gradients, no heavy shadows, no glassmorphism.
Chinese UI, PingFang SC look, desktop ~1440x900, aspect 16:9.
```

**参考图 `reference_image_paths` 顺序**

**同系列后续屏（首屏已确认时，强制）**

1. **已确认的同系列 Dialog 金标准** `designs/01-*.png`（或用户指定的确认屏）— 必须第一位  
2. 现网外壳 / Dialog：`00` / `90` / `01` / `94` 等  
3. 该屏 `shots/*.png`（**仅内容结构**，禁止当弹框外形）

Prompt 追加：`Reuse EXACT same Dialog chrome as first reference. Only change inner content for this screen.`

**首屏 / 无已确认稿时**

1. 本屏按 [visual-baseline-index.md](visual-baseline-index.md) 选出的现网截图（2–5 张）
2. 该屏 `shots/*.png`（结构参照）
3. （若有）同系列其它已确认 `designs/*.png`

## 首屏确认话术（示例）

```
首屏设计稿已出：`prototypes/output/<feature>/designs/01-xxx.png`

参考基准：<列出用到的 bkflow-engine-admin 文件名>

请确认：
1. 视觉（深色顶栏 / 侧滑或 Dialog / 控件形态）是否贴近现网
2. 红色交互标注 ❶… 是否齐全，且每条引线是否指到正确控件

确认后我按同一规范出其余 N 屏；若要改，直接说改点（含标注编号）。
```

## 提交前自检清单

- [ ] 已按 [design-constraints.md](design-constraints.md) 核对流转 / 入口 / 主旁路 / 遮罩 / 互斥 / **同系列弹框锁定**
- [ ] 每屏都有对应 `designs/NN-*.png`
- [ ] 每屏生成前查过 visual-baseline-index，并传入现网参考图
- [ ] 后续屏 `reference_image_paths[0]` 为已确认 `designs/01`；弹框外轮廓与首屏一致
- [ ] 改造已有页时布局贴近截图，未自创整页结构
- [ ] Dialog 有遮罩；未叠开互斥面板；向导未跨语境跳转
- [ ] 维护/异常屏标明真实入口；旁路有置灰说明或独立稿
- [ ] 每屏都有红色编号标注，覆盖 README 交互表要点
- [ ] 每条标注引线落点与文案一致（无悬空、无指错）
- [ ] 顶栏为深色；用户为 `admin`；空间为 `演示空间 (100)`
- [ ] 未出现 checkbox 替代 `${x}`、白顶栏等易错项
- [ ] `strings` 扫描 designs 无内部人名 / 敏感域名明文
- [ ] README 目录表已含 `designs/` 一行；流转变更已同步 spec/TAPD（如有）
- [ ] 文件名与 `screens/NN-*.md` 编号对齐

## 完整样例

- `prototypes/output/space-config-redesign/designs/`
- `prototypes/output/parallel-variable-aggregation/designs/`（流程编辑 + 变量弹窗场景）
