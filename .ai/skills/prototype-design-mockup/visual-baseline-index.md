# BKFlow 现网截图视觉基准索引

> **用途**：出设计稿前，按本屏 UI 模式查表，选出 2–5 张 `output/playwright/bkflow-engine-admin/*.png` 作为 `GenerateImage` 的 `reference_image_paths`。  
> **根目录**：`output/playwright/bkflow-engine-admin/`  
> **脱敏**：参考图里可能含真实账号 / 空间名；生成稿必须改写为 `admin` / `演示空间 (100)`。

## 使用步骤（强制）

1. 读线框 `screens/NN-*.md`，判断本屏涉及哪些 **UI 模式**（见下表「按 UI 模式选图」）。
2. 每个模式至少选 **1 张主基准图**；外壳类再补 1 张（`00` 或当前模块列表页）。
3. 将选中路径写入 `reference_image_paths`（顺序建议：外壳 → 主容器 → 弹层/表单细节 → 该屏 `shots/*.png` → 已确认的上一屏 `designs/*.png`）。
4. Prompt 中写明：**视觉必须贴近这些参考截图**（深色顶栏、侧滑宽度、按钮位置、表格 `${x}` 等），禁止凭空 invent 白顶栏 / 勾选框替代 `${x}` 等。

---

## 按 UI 模式选图（主索引）

| UI 模式 | 关键词 / 线框特征 | 主基准（必选其一） | 辅助基准 | 生成时必须对齐的点 |
|---------|-------------------|--------------------|----------|-------------------|
| **A. 管理端外壳** | 任意管理页 | `00-space-template-home.png` | `70-system-space-list.png`, `80-plugin-list.png` | **深色顶栏**（非白）；Logo + 空间管理/系统管理/我的插件；深色侧栏；空间选择器；主色 `#3a84ff` |
| **B. 列表页 + 搜索/分页** | 表格列表、空态 | `00-space-template-home.png` | `40-space-credential-list.png`, `12-space-mocktask-list.png`, `10-space-task-empty-state.png`, `20-space-decision-empty-state.png`, `60-space-label-empty-list.png` | 蓝主按钮在左上；搜索在右；表头浅灰；操作列蓝字链接；底部分页 |
| **C. 居中 Dialog** | 新建/确认/校验弹窗 | `01-space-template-create-dialog.png` | `02-space-template-create-validation.png`, `05-space-template-copy-confirm.png`, `06-space-template-delete-confirm.png`, `61-space-label-create-dialog.png`, `81-plugin-authorize-dialog.png`, `13-space-mocktask-delete-confirm.png`, `31-space-config-restore-confirm.png`, `94-template-debug-save-confirm.png`, `95-template-debug-execute-error-modal.png` | 白底居中；标题左 + 右上 X；表单 label；**底栏按钮居中**（主蓝 + 白边取消）；危险操作用确认文案 |
| **D. 右侧 Sideslider** | 侧滑新建/编辑表单 | `03-space-template-create-task-sideslider.png` | `04-space-template-create-task-json-mode.png`, `41-space-credential-create-sideslider.png`, `42-space-credential-view-content.png` | 右侧白面板盖住部分列表；标题在侧滑顶；底栏 **确定/提交在左下**（侧滑内，非页面居中） |
| **E. 流程编辑画布** | 模板编辑、节点选中 | `90-template-edit-node-selected.png` | `93-template-save-enabled-after-node-confirm.png` | 顶栏为「← 编辑流程 + 流程名」；右上 保存/调试/**发布**；左节点工具条；画布缩放条；选中节点蓝框 |
| **F. 节点配置侧滑** | 节点配置、输出参数 | `91-template-node-config-panel.png` | `92-template-global-vars-popup.png` | 右侧「节点配置」；顶右「全局变量」链接；分区：基础信息/输入/输出；输出表列 **名称\|KEY\|勾选为全局变量**；操作为 **`${x}` 方钮**（非 checkbox）；底栏左下 确定+取消 |
| **G. 全局变量侧滑** | 变量列表/编辑（流程设置） | `90-template-edit-node-selected.png`（画布）+ 侧滑形态见 `03`/`41` | 代码真源：`TabGlobalVariables/index.vue`（`bk-sideslider` width 800，头「全局变量 > 编辑」） | **禁止与「节点配置」同时出现**。从流程编辑顶栏设置图标打开右侧侧滑，画布仍可见；编辑态标题为「全局变量 > 编辑」，表单对齐 `VariableEdit.vue`。`92` 仅作节点配置内「全局变量」快捷弹层参考，**不是**流程级变量编辑主路径 |
| **H. 任务执行详情** | 节点详情、输出预览、日志 | `96-task-execute-detail-node-detail.png` | `97-task-execute-detail-call-log.png`, `98-task-execute-detail-config-snapshot.png` | 侧栏「任务」高亮；左节点列表；右详情标题+完成态；Tab：执行记录/配置快照/操作历史/调用日志；参数表；日志深色代码块 |
| **I. 引擎面板表单** | 引擎请求/调试入参 | `11-engine-panel-task-request-form.png` | `14-engine-panel-mocktask-request-form.png`, `95-template-debug-execute-error-modal.png` | 调试/引擎表单分区；主按钮在内容区左下 |
| **J. 代码/JSON 编辑** | JSON 模式、源码配置 | `30-space-config-code-form.png` | `04-space-template-create-task-json-mode.png` | 代码区等宽字体；表单/JSON 模式切换 |
| **K. 决策表编辑** | 决策表 | `21-decision-editor-new.png` | `20-space-decision-empty-state.png` | 决策表编辑器布局 |
| **L. 系统管理** | 空间/模块列表 | `70-system-space-list.png` | `71-system-module-list.png` | 系统管理顶栏 Tab；列表样式同 B |
| **M. 插件管理** | 插件列表/授权 | `80-plugin-list.png` | `81-plugin-authorize-dialog.png` | 「我的插件」语境；状态绿徽标；授权确认 Dialog |
| **N. 运营统计空白** | 空白页 | `50-space-statistics-blank.png` | — | 空态占位 |

---

## 按场景组合速查（常见设计稿屏）

| 设计稿场景 | 推荐 `reference_image_paths`（按序） |
|------------|--------------------------------------|
| 流程编辑 + 节点配置 + 变量冲突弹窗（向导步骤1） | `91`, `90`, `01` 或 `81`, 本屏 `shots`；Dialog 须有遮罩 |
| 聚合方式设置（向导步骤2，仍在节点配置） | `91`, `01`/`81`（Dialog）, `90`, 本屏 `shots`；**禁止**改成「全局变量」侧滑 |
| 引用影响确认（向导步骤3，同链路） | `81` 或 `31`, `91`, `90`, 本屏 `shots`；完成后仍回节点配置 |
| 事后微调：全局变量侧滑编辑 | `90`（无节点配置）, `03`/`41`（侧滑）, 本屏 `shots`；与创建向导解耦 |
| 分支联动 / 多场景状态卡 | `00`, `91`, `02`（校验态）, 本屏 `shots` |
| 任务执行 · 聚合结果预览 | `96`, `97`, `98`, 本屏 `shots` |
| 空间配置类改版 | `30`, `31`, `00`, 已有 `space-config-redesign/designs` |
| 列表 + 新建 Dialog | `00`, `01`, `02` |
| 列表 + 右侧新建侧滑 | `00`, `03`, `41` |
| **发布确认 + 版本 Diff（同系列后续屏）** | **已确认** `prototypes/.../designs/01-release-confirm-diff-overview.png`（第一位）, `90`, `01`/`94`, 本屏 `shots`；外壳锁定屏1，只改内部 |

完整路径前缀一律：`output/playwright/bkflow-engine-admin/`（同系列已确认 `designs/` 除外，须放第一位）。

---

## 全量文件目录（编号 → 内容）

| 文件 | 一句话内容 | 主要模式 |
|------|------------|----------|
| `00-space-template-home.png` | 流程列表首页（外壳金标准） | A, B |
| `01-space-template-create-dialog.png` | 新建流程 Dialog | C |
| `02-space-template-create-validation.png` | 新建流程校验失败 | C |
| `03-space-template-create-task-sideslider.png` | 新建任务侧滑 | D |
| `04-space-template-create-task-json-mode.png` | 新建任务 JSON 模式 | D, J |
| `05-space-template-copy-confirm.png` | 复制确认 | C |
| `06-space-template-delete-confirm.png` | 删除确认 | C |
| `10-space-task-empty-state.png` | 任务空态 | B |
| `11-engine-panel-task-request-form.png` | 引擎任务请求表单 | I |
| `12-space-mocktask-list.png` | Mock 任务列表 | B |
| `13-space-mocktask-delete-confirm.png` | Mock 删除确认 | C |
| `14-engine-panel-mocktask-request-form.png` | Mock 引擎请求表单 | I |
| `20-space-decision-empty-state.png` | 决策表空态 | B, K |
| `21-decision-editor-new.png` | 新建决策表编辑器 | K |
| `30-space-config-code-form.png` | 空间配置代码表单 | J |
| `31-space-config-restore-confirm.png` | 恢复默认确认 | C |
| `40-space-credential-list.png` | 凭证列表 | B |
| `41-space-credential-create-sideslider.png` | 新建凭证侧滑 | D |
| `42-space-credential-view-content.png` | 查看凭证内容 | D |
| `50-space-statistics-blank.png` | 运营统计空白 | N |
| `60-space-label-empty-list.png` | 标签空列表 | B |
| `61-space-label-create-dialog.png` | 新建标签 Dialog | C |
| `70-system-space-list.png` | 系统·空间列表 | A, L |
| `71-system-module-list.png` | 系统·模块列表 | L |
| `80-plugin-list.png` | 插件列表 | A, M |
| `81-plugin-authorize-dialog.png` | 插件授权确认 Dialog | C, M |
| `90-template-edit-node-selected.png` | 流程编辑·节点选中 | E |
| `91-template-node-config-panel.png` | 节点配置侧滑 | F |
| `92-template-global-vars-popup.png` | 全局变量弹层 | G, F |
| `93-template-save-enabled-after-node-confirm.png` | 节点确认后可保存 | E |
| `94-template-debug-save-confirm.png` | 调试保存确认 | C |
| `95-template-debug-execute-error-modal.png` | 调试执行异常弹窗 | C, I |
| `96-task-execute-detail-node-detail.png` | 任务·节点详情·执行记录 | H |
| `97-task-execute-detail-call-log.png` | 任务·调用日志 | H |
| `98-task-execute-detail-config-snapshot.png` | 任务·配置快照 | H |

---

## 易错对照（参考图 vs 错误生成）

| 错误生成 | 正确（见参考图） |
|----------|------------------|
| 白色顶栏 + 蓝下划线 Tab | **深色顶栏**，白字 Tab（`00`/`90`） |
| 输出参数用 checkbox | 用 **`${x}` 方钮**（`91`） |
| 变量冲突做成整页表单 | 节点配置侧滑 + **居中 Dialog**（`91`+`01`） |
| 全局变量编辑叠在节点配置上 | **互斥**：流程顶栏打开「全局变量」侧滑（`全局变量 > 编辑`），画布可见、无节点配置（见 `TabGlobalVariables`） |
| Dialog 按钮贴右下 | Dialog **按钮居中**（`01`/`81`） |
| 侧滑按钮居中 | 侧滑 **左下** 确定/取消（`91`/`03`） |
| 流程编辑顶栏像列表页 | 「← 编辑流程」+ 保存/调试/发布（`90`） |
| 任务详情做成自定义双栏仪表盘 | 左节点列表 + 右 Tab 详情（`96`） |
| Dialog 无遮罩、背景同亮 | 半透明遮罩压暗画布/侧滑（对齐现网 Dialog） |
| 向导下一步跳到互斥面板 | 同语境多步；事后入口单独成屏（见 [design-constraints.md](design-constraints.md)） |
| 维护态无入口说明书页 | 图上标明真实操作入口 |

索引更新：若 `bkflow-engine-admin/` 新增截图，在本文件「全量文件目录」与对应「UI 模式」行各补一行。  
通用交互/流转约束见 [design-constraints.md](design-constraints.md)。
