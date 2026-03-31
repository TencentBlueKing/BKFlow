# BKFlow 发布影响范围与操作清单

- **Diff 链接**: https://git.woa.com/bkapps/BK-Flow/compare/d6a253840ab699ed9740b344634da0ddf4130a6e...767152970239e58404ddb30c8db9a3328f3d0b55?source_project_id=1325348&target_project_id=1325348
- **评估日期**: 2026-03-30
- **变更规模**: 389 文件，+32640 / -3153
- **适用场景**: 用于本次版本发布前评估、发布操作执行、发布后验证

---

## 一、功能影响范围

本次不是单一功能上线，而是一组联动发布，主要影响以下功能域。

### 1. 运营统计能力

- 新增平台运营统计能力，覆盖模板、任务、插件三个维度
- 支持总览、趋势、空间排行、模板排行、插件排行、失败分析、日报汇总等统计口径
- 系统会开始定时生成统计汇总数据
- 如需展示历史数据，除代码发布外还需要执行统计回填

业务影响：

- 发布后可以提供新的统计接口和统计展示能力
- 若未执行回填，统计数据默认仅覆盖发布后的增量数据
- 若采用独立统计库，系统会新增一套统计数据存储和调度依赖

### 2. 凭证管理能力

- 空间凭证支持多种类型，如应用凭证、登录态凭证、Basic Auth、自定义凭证
- 凭证内容从普通存储切换为加密存储
- 凭证新增作用域控制，不再默认在所有模板和节点中通用
- 历史凭证会在迁移中被加密，并尝试自动识别类型
- 凭证支持更新，不再只支持创建

业务影响：

- 老凭证数据会被迁移处理，属于本次最高风险功能域
- 凭证的可用范围将受作用域规则影响，历史行为可能发生变化
- 若密钥配置异常，凭证读取、展示、执行都会受影响

### 3. 模板设计与任务执行能力

- 模板编辑节点时支持配置访问凭证
- 创建任务、按应用创建任务、无模板创建任务时支持传递凭证上下文
- mock 执行链路支持携带 mock 数据和凭证数据
- 模板与节点详情返回能力增强，便于对接和调试

业务影响：

- 节点鉴权能力更强，模板设计和任务执行链路更完整
- 模板调试、mock、正式执行的行为一致性提升

### 4. API 网关对外能力

- 获取模板详情支持 `plugin` 格式返回
- 获取模板详情支持返回 mock 数据
- 获取任务节点详情时可按参数返回节点快照配置
- 新增凭证更新接口
- API 网关文档和资源定义同步更新

业务影响：

- 对接方可以拿到更丰富的模板和节点配置数据
- 已对接 API 的调用方需要确认新增字段和新接口的兼容性

### 5. Webhook 事件能力

- 新增模板发布事件广播
- 新增任务暂停、恢复、撤销事件广播

业务影响：

- 下游 webhook 消费方会接收到更多事件类型
- 如果下游做了严格白名单、字段校验或事件映射，需要提前确认兼容性

### 6. 管理后台能力

- Django Admin 新增 engine 模块入口
- 可以从后台快速跳转到 engine 管理页面

业务影响：

- 多模块部署场景下的运维排障效率提升

### 7. 可观测性与链路追踪

- 任务执行和插件执行的 trace/span 关联能力增强
- 插件执行链路的父子关系和上下文传递更加完整

业务影响：

- 已接入 OTEL 的环境中，可观测性增强
- 若现网 trace 配置不完整，需要重点关注发布后的日志和链路异常

---

## 二、发布前准备

### 1. 配置项确认

发布前至少确认以下配置已在目标环境准备完成：

- `PRIVATE_SECRET`
  - **interface 和所有 engine 模块必须配置相同的值**，因为凭证加解密依赖此密钥
  - 至少 24 个 ASCII 字符（AES-192 密钥取前 24 位），推荐用 `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` 生成
  - 一旦有凭证数据被加密入库，**不可更换**，否则历史凭证无法解密
  - 若未配置，会 fallback 到 Django `SECRET_KEY`，但建议显式配置独立值
- `STATISTICS_ENABLED`
  - 建议 engine 模块先设为 `false`，待 interface 完成 migrate 后再改为 `true` 并重启 worker（避免统计表不存在时产生异常日志）
- `STATISTICS_INCLUDE_MOCK`
- `STATISTICS_DETAIL_RETENTION_DAYS`
- `STATISTICS_SUMMARY_RETENTION_DAYS`
- `STATISTICS_DAILY_SUMMARY_CRONTAB`
- `STATISTICS_PLUGIN_SUMMARY_DAY_CRONTAB`
- `STATISTICS_PLUGIN_SUMMARY_WEEK_CRONTAB`
- `STATISTICS_CLEAN_CRONTAB`
- `STATISTICS_DB_HOST`
- `STATISTICS_DB_PORT`
- `STATISTICS_DB_NAME`
- `STATISTICS_DB_USER`
- `STATISTICS_DB_PASSWORD`
- `BKAPP_ENABLE_OTEL_TRACE` 或等价 OTEL 配置项

确认统计库用的是哪个数据库：

```bash
python manage.py shell -c "
from django.conf import settings
stats_db = settings.DATABASES.get('statistics')
if stats_db:
    print(f'统计模块使用独立库: {stats_db[\"HOST\"]}:{stats_db[\"PORT\"]}/{stats_db[\"NAME\"]}')
else:
    default_db = settings.DATABASES['default']
    print(f'统计模块使用 default 库: {default_db[\"HOST\"]}:{default_db[\"PORT\"]}/{default_db[\"NAME\"]}')
"
```

### 2. 发布范围确认

本次发布不是单纯后端发布，必须确认以下组件同步更新：

- Web 服务
- Celery worker
- Celery beat
- 前端静态资源

### 3. 发布顺序说明（interface 与 engine 分批发布场景）

如果 interface 和 engine 不能同时发布，需遵循以下顺序：

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | 发布所有 engine 模块新代码 | engine 新代码的 `SecretSingleJsonField` 对明文数据解密失败时会 fallback 返回原值，兼容未迁移状态 |
| 2 | engine 环境变量 `STATISTICS_ENABLED=false` | 避免统计信号触发写入尚未创建的统计表，产生异常日志和队列堆积 |
| 3 | 重启 engine 的 worker 进程 | 使新代码和环境变量生效 |
| 4 | 发布 interface 模块新代码 | — |
| 5 | 在 interface 上执行 `python manage.py migrate` | 凭证加密迁移（0009）此时执行，所有 engine 已能正确解密 |
| 6 | 如有独立统计库，执行 `python manage.py migrate --database=statistics` | 创建统计表 |
| 7 | engine 环境变量改为 `STATISTICS_ENABLED=true`，重启 worker | 统计表已就绪，开始正常采集 |

**禁止反向操作**：不可先发 interface + migrate 后再发 engine，因为旧版 engine 代码的 `JSONField` 无法解密已加密的凭证数据，会导致所有依赖凭证的插件执行失败。

### 4. 下游依赖确认

- webhook 消费方已知晓新增事件
- API 对接方已知晓模板详情、节点详情、凭证接口的能力增强
- 若启用独立统计库，数据库资源已提前准备

---

## 三、发布前备份指令

本次最建议备份的对象是凭证相关数据，因为其涉及历史数据迁移、加密和类型识别。

### 1. 优先推荐：整库备份

适用于正式环境，最稳妥。

```bash
mysqldump -h <db_host> -P <db_port> -u <db_user> -p \
  --single-transaction --routines --triggers --default-character-set=utf8mb4 \
  <db_name> > bkflow_full_backup_$(date +%F_%H%M%S).sql
```

### 2. 最小建议：备份高风险表

建议至少备份以下表：

- `space_credential`
- `space_credentialscope`
- `django_migrations`

命令如下：

```bash
mysqldump -h <db_host> -P <db_port> -u <db_user> -p \
  --single-transaction --default-character-set=utf8mb4 \
  <db_name> space_credential space_credentialscope django_migrations \
  > bkflow_credential_backup_$(date +%F_%H%M%S).sql
```

### 3. 可选：附带备份模板与任务主表

如果希望在排查凭证联动问题时保留更多上下文，可追加备份：

- `template_template`
- `task_taskinstance`

```bash
mysqldump -h <db_host> -P <db_port> -u <db_user> -p \
  --single-transaction --default-character-set=utf8mb4 \
  <db_name> \
  space_credential space_credentialscope django_migrations \
  template_template task_taskinstance \
  > bkflow_release_core_backup_$(date +%F_%H%M%S).sql
```

### 4. 如果启用了独立统计库

若统计库已存在历史数据或已在预发环境试跑，也建议额外备份：

```bash
mysqldump -h <statistics_db_host> -P <statistics_db_port> -u <statistics_db_user> -p \
  --single-transaction --default-character-set=utf8mb4 \
  <statistics_db_name> > bkflow_statistics_backup_$(date +%F_%H%M%S).sql
```

### 5. 备份前后检查命令

确认关键表存在：

```bash
mysql -h <db_host> -P <db_port> -u <db_user> -p -D <db_name> -e "SHOW TABLES LIKE 'space_credential';"
mysql -h <db_host> -P <db_port> -u <db_user> -p -D <db_name> -e "SHOW TABLES LIKE 'space_credentialscope';"
mysql -h <db_host> -P <db_port> -u <db_user> -p -D <db_name> -e "SHOW TABLES LIKE 'django_migrations';"
```

确认备份文件已生成：

```bash
ls -lh bkflow_*backup_*.sql
```

快速确认备份中包含凭证表结构或数据：

```bash
rg "INSERT INTO `space_credential`|CREATE TABLE `space_credential`" bkflow_credential_backup_*.sql
```

---

## 四、发布操作步骤

### 1. 发布代码

按现网发布方式更新以下内容：

- Web 代码版本
- Worker 代码版本
- Beat 代码版本
- 前端静态资源版本

### 2. 执行数据库迁移

默认库迁移：

```bash
python manage.py migrate
```

如果启用了独立统计库，执行：

```bash
python manage.py migrate --database=statistics
```

建议随后检查迁移状态：

```bash
python manage.py showmigrations space
python manage.py showmigrations statistics
python manage.py showmigrations --database=statistics statistics
```

### 3. 重启进程

至少重启以下进程：

- Django Web
- Celery worker
- Celery beat

原因：

- 统计模块依赖异步任务和定时任务
- 新环境变量需要进程重载
- webhook、trace、凭证、apigw 增强逻辑均在运行时生效

### 4. 视情况执行统计回填

如果需要上线后立即看到历史统计数据，需要执行回填。

全量回填：

各回填类型在哪里执行：

| 回填类型 | 执行位置 | 说明 |
|---------|---------|------|
| `--type=template` | **interface 模块执行一次** | 模板数据只存在于 interface 库 |
| `--type=task` | **每个 engine 模块各执行一次** | 任务数据分散在各 engine 独立库，回填时自动写入 `engine_id` 标识来源 |
| `--type=summary` | **interface 模块执行一次** | 从统计库聚合已回填的模板和任务数据生成日报汇总 |
| `--type=all` | **不建议使用** | 会在 engine 上多跑一次无效的 template 回填（0 条），在 interface 上多跑一次无效的 task 回填（0 条） |

推荐执行顺序：

```bash
# Step 1: 在 interface 模块回填模板统计
python manage.py backfill_statistics --type=template --batch-size=100

# Step 2: 在每个 engine 模块分别回填任务统计
# （各 engine 自动通过 BKFLOW_MODULE_CODE 写入对应的 engine_id）
python manage.py backfill_statistics --type=task --batch-size=100

# Step 3: 等 Step 1 和 Step 2 全部完成后，在 interface 模块生成汇总
python manage.py backfill_statistics --type=summary --date-start=2026-03-01 --date-end=2026-03-30
```

按空间分批回填（适用于数据量大的环境）：

```bash
# interface 模块
python manage.py backfill_statistics --type=template --space-id=<space_id> --batch-size=100

# 各 engine 模块
python manage.py backfill_statistics --type=task --space-id=<space_id> --batch-size=100
```

如需使用异步并行模式（需 Celery worker 已启动）：

```bash
python manage.py backfill_statistics --type=task --parallel --batch-size=100
```

回填后验证：

```bash
python manage.py shell -c "
from bkflow.statistics.models import TemplateStatistics, TaskflowStatistics
from bkflow.statistics.conf import StatisticsSettings
db = StatisticsSettings.get_db_alias()
print(f'统计库: {db}')
print(f'TemplateStatistics: {TemplateStatistics.objects.using(db).count()} 条')
print(f'TaskflowStatistics: {TaskflowStatistics.objects.using(db).count()} 条')
"
```

建议：

- 先小环境验证
- 生产优先按空间分批执行
- 严格按 template → task → summary 顺序执行，summary 依赖前两者的数据

---

## 五、发布后验证项

### 1. 凭证功能验证

- 可以创建凭证
- 可以更新凭证
- 老凭证可以正常展示和使用
- 不同类型凭证展示正确
- 作用域为 `all`、`part`、`none` 时行为符合预期
- 模板节点中可以正确选择凭证
- 任务执行时凭证可以被正常传递和解析

### 2. 统计功能验证

- 统计路由和接口可访问
- 总览接口返回结构正确
- 趋势、排行、失败分析接口可返回结果
- 无数据时返回空结果而不是异常
- 定时任务开始按预期调度

### 3. API 网关验证

- 模板详情支持 `format=plugin`
- 模板详情按应用查询正常
- `with_mock_data` 返回结果正常
- 任务节点详情传入 `include_snapshot_config=true` 后返回节点快照配置
- 凭证更新接口可正常工作

### 4. Webhook 验证

- 模板发布会触发 `template_release`
- 任务暂停会触发 `task_paused`
- 任务恢复会触发 `task_resumed`
- 任务撤销会触发 `task_revoked`

### 5. 管理后台验证

- `bkflow_admin` 可访问
- Engine 模块列表展示正常
- 跳转到 Engine Django Admin 的入口可用

### 6. 可观测性验证

- 任务执行无明显 trace 相关错误日志
- 插件执行链路正常
- 若对接 OTEL，链路信息可以正常采集或至少不影响主流程

### 7. 推荐执行的测试命令

```bash
pytest tests/interface/credential -q
pytest tests/interface/statistics -q
pytest tests/interface/apigw/test_create_task.py -q
pytest tests/interface/apigw/test_get_task_node_detail.py -q
pytest tests/interface/apigw/test_get_template_detail.py -q
pytest tests/interface/admin/test_engine_admin_portal.py -q
```

若仅执行一组精简回归：

```bash
pytest tests/interface/credential tests/interface/statistics tests/interface/apigw -q
```

---

## 六、风险说明

### 1. 最高风险：凭证迁移与加密

风险来源：

- 历史凭证内容会被加密
- 系统会尝试自动识别凭证类型
- 作用域规则变化后，历史凭证可用性可能变化

可能问题：

- 凭证迁移后无法解密
- 类型识别与预期不一致
- 老模板或老任务引用的凭证在新规则下不可用

重点建议：

- 发布前务必做数据库备份
- 发布后优先抽样验证历史凭证

### 2. 中高风险：统计模块上线后无历史数据

风险来源：

- 统计功能依赖回填才能看到历史数据
- worker / beat 未同步更新时，统计采集和汇总可能不生效
- 多 engine 部署场景下，任务数据分散在各 engine 独立库，遗漏某个 engine 的回填会导致统计数据不完整

重点建议：

- 发布前明确是否需要历史数据
- 若需要，提前规划回填窗口和批量大小
- 回填任务统计时必须在**每个 engine 模块**分别执行，不可只在 interface 或某一个 engine 上执行
- 严格按 template → task → summary 顺序执行

### 3. 中风险：interface 与 engine 发布顺序不当导致凭证读取失败

风险来源：

- 凭证加密迁移（migration 0009）会将数据库中的凭证明文加密为密文
- 旧版 engine 代码的 `JSONField` 无法解密已加密的数据
- 新版 engine 代码的 `SecretSingleJsonField` 向下兼容明文数据（解密失败时 fallback 返回原值）

重点建议：

- **必须先发 engine 再发 interface + migrate**，不可反向操作
- engine 先发后凭证读取不受影响（兼容明文）
- interface migrate 后凭证变为密文，此时 engine 已能正确解密

### 4. 中风险：前后端与异步进程版本不一致

风险来源：

- 前端页面、后端接口、静态资源、worker 逻辑都发生了变化

重点建议：

- 本次必须整包发布
- 不建议只发 Web 或只替换后端代码

### 5. 中风险：Webhook 下游兼容性

风险来源：

- 下游系统会收到更多事件类型

重点建议：

- 发布前通知下游
- 发布后观察 webhook 消费失败率和告警

---

## 七、建议执行顺序

### 同时发布场景

1. 备份整库，或至少备份凭证相关高风险表
2. 更新所有模块环境变量（`PRIVATE_SECRET` 各模块必须一致）
3. 发布代码与静态资源（interface + 所有 engine 同时更新）
4. 执行数据库迁移（`python manage.py migrate`，如有独立统计库加 `--database=statistics`）
5. 重启 Web、worker、beat
6. 先验证凭证与网关核心能力
7. 再验证统计接口
8. 按需执行统计回填（template 在 interface，task 在每个 engine，summary 最后在 interface）
9. 观察日志、任务调度、数据库写入与 webhook 消费情况

### 分批发布场景（先 engine 后 interface）

1. 备份整库，或至少备份凭证相关高风险表
2. 更新所有 engine 模块环境变量（`PRIVATE_SECRET` 与 interface 一致，`STATISTICS_ENABLED=false`）
3. 发布所有 engine 模块新代码，重启 worker
4. 验证 engine 任务执行正常（新代码兼容明文凭证）
5. 发布 interface 模块新代码
6. 在 interface 执行 `python manage.py migrate`（凭证加密迁移在此步执行）
7. 如有独立统计库，执行 `python manage.py migrate --database=statistics`
8. 重启 interface 的 Web、worker、beat
9. 验证凭证创建、更新、历史凭证展示和使用正常
10. 所有 engine 改 `STATISTICS_ENABLED=true`，重启 worker
11. 执行统计回填：interface 跑 template → 每个 engine 跑 task → interface 跑 summary
12. 观察日志、任务调度、数据库写入与 webhook 消费情况

