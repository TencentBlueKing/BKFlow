# Python 3.11 / 4.0 LTS 本地升级验证记录

日期：2026-10-20。当前结论基于已发布的正式包：`bamboo-pipeline==4.0.6`、`bamboo-engine==3.0.7`。
本次从新的本地服务数据目录和旧版空数据库开始，完成升级、保留数据库的回滚、共存和周期派发验证。
未操作远程部署环境；生产环境验收仍需独立进行。

## 版本与环境

| 项目 | 旧版本 | 新版本 |
| --- | --- | --- |
| BKFlow 基线 | `75879886` | 同一基线加本次适配 |
| Python | 3.9.12 | 3.11.10 |
| Django | 3.2.25 | 4.2.30 |
| Celery | 5.2.3 | 5.3.6，billiard 4.2.1，kombu 5.3.7 |
| bamboo-pipeline | 3.29.11rc1 | 4.0.6，正式 PyPI 包 |
| bamboo-engine | 2.11.5rc1 | 3.0.7，正式 PyPI 包 |
| Webhook SDK | 1.2.5 | 2.0.1 |
| BKVision SDK | 1.2.0 | 1.2.0，应用内路由适配 |

MySQL 8.0.46、RabbitMQ 4.3.6、Redis 7.2.5 使用专用回环端口和全新数据目录。
新旧测试数据库分别命名，切换演练共用专用业务数据库。worker 使用 threads 模式，并发数为 2。
空间变量、周期任务模板和事件广播使用本地 HTTP 夹具；没有访问真实外部平台。

正式包安装在新建的 Python 3.11 虚拟环境，包含 BKVision SDK。完整依赖检查通过。
下载的 wheel 哈希与 PyPI 元数据相同，安装后的 engine 67 个、pipeline 514 个 Python 文件逐一匹配 wheel 内容。

| Wheel | SHA256 |
| --- | --- |
| bamboo_engine-3.0.7-py3-none-any.whl | `cb4310cba96b0ecb29a99886618c1bf5c1ce949c2a9065260edfa1772eef3252` |
| bamboo_pipeline-4.0.6-py3-none-any.whl | `d784e59079864cda23b85197dd845fc4059661cdbedccda9a54159bc95a0778a` |

## 正式包自动化回归

| 检查 | 结果 |
| --- | --- |
| 引擎 / plugin_service，含新增周期更新回归 | 695 passed，1 skipped |
| 接口、插件、配置、决策表、标签等，含完整 BKVision SDK | 2240 passed，1 skipped |
| 权限真实 MySQL 生命周期和迁移，独立进程 | 21 passed |
| interface / engine 启动检查与迁移检查 | 通过 |
| 修改文件 Black / Flake8、diff 空白检查 | 通过 |

合计 2956 passed、2 skipped。跳过项是原有测试标记；切换探针没有跳过。
Django 的既有 JSONField 默认值告警、索引弃用告警等仍存在，不等同于本次运行失败。

## 正式包切换结果

| 场景 | 旧 → 新 | 新 → 旧 |
| --- | --- | --- |
| 等待回调节点，切换后提交回调，核对回传数据 | 通过 | 通过 |
| 定时节点，读取已存 datetime / pytz 对象并接续 ETA 消息 | 通过 | 通过 |
| 失败 Python 节点，切换后修改输入重试并核对输出 | 通过 | 通过 |
| 生产者发送但尚未消费的普通任务 | 通过 | 通过 |
| 已保存的周期任务及 Asia/Shanghai 调度信息 | 通过 | 通过 |
| 子画布两轮循环，第一轮等待回调时切换，第二轮及父任务完成 | 通过 | 通过 |
| Webhook 配置跨版本读取、创建（升级后的同一数据库） | 通过 | 通过 |
| 实际 beat 读取另一版本保存的配置，派发并完成 BKFlow 周期流程 | 通过 | 通过 |

每个流程都检查持久化引擎状态及 BKFlow `is_finished`，同时校验回调/重试输出。
子画布父任务分别产生并完成两个真实子任务。周期流程由独立 beat 进程和正常的
`bkflow_periodic_task_start` 执行，每个配置生成 1 个完成的流程，`total_run_count == 1`。

共存测试中，新旧应用各发送 20 个任务；新旧 worker 各实际完成 20 个，40 个全部完成。
切换使用 TERM 正常退出，回滚保留新版本迁移后的数据库，没有还原数据库或重建流程实例。
本次验证支持上述场景采用正常滚动切换，不要求停机批量转换流程数据。

## 已处理的升级问题

1. 官方 pipeline 4.0.5 缺少当前 BKFlow 的 `SubCanvas` 等能力。补齐改动已合入
   [bamboo-engine #316](https://github.com/TencentBlueKing/bamboo-engine/pull/316)，并随 4.0.6 / 3.0.7 发布。
2. DRF 普通字典在周期任务更新时被遍历中删除，导致 `RuntimeError`；修复后保留部分配置合并语义。
3. 重复 router basename 和旧 `filter_class` 在升级后分别导致启动失败和筛选失效，已适配。
4. Webhook 2.0.2 新增必填列会使旧版本写入报 1364，已固定 2.0.1，正式包环境再次验证旧版可写。
5. 内部 BKVision SDK 1.2.0–1.2.4 仍依赖已删除的 `django.conf.urls.url`，通过应用路由转接保留原始 SDK 视图。
6. Python 3.11 + Celery 5.2.3 的异常任务探针曾复现 `co_positions` 日志错误；本次固定 Celery 5.3.6 组合。

## 数据库与复现

增量迁移只有 Celery Beat 0016–0019。本地 MySQL 8.0.46 的 `sqlmigrate` 全部为 no-op；
迁移更新记录，不转换任务数据。本次没有新增 BKFlow migration。
旧主干已有 bkoauth、space、template 的 `makemigrations --check` 差异；新环境还会提示 Webhook
索引的状态表示差异，没有生成或应用这些无关迁移。正常发布仍应执行 `migrate` 并检查目标环境迁移计划。

复现脚本、固定的隔离配置和执行顺序见 [tests/upgrade/README.md](../../tests/upgrade/README.md)。
本次完整本地证据保存在工作区父目录 `official-rehearsal/`：
`manifest.json`、`new-installed.txt`、`forward.result.json`、`rollback.result.json`、
`nested-*.result.json`、`mixed.result.json`、`periodic-*.result.json`、`webhook.result.json` 和 `logs/`。
原始日志和本地生成的数据导出不进入应用代码仓库。

初轮启动脚本遇到符号链接路径重复、子进程已退出但等待回收而被误判存活两个脚本问题，已修正；
升级验证接续原有持久化数据完成，未通过重建任务绕过错误。

## 早期验证与目标环境边界

正式发包前曾使用本地补齐 wheel 执行旧版基线及 Bamboo 测试：旧引擎 694 passed / 1 skipped，
旧接口 1949 passed，旧插件独立进程 286 passed / 1 skipped；Bamboo 核心 697 passed / 1 skipped、
runtime / diagnostics 980 passed。这些是早期证据，正式包结论以上面的新环境结果为准。

初轮未覆盖真实登录、浏览器页面、网关、第三方插件、通知和 Webhook HTTP 投递，也不等于目标环境已验收。
本次后续评估仅关注升级带来的差异，普通发布的进程退出、资源故障及调度器交接不列为升级新增风险。

## 同日补充：依赖与响应兼容性

在初轮 PR `73c45ea0` 上发现并处理以下问题：

1. 周期任务部分更新已经正确落库，但响应中的 `config` 未合并，可能遗漏空间、作用域及流程树。
   恢复已有配置键的合并回写，不在遍历时增删键；新增实际视图响应测试，覆盖开启和关闭两种状态。
2. 远程定时节点用例在收集时生成十分钟后的时间，约二十九分钟后执行导致过期。
   固定被测插件时钟，并增加过期输入的拒绝检查。该失败不代表定时任务跨版本接续失败。
3. jsonschema 默认校验规则从 Draft 4 变为新版：同一 Python 节点在旧环境成功，新环境因布尔
   `exclusiveMinimum` 报 SchemaError。应用入口和隔离执行器均保留旧默认草案，显式版本仍受尊重。
   执行器继续使用 `-I` 独立运行，不引入项目路径，也不修改第三方模块的全局默认规则。

Webhook 复核使用从 PyPI 校验的原始 1.2.5 / 2.0.1 wheel，分别与安装目录的 24 个 Python 文件匹配。
两版四条 migration 的操作一致；实质变更为版本声明、翻译和 Signal 接口及模型索引的声明方式。
模型业务字段、密文处理、消息参数、任务名和重试逻辑一致。2.0.1 的模型索引声明与既有 migration
状态差异依然存在，但本次不生成额外迁移，原索引仍在数据库中。

| Webhook 补充场景 | 旧 1.2.5 → 新 2.0.1 | 新 2.0.1 → 旧 1.2.5 |
| --- | --- | --- |
| 无消费者时发送通知，另一版本消费后实际 HTTP 投递 | 通过 | 通过 |
| Basic / Bearer 鉴权及自定义加密请求头 | 通过 | 通过 |
| 首次 HTTP 503 后自动重试，写入 503 / 200 两条历史 | 通过 | 通过 |
| 已失败并进入等待的重试消息，切换后继续投递 | 通过 | 通过 |
| 同一数据库内解密、更新配置，再由原版本读取 | 通过 | 通过 |

合计 6 条排队通知、2 条等待重试通知，接收端收到 12 次实际 HTTP 请求。
同时校验投递 ID、事件载荷、鉴权头、加密存储与解密结果，以及数据库投递历史；
接收端只监听 `127.0.0.1:19998`。没有向真实业务方发送通知，也无需修改或重新发布 Webhook 包。

完整依赖检查覆盖 137 个已安装包；Blueapps 4.16rc3 与本次 OpenTelemetry 组合的
`LazyBatchSpanProcessor`、Django/Celery/requests/Redis/数据库采集初始化、内存导出和 OTLP Protobuf 编码通过。
导出器接收端由内存夹具替代，不代表真实监控服务已验收。

补充证据保存于工作区父目录的 `upgrade-followup/`，包括 Webhook wheel 校验、各阶段结果、
HTTP 接收记录、jsonschema 新旧对照及回归日志。可提交的探针为 `tests/upgrade/webhook_rehearsal.py`。

修复后的完整回归为引擎 / plugin_service **697 passed、1 skipped**，接口 / 插件等
**2245 passed、1 skipped**，独立权限 MySQL 回归 **21 passed**，合计 **2963 passed、2 个原有 skipped**。
单独的依赖回归 346 passed、1 skipped 已包含在完整回归中，不重复累计。
这些是本地当前代码结果；远程 CI 状态以 PR 当前提交的检查结果为准。
