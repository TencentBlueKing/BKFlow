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

尚未覆盖真实登录、浏览器页面、网关、第三方插件、通知和 Webhook HTTP 投递，也不等于目标环境已验收。
目标环境需核对 broker、队列和正常退出宽限时间，beat 保持单实例，保留旧镜像并先小批量切换 worker。
