# Python 3.11 与 bamboo-pipeline 4.0 LTS 升级

本次使用 Python 3.11.10、Django 4.2.30、Celery 5.3.6，以及已在 PyPI 发布的
[bamboo-pipeline 4.0.6](https://pypi.org/project/bamboo-pipeline/4.0.6/) 和
[bamboo-engine 3.0.7](https://pypi.org/project/bamboo-engine/3.0.7/)。4.0.6 精确依赖 engine 3.0.7，
两者要求 Python >=3.11,<3.12。本次应用依赖中不再使用本地补齐版本。

## 为什么不能直接换成官方 4.0.5

本次 BKFlow 基线为 `75879886d914bc91bbefac411d703eeadb11cc94`，依赖 pipeline 3.29.11rc1 / engine 2.11.5rc1。
官方 pipeline 4.0.5 / engine 3.0.6 尚缺少该基线已经使用的子画布、循环控制，以及部分诊断、恢复和 Mako 安全修复。
实际启动接口模块会在 `PWE.SubCanvas` 处失败；直接降级功能或隐藏导入错误无法保证已有任务继续运行。

上述能力已通过 [bamboo-engine PR #316](https://github.com/TencentBlueKing/bamboo-engine/pull/316)
补入 `bamboo_pipeline_4.0_lts`，保留 LTS 的 Python/Django 适配和依赖范围，并发布在 4.0.6 / 3.0.7 中。
不要用原版 4.0.5 / 3.0.6 替换本次固定版本。

## 应用适配范围

- 将 Django 删除的翻译、路由、字符转换和 Signal 参数替换为支持的接口。
- 更新 django-filter 的 `filterset_class`，保留原筛选行为；为插件管理路由设置独立 basename，URL 不变。
- 修复 DRF 使用普通字典后，周期任务更新时遍历中删除字段的问题；合并配置时保留未修改字段。
- 显式导入 `pytz`，保留定时节点已经存储的 datetime/tzinfo 对象形式及原有时区处理语义。
- 保留 blueapps 4.16.rc3 和 APIGW 4.2.0，更新 Python 3.11 所需依赖；CI 运行版本改为 3.11。
- 保留 django-bkvision 1.2.0，通过 `bkflow.statistics.bkvision_urls` 调用 SDK 原有视图。
  SDK 1.2.0–1.2.4 仍导入 `django.conf.urls.url`；应用适配不修改 Django 全局行为，也不更换 SDK 鉴权视图。

Celery 5.3.6 / billiard 4.2.1 / kombu 5.3.7 固定为本次验证组合。bamboo 本身并不强制 Celery 5.3，
但此前 Python 3.11 + Celery 5.2.3 的异常任务探针已复现 traceback 日志的 `co_positions` 错误，因此没有保留该组合。

## Webhook 与数据库

采用 `bkflow-django-webhook==2.0.1`，它支持 Django 4.2，且与旧包 1.2.5 使用相同的业务字段。
不要在此次升级中顺带换到 2.0.2：它新增必填字段 `enable_webhook`，迁移后旧包创建 Webhook 会报
`1364: Field 'enable_webhook' doesn't have a default value`，本地已复现。

最终组合没有新增 BKFlow 迁移。旧环境数据库升级时只有 django-celery-beat 0016–0019 待应用；
在本次 MySQL 8.0.46 上，四条 `sqlmigrate` 均为 no-op，仅更新迁移记录。
依然应使用正常发布步骤执行 `migrate`，不能跳过迁移检查。
没有对流程实例、上下文、执行数据或队列消息做批量格式转换。回滚演练保留了已升级的数据库，没有逆向迁移。

## 本地构建与复现

安装正式依赖，不再需要构建 Bamboo 本地 wheel：

```bash
uv venv --python 3.11.10 .venv
uv pip install --python .venv/bin/python -r requirements.txt
uv pip check --python .venv/bin/python
```

`django-bkvision==1.2.0` 需使用项目登记的腾讯内部 PyPI 源或已验证的原始 wheel；
其余依赖可从公共源获取。公共 GitHub CI 会跳过该内部包，本次本地完整启动验证实际安装了它。

切换探针在 `tests/upgrade/rehearsal.py`。它会拒绝连接本次专用地址以外的数据库和队列：
MySQL `127.0.0.1:13306/bkflow_lts_engine`、Redis `127.0.0.1:16379`、RabbitMQ `127.0.0.1:15673`，模块代码为 `lts`。
执行前必须使用显式的本地配置，不继承项目现有 `.envrc` 或生产环境变量。
复现配置和分阶段命令见 [本地切换探针说明](../../tests/upgrade/README.md)。
`tests/upgrade/interface_fixture.py` 只在回环地址提供空间变量、模板和事件响应；它不代表真实外部平台。

基本切换顺序：

1. 旧解释器、旧应用依赖执行迁移，使用真实 threads worker 创建任务，等待回调、定时和失败状态落库。
2. 对旧 worker 发出 TERM，确认正常退出和尚未执行的 ETA 消息归还队列；退出后由旧应用再发送普通任务。
3. 新解释器执行迁移，启动新 worker，在同一数据库和队列中回调、重试并等待任务完成。
4. 反向重复，使用新应用创建的数据和消息回切旧 worker，保留升级后的数据库。
5. 新旧 worker 同时在线，分别由新旧应用发任务，检查双方均实际消费并完成任务。

## 发布边界

本地结果支持对已覆盖场景采用正常滚动发布，不要求停机批量迁移流程数据。正式发布仍需：

- 使用本次固定的正式 LTS 包，完整构建检查包含 BKVision SDK。
- 在实际目标环境核对 MySQL、RabbitMQ、进程退出宽限时间、队列和 beat 配置。beat 保持单实例，worker 使用正常退出。
- 保留旧镜像，先小批量切换 worker，观察回调、定时、重试和子任务，再继续切换。

这次没有操作远程环境，也没有验证真实网关、第三方插件、通知或 Webhook HTTP 投递。
本地 RabbitMQ 为 4.3.6，单独开启了旧客户端所需的 `transient_nonexcl_queues` 兼容选项；它不代表目标环境的 broker 配置。
详细证据见 [2026-10-20 本地验证记录](../plans/2026-10-20-python311-lts-upgrade.md)。
