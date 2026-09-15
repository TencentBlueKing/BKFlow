# PR #927 存量兼容与 master 集成

## 范围

从 `dev_multi_tenant@8d09251` 合并 `master@7b5ffb5`，保留 master 的开放插件目录、V4 表单、任务快照和新版空间配置，再补多租户兼容。保留原 PR #927 和共享分支历史，不进行 rebase 或强制推送。

本次处理：任务入口漏传租户、嵌套子任务继承、历史周期配置与运行上下文、关闭多租户模式的原服务兼容、定时秒数与负时区、通知业务失败、新旧审批协议，以及合并产生的来源 headers/前端 api_name 遗漏。

后续独立处理：Space single/global 语义、跨租户资源访问约束、插件来源租户与运行租户的授权契约、租户联合缓存/标识、租户初始化与 SDK 配套验证。本次修改不代表这些边界已具备。

## 存量回填

命令 `backfill_tenant_ids` 默认只预览。通过 JSON 指定已经核实的空间归属，例如：

```json
{"1": "tenant-a", "2": "tenant-b"}
```

不要使用示例值作为实际归属；不要未经核实将所有空间映射到 `system`。只处理映射列出的空间，包括已软删除的空间/任务，保留业务数据与周期配置中的其他字段。已有非 `default` 且不等于目标租户的记录会报错，禁止覆盖；已回填到目标租户的记录可重复执行。

1. 清点 Interface 中的空间，以及每个 Engine 中对应的 TaskInstance 和 PeriodicTask；确认映射覆盖全部拟升级的空间。跨租户共享空间和已有混合租户记录需先明确归属，不使用此命令强行统一。
2. 备份各模块数据库。停止空间/任务创建、周期触发及相关配置写入，并暂停 worker，避免预览与执行之间继续产生旧数据。
3. 分别部署同一版本的 Interface 和各 Engine 并执行常规 schema migration；Engine 包含框架生成的 `0019_merge_20260915_1225`，连接多租户字段与 master 的任务迁移链。不要使用 `--fake` 跳过真实操作。
4. 使用各模块自己的配置与数据库连接，分别预览：

   ```sh
   python manage.py backfill_tenant_ids --module interface --mapping /secure/space-tenants.json
   python manage.py backfill_tenant_ids --module engine --mapping /secure/space-tenants.json
   ```

   第二条需要在**每一个 Engine 数据库**执行。Engine 不查询 Interface ORM，也不会自动修改其他 Engine。

5. 核对逐空间的待修改数量。确认后在相应模块的同一环境增加 `--apply`。执行前预检全部映射；写入按空间使用事务，若后续空间发生并发冲突，前面已提交的空间会保留，可停写后重跑。保存命令输出和数据库备份。
6. 再次运行默认预览，确认拟处理空间的计数全部为零，并核对未列入映射的空间不属于此次升级范围。
7. 验证后恢复 worker、周期触发和请求入口。回滚需协调各模块版本和数据库备份；此命令不会自动将已核实的租户改回 `default`。

## 在途流程

- 升级前已持久化的 Pipeline 上下文如果缺少租户，远程插件、审批和通知从本 Engine 的 TaskInstance 读取回填后的租户。不批量改写运行中的 Pipeline 上下文。
- 历史周期配置缺少租户时，通过 Interface 内部接口查询空间租户；无法查得时停止创建并记录错误，不猜测归属。该后备路径要求 Interface 已先完成回填；不能代替完整数据盘点。
- 审批 v1.0 同时接受旧的 `approve_result` 和 ITSM4 的 `ticket.approve_result` 回调。两个审批 URL 均按节点输出分流：只有 `sn` 使用旧 ITSM；有 `id` 使用 ITSM4。因此切换期间仍需保留旧 ITSM 的访问能力，直到旧单据处理完毕。
- 关闭多租户时创建空间/任务的旧请求可省略租户；通知、审批、消息渠道和用户展示保留原部署行为。

## 验证与发布

本地测试使用独立临时 MySQL，不执行真实租户回填或调用真实审批/通知服务。前端构建/静态检查与单元测试只能证明本地代码状态；发布前仍需在 STAG 验证真实用户登录、两个租户的普通/无模板/Mock/周期/嵌套子任务、历史审批、通知失败，以及开放插件的目录/Schema/快照/执行/回调。

开放插件查询透传的是空间来源**已配置**的 headers，本次不自动生成新的租户授权策略。配置中的来源与实际插件网关要求需由后续边界工作核验。

### 2026-09-15 本地验证记录

- 针对本次修改的 Interface、插件、任务视图等回归：214 项通过；Engine 存量兼容及插件服务回归：105 项通过。
- 完整 Interface 首轮：1,731 通过、61 失败、1 跳过。其中 3 项时区参数断言已更新并在上述回归通过；其余 58 项 Python 沙箱失败与相同环境下 master 的完整测试失败集合一致（master：1,709 通过、58 失败、1 跳过）。单独运行相应沙箱样例，在两个分支均通过，保留整套测试环境相互影响的问题供另行定位。
- Engine task/utils/plugin_service 扩展首轮：550 通过、9 失败；9 项涉及旧插件认证及新增 tenant 参数的断言，修复后相关插件服务/存量兼容测试通过。
- 前端既有表单测试、增加 api_name 的测试、生产构建通过；ESLint 无错误，有 15 条既有或格式告警。保留 master 的完整字体资产，未缺少多租户分支图标。
- 临时独立数据库完成 master 建库及造旧数据 → 本分支 migrate → dry run → apply → 再次 dry run。Interface 空间、Engine 任务及周期配置回填后，待修改数量归零，周期配置其他字段保留。
- Engine task 的迁移状态检查无遗漏。Interface 的 SpaceConfig.name、TemplateOperationRecord.operate_type choices 漂移在 master 同样存在；本次未额外修改这些既有模型声明或第三方 bkoauth 迁移。
- APIGW operationId 无重复，文档 zip 与更新后的 Markdown 内容一致。未执行生产回填、远端分支合并或 STAG 验收。
