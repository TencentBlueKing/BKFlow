# 03 后台任务与迁移清单

[返回总览](2026-10-30-space-plugin-catalog-v2-review-design.md) · [模型与接口](2026-10-30-space-plugin-catalog-v2-contracts.md) · [实施与验收](../plans/2026-10-30-space-plugin-catalog-v2-team-plan.md)

## Celery：建议新增 2 个，改造 2 个

**这是待技术评审的拆分建议。** 原 plan 明确了同步、自动 AI 和新空间初始化职责，没有明确 Celery 注册函数数量。下面复用现有调度，形成可估算的最小方案；不增加独立服务或 Engine 队列。

| 任务 | 新增 / 改造 | 触发与拟定参数 | 执行内容 / 去重依据 |
| --- | --- | --- | --- |
| dispatch_open_plugin_catalog_sync | 改造现有任务 | 现有 Beat 定时触发；无业务参数 | 为就绪空间汇总全部来源与范围，投递同步任务；未初始化存量不走新插件准入 |
| sync_open_plugin_catalog_source | 改造现有任务 | 调度 / 配置变化 / 有限重试；space_id、source_key；trigger、配置/采集代次拟扩展 | 调用全类型 Provider，提交来源结果；按代次拒绝晚到结果；重试同一来源工作，不另建 retry task |
| apply_automatic_classification_task（拟名） | **新增 1** | 来源提交后；intent 含 request_id、space_id、plugin_keys、policy_revision、directory_revision、ai_scope | 调 bkaidev，校验结果，提交自动分类；同请求只应用一次，过期结果丢弃 |
| initialize_space_catalog_task（拟名） | **新增 1** | 新空间创建成功后；space_id | 调共用初始化服务；按空间就绪状态幂等。失败后的再调度入口**待明确**，不能默认无限重试 |

**任务总数口径：** 该功能目标为 4 个注册任务＝2 个既有任务改造＋2 个拟新增任务。Beat 建议继续使用现有 1 个周期入口；快速重试用同一来源任务的延迟投递，低频恢复走正常巡检。最终 task 名、消息字段和路由需技术评审，不写成已落地数量。

| 工作 | 是否另建 Celery task | 原因 |
| --- | --- | --- |
| 手动 AI 分类 | 按现有 plan 不新增 | Web 调用返回 patch/empty/error，前端修改编辑副本；网关/Web 与 LLM 超时的衔接仍待联调 |
| 引用更新 | 不新增 | 和流程最终写入处于同一事务，避免保存成功但当前引用仍旧 |
| 存量初始化命令 | 不新增 | 运维显式执行，按空间同步处理并输出结果；不靠 migrate 派发 |
| 来源快速重试 / 低频恢复 | 不单独计 task | 同一同步执行函数、不同触发原因；失败次数和时限写入 SourceSyncState |

现有 Beat 默认 cron 为 `*/30 * * * *`，来源于 env.py 的 OPEN_PLUGIN_CATALOG_SYNC_CRONTAB；这是当前代码配置，不是新增用户开关。原 plan 的快速重试技术默认值为最多 3 次、10/20/40 秒、抖动不超过 20%、一轮不超过 5 分钟；耗尽后同一故障不重新开启快速重试。

## 迁移：1 个新命令，2 类数据准备

| 操作 | 执行位置 | 命令 / 参数 | 写入什么 |
| --- | --- | --- | --- |
| 建新表 | Interface | 现有 `python manage.py migrate` | 新 app 的 0001_initial；只做 schema，无 RunPython 业务初始化 |
| 预览存量初始化 | Interface | 新命令 initialize_plugin_catalog；--space-id 可重复，或 --all-spaces；加 --dry-run | 不写业务数据；输出可选范围、来源分类、V4 关闭项、旧范围限制例外及老 API 诊断 |
| 执行存量初始化 | Interface | 同一新命令，不加 --dry-run | 旧配置快照、来源清单、目录/管理设置、当前引用和就绪记录；逐空间原子提交 |
| 新空间初始化 | Interface | 共用 initialize_space 服务；由新空间入口触发 | 默认开放且沿来源分类；任务包装采用上面的待评审建议 |
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

## 发布顺序和待定项

**表结构 → 预览 → 手动初始化 → 核对可选集合 / 引用 → 管理页、两套画布与网关接通 → 存量运行回归。** 默认 migrate 不做存量初始化，新周期同步不能提前把存量当新插件审核。

| 待明确事项 | 已有边界，继续保留 |
| --- | --- |
| Celery 注册函数、消息参数及新空间失败再调度入口 | 按上述 2 新增＋2 改造评审；不擅自增加无限重试或新周期任务 |
| 初始化进度的权威字段与具体事务顺序 | 保持每空间原子、重跑不覆盖人工决定；模型不重复维护两份无规则的进度 |
| 手动 AI 的请求时限 | 原 plan 连接 5 秒、读取默认 60 秒；验证网关/Web 允许时限，不自行改成带任务轮询的新 API |
| 快捷改目录保存时机（第 6 项）、批量启用逐项目录确认（第 7 项）；联系字段/替换文案 | 继续暂定 / 建议；不由技术拆分代替产品确认 |
