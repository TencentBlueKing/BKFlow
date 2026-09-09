# Token 授权统一存储 Implementation Plan

> **当前状态：** Task 1 与 Task 2 的本地实施和验证已完成，已完成步骤仅作为执行台账保留，不应重复执行；Step 7 的审查、推送、TAPD、新提交 CI 和测试 MySQL 关闭由控制器负责。

**Goal:** 所有 Token 统一从 TokenGrant 读取授权，发布 migrate 自动回填存量并删除主表冗余授权字段，保持旧接口协议。

**Architecture:** 唯一 Token 主记录关联一到多条不可变明细，集合摘要统一复用。追加数据迁移及自动生成结构迁移；维护窗口停止旧进程写入，先回填校验后清理旧列。

**Tech Stack:** Python 3.9、Django 3.2.25、MySQL 8.0.46、pytest、DRF。

**Spec:** [统一存储设计](../specs/2026-09-09-unified-token-storage-design.md)

## Global Constraints

- 保持所有已批准旧 HTTP 请求/响应/错误/auth/日期时间编码协议；不新增接口。
- 单项与组合授权都只存入 TokenGrant；Token 不保留 resource_type/resource_id/permission_type 字段或写入兼容层。
- 存量 token 值、用户、空间、有效期和原三元组身份不变；迁移涵盖过期和失效资源记录，不调用外部资源服务。
- 原始 grants 1–32 项、旧字段优先、完全校验后原子签发、完整集合复用、整张撤销、撤销不可续活保持不变；组合申请默认开启，显式 false 可关闭。
- 只追加迁移；结构操作由 Django makemigrations 自动生成；数据回填使用 makemigrations --empty 生成的独立 RunPython 迁移和历史模型。
- 所有 commit 使用 --story=138057563，追加原 ai/docs-token-authorization 分支和 PR #913；不合并、不部署、不启用生产开关。
- 两连接 MySQL 及 MigrationExecutor 用例须在独立 pytest 进程运行；覆盖率 append；保留测试失败传播。

## Context and validation commands

基线 `660f2005c7087db647c980cc68043611d469ad99` 已验证接口1639、Linux CI2211通过/1既有跳过。复用当前干净工作树，无需重跑基线或重装依赖。

工作目录 `/Users/dengyh/Projects/bk-flow/.worktrees/docs-token-authorization`。Python 使用 `direnv exec /Users/dengyh/Projects/bk-flow`；MySQL 专用端口33316，settings为 `/tmp/bkflow_composite_mysql_settings.py`，仅控制器启动/停止。测试命令模板：

```sh
direnv exec /Users/dengyh/Projects/bk-flow env PYTHONPATH=/tmp:$PWD PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 BKFLOW_MODULE_TYPE=interface BKFLOW_MODULE_CODE=interface python -m pytest -p django -p pytest_mock -p no:warnings -o addopts='' --ds=bkflow_composite_mysql_settings tests/interface/permission/test_grants.py tests/interface/permission/test_lifecycle.py tests/interface/permission/test_mysql_lifecycle.py
```

### Task 1: 统一模型、生命周期与可验证数据迁移

**Files:**
- Modify: `bkflow/permission/models.py`, `services.py`, `admin.py`。
- Create: `bkflow/permission/migrations/0006_*.py` 数据迁移及下一条自动生成结构迁移。
- Modify: `tests/interface/permission/test_grants.py`, `test_lifecycle.py`, `test_mysql_lifecycle.py`。
- Create: `tests/interface/permission/test_unified_migrations.py`。

**Interfaces:**
- Consumes: `Grant`, `canonical_grants`, `grant_hash`, `grant_set_hash` 的现有 v1 协议。
- Produces: 保留 `issue_token`, `renew_token`, `revoke_tokens`, `get_valid_token`, `iter_user_grants`, `Token.get_grants`, `Token.to_json`, `Token.verify` 签名；`Token.is_composite` 表示有效明细数大于一；存储统一。

- [x] Step 1: 先增加单项授权必须有明细且旧字段不存在的失败断言。其他非法集合用例仍真实写入损坏明细，验证 fail-closed。

```python
token = issue_token(1, "alice", (Grant("TEMPLATE", "001", "MOCK"),), 3600, False)
assert token.grants.count() == 1
assert token.grant_set_hash == grant_set_hash(token.get_grants())
assert not {"resource_type", "resource_id", "permission_type"} & {f.name for f in Token._meta.fields}
assert token.to_json()["resource_id"] == "001"
assert token.is_composite is False
```

- [x] Step 2: 跑上述测试观察基线失败；记录输出，再修改模型/服务。删除主表三字段和旧索引；只从明细计算完整集合；摘要非NULL；旧成功响应只能从单项重建。所有签发统一计算集合摘要并在同一事务 bulk_create 明细；复用保留主键锁顺序与最新有效期排序；撤销与汇总统一 EXISTS 明细过滤。get_grants 不依赖 is_composite，避免递归。

```python
digest = grant_set_hash(grants)
# 候选通过 digest、用户、空间和有效期检索，锁后仍比较全部 grants。
TokenGrant.objects.bulk_create(
    [TokenGrant(token=token, grant_hash=grant_hash(grant), **grant.as_dict()) for grant in grants]
)
```

- [x] Step 3: 在未更改已有迁移的前提下，先 `makemigrations permission --empty --name backfill_token_grants`，填入自包含历史模型 RunPython 正反向数据迁移；再运行 `makemigrations permission --noinput` 生成结构清理。生成命令通过与测试相同环境及 settings；只允许项目格式化改动生成的结构文件。

正向函数 `forwards(apps, schema_editor)` 与反向函数 `backwards(apps, schema_editor)` 均通过 `apps.get_model("permission", "Token")` / `TokenGrant` 获取历史模型，以 `schema_editor.connection.alias` 指定数据库。`migrations.RunPython(forwards, backwards, atomic=True)` 只做数据变更。正向先验证所有原组合集合，再逐票据取旧字段、清除意外旧明细、创建唯一明细、更新摘要并读回比对；反向先验证全部集合，单项写回旧字段/置NULL摘要/删除明细，多项恢复旧列空字符串并保留摘要与明细。异常必须使全部数据写入回滚。冻结摘要算法的具体形式：

```python
import hashlib
import json

def payload_hash(payload):
    serialized = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

fields = (token.resource_type, token.resource_id, token.permission_type)
item_digest = payload_hash(["v1", *fields])
set_digest = payload_hash(["v1", [list(fields)]])
```

迁移校验字段身份、唯一性、条目摘要与排序后集合摘要；不依赖运行时模型方法，不能输出 token 值。

- [x] Step 4: MigrationExecutor 真正执行 `0004→最新`、`0005混合→最新`、`最新→0005→最新`。预置活跃/过期/已删资源、`001`、大小写和Unicode；比较主表身份/时间和三元组。调用失败场景后证明旧字段仍在且事务回滚；重复回填不增条目；保留原组合损坏状态并中止，不重算摘要使其有效。迁移测试结束恢复最新结构。
- [x] Step 5: 调整本任务三份 permission 测试的 fixture/旧字段断言，对单项也覆盖明细失败整体回滚、损坏摘要、精确集合复用、同明细 AND、计数和并发。真实 MySQL worker仍独立连接、观测 performance_schema 锁等待，单项明细数量从0改1。
- [x] Step 6: 执行本任务focusedMySQL测试和permission迁移漂移检查；admin系统检查可在独立spec说明上下文中执行。提交精确文件，报告迁移命令/真实结果、通过项及留给Task2适配的旧fixture名单。

### Task 2: 全量旧协议回归、发布文档及交付

**Files:**
- Modify: 其余使用旧 Token ORM fixture/字段断言的 `tests/interface/`, `tests/decision_table/`, `tests/label/` 中实际命中文件；可新增 `tests/utils/token.py` 作为纯测试 fixture helper。
- Modify: `scripts/run_interface_unit_test.sh`、`docs/guide/token_authorization.md`、`docs/guide/space_config.md`、`docs/guide/system_access.md`、`docs/specs/2026-09-09-composite-token-design.md`、`docs/plans/2026-09-09-composite-token.md`、`.ai/rules/bkflow-permission.mdc`。
- Modify if storage text affected: `bkflow/apigw/docs/zh/apply_token.md`, `revoke_token.md`, `bkflow/apigw/management/commands/data/api-resources.yml`；通过 `bash scripts/apigw_docs.sh` 生成 zip。

**Interfaces:**
- Consumes: Task1最终模型及迁移；旧 HTTP 协议保持不变。
- Produces: 全量接口、独立迁移/并发、文档包、旧版迁移/回退及新 HEAD CI 证据。

- [x] Step 1: 在Task1完成后运行旧请求测试，记录旧fixture直接构造已删除字段的失败；只调整存储准备/检查，保留真实HTTP输入、响应、用户/空间、403/auth、时间编码断言。
- [x] Step 2: 如抽取fixturehelper，只写测试路径，用真实models一次事务创建唯一Token、摘要和全部明细，允许测试显式传token值/expired_time，不调用签发service来构造全部鉴权fixtures。

```python
with transaction.atomic():
    token = Token.objects.create(token=token_id, user=user, space_id=space_id,
                                 expired_time=expired_time, grant_set_hash=grant_set_hash(grants))
    TokenGrant.objects.bulk_create([
        TokenGrant(token=token, grant_hash=grant_hash(grant), **grant.as_dict()) for grant in grants
    ])
return token
```

- [x] Step 3: 扩展独立pytest入口：首先执行 `test_mysql_lifecycle.py` 与 `test_unified_migrations.py`，然后原套件忽略这两份文件并 `--cov-append`。迁移测试不可与正常用例并发修改同一测试数据库。
- [x] Step 4: 补旧APIGW单项请求复用真实迁移票据的验证（在迁移测试中用当前view/middleware或在独立临时库直接HTTP测试），重复旧请求不换token；新grants单项请求响应仍为grants。回归整票据撤销、复用/续期/清理以及多项完整性行为。
- [x] Step 5: 更新所有权威文档，删除双存储、NULL判别、免回填和可混用旧实例说法。说明自动回填顺序、维护窗口、全量旧记录不重签、失败停止、明确0005反向回退、开关只控制组合申请。更新旧spec/plan的状态并指向本次统一设计；同步权限规范模型描述，路由/认证配置保持不变。
- [x] Step 6: 执行实际 interface入口：

```sh
direnv exec /Users/dengyh/Projects/bk-flow env PYTHONPATH=/tmp:$PWD PYTEST_ADDOPTS='-o faulthandler_timeout=60 --ds=bkflow_composite_mysql_settings' sh scripts/run_interface_unit_test.sh
```

执行变更Python格式/导入/Flake8、`git diff --check`、Django check、permission迁移漂移；全项目漂移与已知space/template基线分开报告。校验102operation路由/auth/plugin不变、92zip文件与源码相同、相对链接和JSON示例。提交精确文件。
- [ ] Step 7（控制器负责）: 完成独立任务审查及本次改动最终审查，更新原 PR/TAPD，推送并核对新 HEAD Linux CI。不得把之前 `660f2005` 的绿色 CI 当作本次结果。保留工作树，关闭仅本任务启动的测试 MySQL，归档验证日志后清理本计划 scratch。

## 本地执行台账（2026-09-09）

- Task 1 已由提交 `eaef4c1a26b08ecb68db3a2e32628ce1bb7a9d36` 完成统一模型、服务、后台和 `permission.0006`/`0007` 迁移；Task 2 在该提交上继续执行。
- Task 2 旧 fixture RED 为 54 失败、119 通过，失败来自已删除主表字段的 ORM 写入、查询和双存储断言；改用纯测试统一明细 fixture 后，相关 HTTP、权限、任务和生命周期用例 226 通过。
- 专用 MySQL 独立入口中，`test_mysql_lifecycle.py` 与 `test_unified_migrations.py` 共 21 通过。迁移用例覆盖真实旧记录升级后以当前旧 HTTP 请求连续复用同一 token，并覆盖全空旧三元组停止、非标准原值保留但运行时拒绝、正反向迁移和异常回滚。
- 实际 `scripts/run_interface_unit_test.sh` 按顺序执行：独立迁移/并发阶段 21 通过；排除两份结构用例后的 interface/plugins/project_settings/contrib/decision_table/label 阶段 1635 通过并追加覆盖率。
- 产物校验确认 102 个网关 path/method/operationId/backend/auth/plugin 配置不变，92 个 zip 文件与源码一致，54 个相对链接和 17 个 JSON 示例有效。路由和 Schema 未因统一存储新增或改变认证配置。
- 上述为本地结果。Task 2 独立审查、最终审查、推送、TAPD 同步、新提交 CI 和测试 MySQL 关闭均由控制器执行；实时状态以 [PR #913](https://github.com/TencentBlueKing/BKFlow/pull/913) 为准。
