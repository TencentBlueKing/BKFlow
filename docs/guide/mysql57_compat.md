# MySQL 5.7 兼容补丁

Python 3.11 升级同时将 Django 升到了 4.2。Django 4.2
[移除了 MySQL 5.7 支持](https://docs.djangoproject.com/en/4.2/releases/4.2/#dropped-support-for-mysql-5-7)，
因此连接 MySQL 5.7.20 会报 `MySQL 8 or later is required`。
该错误发生在 Django 初始化数据库连接时。

BKFlow 默认使用局部兼容后端 `bkflow.db.mysql57`，允许已有的 MySQL 5.7.20+ 部署继续运行。
它是应用维护的过渡兼容层，不改变 Django 官方的数据库支持范围。

## 部署方式

部署包含该补丁的应用版本即可生效，无需环境变量开关。
应用在加载完平台、模块和本地数据库配置后，统一将原生 MySQL 后端替换为兼容后端，
保留地址、账号、数据库名、连接选项等配置。接口模块和独立引擎模块均适用；SQLite 和其他自定义后端不会被替换。
Web、worker、beat 和迁移进程使用相同配置入口。通过正常发布步骤执行迁移；
补丁本身没有新增迁移、数据转换或队列格式变更。

兼容后端仅支持 Django 4.2 系列；更换 Django 系列后使用该后端会明确报配置错误。
MySQL 最低版本保持为本次验证的 5.7.20，低于该版本仍会拒绝连接。
原有 MySQL 8 与 MariaDB 的 SQL 生成逻辑、MariaDB 最低版本检查保持不变。

## 为什么不只关闭版本检查

补丁恢复了 Django 4.1 中的两处 MySQL 5.7 兼容行为：

- 正则查询使用 `REGEXP` / `REGEXP BINARY`，避免 MySQL 8 才提供的 `REGEXP_LIKE`。
- 无表且带条件的 `SELECT` 补上 `FROM DUAL`。

真实 MySQL 5.7.20 已验证：仅放行版本检查后，这两类原生 SQL 仍然会报错。
兼容后端保留 Django 对窗口函数、`SKIP LOCKED`、`NOWAIT` 等能力的版本判断，不能让 5.7 获得 MySQL 8 的功能。

## 已验证范围

2026-10-22，在独立本地 MySQL 5.7.20 上验证。组合为 Python 3.11.10、Django 4.2.30、
bamboo-pipeline 4.0.6、bamboo-engine 3.0.7、bkflow-django-webhook 2.0.1、PyMySQL 1.1.1。
数据库开启 `STRICT_TRANS_TABLES` 和 `ONLY_FULL_GROUP_BY`。

- 原生 Django 后端复现同一 `NotSupportedError`；不设置任何兼容开关时，接口和引擎均自动适配并正常连接。
- 接口模块、引擎模块分别从空库执行全部迁移成功，包含 Bamboo、Webhook 和周期任务依赖的迁移。
- 9 项数据库探针通过：原错误复现、单纯放行的缺口、CRUD/JSON、正则、无表查询、聚合/子查询、
  行锁/事务回滚、字段新增/改名/删除、冲突更新。
- 移除开关后，接口侧 184 项回归通过，含模板读取 `get_template_data`、模板模型、回调入口、凭证读写及兼容后端边界检查；
  引擎侧 99 项通过，含任务模型、节点操作、周期任务部分更新和时区处理。
- 另外验证其他 Django 系列不能静默沿用补丁；完整安装环境的依赖一致性检查通过。

这些结果覆盖数据库访问和针对性应用回归，没有重新执行 MySQL 5.7 上的完整 worker 滚动切换、
积压消息接续和真实外部插件闭环。此前 MySQL 8 的切换记录不能替代该项验证。
后续升级 Django、引擎或其他会生成 SQL 的依赖时，需重新检查 5.7 兼容性。

## 后续维护

数据库切换到 MySQL 8 后，兼容后端会使用 Django 原有的 MySQL 8 SQL 生成逻辑，无需修改部署配置。
当所有部署均不再使用 MySQL 5.7 时，可以另行移除兼容后端，并完成验证。
