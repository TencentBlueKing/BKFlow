# 03 后台任务与迁移清单

[返回总览](2026-10-30-space-plugin-catalog-v2-review-design.md) · [模型与接口](2026-10-30-space-plugin-catalog-v2-contracts.md) · [实施与验收](../plans/2026-10-30-space-plugin-catalog-v2-team-plan.md)

## Celery：新增 2 个，改造 3 个

**拆分方向已确认，函数名/消息字段仍为草案。** 复用现有目录同步与蓝鲸插件同步，新增自动 AI 和新空间初始化两个薄任务包装；不增加独立服务或 Engine 队列。

| 任务 | 新增 / 改造 | 触发与拟定参数 | 执行内容 / 去重依据 |
| --- | --- | --- | --- |
| dispatch_open_plugin_catalog_sync | 改造现有任务 | 现有 Beat 定时触发；无业务参数 | 为就绪空间汇总全部来源与范围，投递同步任务；未初始化存量不走新插件准入 |
| sync_open_plugin_catalog_source | 改造现有任务 | 调度 / 配置变化 / 有限重试；space_id、source_key；trigger、配置/采集代次拟扩展 | 按来源调用 Provider 或使用已有采集结果，提交来源结果；按代次拒绝晚到结果；重试同一来源工作，不另建 retry task |
| sync_bk_plugins | 改造现有任务 | 现有蓝鲸插件周期同步，按原租户范围采集 | 将成功/失败结果交给空间目录；复用租户级清单，不对每空间重复请求同一来源 |
| apply_automatic_classification_task（拟名） | **新增 1** | 来源提交后；intent 含 request_id、space_id、plugin_keys、policy_revision、directory_revision、ai_scope | 调 bkaidev，校验结果，提交自动分类；同请求只应用一次，过期结果丢弃 |
| initialize_space_catalog_task（拟名） | **新增 1** | 新空间创建成功后；space_id | 调共用初始化服务；按空间就绪状态幂等。失败后的再调度入口**待明确**，不能默认无限重试 |

**任务总数口径：** 本功能涉及 5 个注册任务＝3 个现有任务改造＋2 个新增任务。沿用目录同步、蓝鲸插件同步两个既有周期入口，不新增 Beat 入口。快速重试仍复用来源任务，低频恢复走既有巡检；新空间和 AI 的派发失败/重复执行恢复方案见 E04。

| 工作 | 是否另建 Celery task | 原因 |
| --- | --- | --- |
| 手动 AI 分类 | 按现有 plan 不新增 | Web 调用返回 patch/empty/error，前端修改编辑副本；网关/Web 与 LLM 超时的衔接仍待联调 |
| 引用更新 | 不新增 | 和流程最终写入处于同一事务，避免保存成功但当前引用仍旧 |
| 存量初始化命令 | 不新增 | 运维显式执行，按空间同步处理并输出结果；不靠 migrate 派发 |
| 来源快速重试 / 低频恢复 | 不单独计 task | 同一同步执行函数、不同触发原因；失败次数和时限写入 SourceSyncState |

现有目录同步 Beat 默认 cron 为 `*/30 * * * *`，来源于 env.py 的 OPEN_PLUGIN_CATALOG_SYNC_CRONTAB；蓝鲸插件同步沿用 SYNC_BK_PLUGINS_CRONTAB。这些是当前代码配置，不是新增用户开关。原 plan 的快速重试技术默认值为最多 3 次、10/20/40 秒、抖动不超过 20%、一轮不超过 5 分钟；耗尽后同一故障不重新开启快速重试。

## 迁移：1 个新命令，2 类数据准备

| 操作 | 执行位置 | 命令 / 参数 | 写入什么 |
| --- | --- | --- | --- |
| 表结构准备 | Interface | 现有 `python manage.py migrate` | 新模块 4 表＋旧插件表扩展迁移；只做 schema，无 RunPython 业务初始化 |
| 预览存量初始化 | Interface | 新命令 initialize_plugin_catalog；--space-id 可重复，或 --all-spaces；加 --dry-run | 不写业务数据；输出可选范围、来源分类、V4 关闭项、旧范围限制例外及老 API 诊断 |
| 执行存量初始化 | Interface | 同一新命令，不加 --dry-run | 变更记录中的旧管理配置快照、扩展旧表中的来源/设置、目录与统一引用、SpaceConfig 就绪状态；逐空间原子提交 |
| 新空间初始化 | Interface | 共用 initialize_space 服务；由新空间入口触发 | 默认开放且沿来源分类；由新增初始化任务调用；失败再调度方式待 E04 |
| 旧任务运行快照回填 | Engine | **已有** backfill_open_plugin_task_snapshots；--space-id、--start-id、--batch-size、--dry-run | TaskInstance.extra_info 的运行快照；按需回归，不计新增命令，也不代替空间目录初始化 |

拟定命令示例，尚未实现或运行：

```bash
# 先预览指定空间
python manage.py initialize_plugin_catalog --space-id 123 --dry-run
# 执行一个或多个空间
python manage.py initialize_plugin_catalog --space-id 123 --space-id 456
# 显式选择全部空间
python manage.py initialize_plugin_catalog --all-spaces
```

| 迁移结果 | 处理方式 |
| --- | --- |
| 空间已完成初始化 | 跳过，不重置管理员后续目录、推荐或启停决定 |
| 单空间失败 | 本空间回滚；其他成功空间保留；汇总失败并非零退出，可重跑 |
| 来源不完整 / 身份或分类无法可靠映射 | 明确报原因，不用半套数据标记就绪 |
| 尚未初始化 | 原读取路径继续；新管理写入/引用功能返回未就绪，不返回虚假的零插件或零引用 |
| 需要部署回退 | 结合版本与快照核对；没有设计新的“一键恢复旧配置”命令，不能覆盖上线后的人工决定 |

## 发布兼容与回退

| 阶段 | 必须完成的内容 | 兼容与进入下一步的条件 |
| --- | --- | --- |
| 1 表结构准备 | 新增 4 表、扩展 2 个旧模型字段/约束，复用 SpaceConfig；仅 schema migration | 不修改已发布旧迁移；不在 migrate 里抓来源、初始化业务或投递任务。唯一键变更及旧字段默认值待 E01 核定 |
| 2 兼容代码覆盖 | Web、Worker、旧 V4 管理写入口、schema/detail/快照读取、配置写入口全部适配 | 同一管理决定不能被新旧入口分别写。覆盖哪些实例、是否排空旧队列及滚动顺序见 E06；覆盖前不对该空间执行初始化 |
| 3 预览与手动初始化 | initialize_plugin_catalog --dry-run → 显式指定空间执行 → 核对可选集合、旧关闭项、来源分类和引用 | 存量未 ready 保留原读取；新管理写入/引用返回未就绪；ready 只表示初始化完成，不是产品总开关 |
| 4 功能切换与联调 | 管理页、两套画布和网关接通同一查询/写入服务；新空间自动初始化 | 旧 V4 路径委托统一服务；旧通用配置不能写新内部键。缓存失效及刷新时效需 E05 核定；不单独上线过滤导致存量不可读 |
| 5 运行验证与交付 | 存量详情、建任务、启动、调试及 Interface/Engine 两种隔离模式回归 | 内部 HTTP 故障、真正版本不可用与空间停用分开验证；真实 AI、CI 和目标环境结果分别记录 |

| 回退时的数据状态 | 允许写入发布说明的边界 |
| --- | --- |
| 尚未初始化 | 先核对旧代码是否兼容新增字段与约束；保留新增数据结构，不把反向删表当默认回退动作 |
| 已 ready，已产生新状态/分类/推荐 | 只能使用验证过兼容这些数据的回退版本；不能恢复旧配置快照而覆盖新的人工决定 |
| 队列仍有新版本消息 | 任务名称、参数和处理版本需对应；旧 Worker 能否处理或怎样排空须 E06 明确 |
| 需要恢复某空间 | 使用初始化结果和变更记录先做差异核对；本期不预设 force、自动回退命令或空间总开关 |

这是发布约束与核对顺序，不是已经验证的生产操作手册。E01、E05、E06 未定案前，不能宣称任意滚动升级/降级都安全。

待确认编号见 [04 实施与验收](../plans/2026-10-30-space-plugin-catalog-v2-team-plan.md)，事务与错误路径见 [05 调用时序](2026-10-30-space-plugin-catalog-v2-interactions-design.md)。
