# 本地升级切换探针

用于验证 Python 3.9 / 旧版 Bamboo 与 Python 3.11 / 正式 LTS 包共享数据库和队列时的接续能力。
探针通过 BKFlow 创建任务、保存执行快照、调用引擎并检查持久化状态；worker 和 beat 使用真实进程。
空间变量、模板读取和事件广播由本地 HTTP 夹具响应，不覆盖登录、浏览器、真实网关和第三方服务。

## 准备独立环境

1. 准备旧版代码 checkout、Python 3.9 环境及其完整依赖；本次旧基线为 `75879886`。
2. 在当前 checkout 使用 Python 3.11.10 安装 `requirements.txt`，包含内部 `django-bkvision==1.2.0`。
   Bamboo 应为公共源的 `bamboo-pipeline==4.0.6` / `bamboo-engine==3.0.7`，不能使用本地补齐 wheel。
3. 两个 checkout 均不能包含 `local_settings.py` 或同名目录。
4. 启动只用于此次演练的 MySQL、Redis、RabbitMQ，使用全新的数据目录及下面的地址。
   创建 `bkflow_lts_engine`、`bkflow_lts_interface` 两个空数据库，字符集为 utf8mb4。

| 服务 | 固定地址 | 本地测试认证 |
| --- | --- | --- |
| MySQL | `127.0.0.1:13306` | root，空密码，仅回环监听 |
| Redis | `127.0.0.1:16379/0` | 无密码，仅回环监听 |
| RabbitMQ | `127.0.0.1:15673/` | guest / guest，仅回环监听 |
| HTTP 夹具 | `127.0.0.1:19999` | 无认证，仅回环监听 |

不能将这些端口转发到远程服务。本次 RabbitMQ 4.3.6 配置了
`deprecated_features.permit.transient_nonexcl_queues = true` 兼容旧客户端。
服务版本和配置必须与演练记录一起保存，不应据此修改生产 broker。

下面命令中的 `OLD_ROOT`、`OLD_PYTHON`、`NEW_PYTHON`、`OUT` 需设置为各自的绝对路径；
`OUT` 是专用结果目录，`NEW_ROOT` 为当前 checkout。

```bash
NEW_ROOT="$PWD"
PROBE="$NEW_ROOT/tests/upgrade/rehearsal.py"
RUNNER="$NEW_ROOT/tests/upgrade/run_local.py"
oldrun() {
  python3 "$RUNNER" --root "$OLD_ROOT" --python "$OLD_PYTHON" --output "$OUT" --version old "$@"
}
newrun() {
  python3 "$RUNNER" --root "$NEW_ROOT" --python "$NEW_PYTHON" --output "$OUT" --version new "$@"
}
oldrun engine manage.py migrate --noinput
oldrun interface manage.py migrate --noinput
newrun engine manage.py migrate --plan
newrun interface manage.py migrate --plan
```

`run_local.py` 会生成固定的本地配置，清除继承的环境变量，再加载仓库的测试环境变量和回环地址。
不要额外加载日常开发环境或生产配置。完整依赖检查应分别使用对应虚拟环境执行。

## 升级与回滚

先启动夹具，保持进程运行：

```bash
"$NEW_PYTHON" "$NEW_ROOT/tests/upgrade/interface_fixture.py" "$OUT/periodic-current.json"
```

启动旧 worker，单独保存日志并记录其 PID：

```bash
oldrun engine -m celery -A config worker -P threads -c 2 \
  -Q er_execute_lts,er_schedule_lts,task_callback_lts -n old-lts@localhost \
  --without-gossip --without-mingle --without-heartbeat -l INFO
```

依次执行：

```bash
oldrun engine "$PROBE" seed "$OUT/forward.json"
# 对旧 worker 发 TERM 并等待正常退出，确认 ETA 消息归还队列。
oldrun engine "$PROBE" queue "$OUT/forward.json"
newrun engine manage.py migrate --noinput
newrun interface manage.py migrate --noinput
# 使用相同参数启动新 worker（oldrun 改为 newrun，节点名改为 new-lts@localhost）。
newrun engine "$PROBE" resume "$OUT/forward.json"
newrun engine "$PROBE" verify "$OUT/forward.json"
```

`seed` 创建等待回调、90 秒定时、失败 Python 节点和禁用的周期任务。
`queue` 在无消费者时发送普通任务；`resume` 回调、重试并读取序列化时间及周期配置；
`verify` 检查任务全部完成以及回调、重试输出。各探针均有超时，失败时保留日志及数据库供排查。

回滚时使用新 worker 运行 `seed`，正常停止它后用新版运行 `queue`；启动旧 worker，
使用旧版执行 `resume`、`verify`，结果写入另一个 `rollback.json`。
保留升级后的数据库，不还原数据库、不执行逆向迁移。

## 子画布、共存及周期派发

- 子画布：旧 worker 上执行 `nested_seed nested-forward.json`，正常退出后由新 worker 执行
  `nested_resume nested-forward.json`。再反向重复。每次验证第一轮回调、第二轮和父任务均完成，
  并确认产生两个真实子任务。worker 必须监听 `task_callback_lts`。
- 共存：同时启动新旧 worker；新旧解释器分别执行 `mixed mixed-old.json`、
  `mixed mixed-new.json`。每组 20 个任务，持久化状态必须全部完成；核对两份 worker 日志，
  确认双方实际消费了任务，不能只依据 worker 在线判断。
- 周期派发：停止共存 worker，用旧版执行 `periodic_seed periodic-current.json`，
  保存该文件副本；启动新版 worker 和下面的新版 beat，然后执行
  `periodic_verify periodic-current.json`。正常停止两个进程后，新版保存配置、旧版 beat 和 worker
  执行，再反向重复。全过程只运行一个 beat。

```bash
oldrun engine "$PROBE" periodic_seed "$OUT/periodic-current.json"
# 在独立终端运行新版 worker，再运行：
newrun engine -m celery -A config beat \
  -S django_celery_beat.schedulers:DatabaseScheduler --max-interval=1 -l INFO \
  --pidfile="$OUT/beat.pid"
# 在另一个终端验证：
newrun engine "$PROBE" periodic_verify "$OUT/periodic-current.json"
```

周期夹具使用 Asia/Shanghai 时区，将上次派发时间设为两分钟前，使调度器实际发送已到期任务。
任务经正常的 `bkflow_periodic_task_start` 创建并启动；验证生成的流程完成且执行计数为 1。
验证结束后禁用这条测试配置。

结果保存为 `*.result.json`。运行结束后正常关闭本次启动的进程，保留版本清单、迁移计划、
任务结果和日志；不要清理其他本地服务。正式包验证结果见
[2026-10-20 验证记录](../../docs/plans/2026-10-20-python311-lts-upgrade.md)。

## Webhook 依赖升级与回滚

`webhook_rehearsal.py` 使用接口模块的本地数据库，调用 BKFlow 配置入口与包的事件信号，
通过真实 RabbitMQ、worker、HTTP 接收端检查配置加密、鉴权、事件载荷、投递历史和失败重试。
它拒绝非上述隔离环境；接收端固定为 `127.0.0.1:19998`，所有鉴权值均为脚本内的本地测试数据。

```bash
HOOK_PROBE="$NEW_ROOT/tests/upgrade/webhook_rehearsal.py"
# 独立终端运行接收端，并保留 JSONL 接收记录。
"$NEW_PYTHON" "$HOOK_PROBE" serve "$OUT/webhook-http.jsonl"

# 暂无 webhook worker 时，由旧版产生三条消息。
oldrun interface "$HOOK_PROBE" seed "$OUT/webhook-forward.json"
# 独立终端启动新版 worker。
newrun interface -m celery -A config worker -I webhook.handlers -P threads -c 2 \
  -Q lts_webhook_upgrade -n webhook-new@localhost \
  --without-gossip --without-mingle --without-heartbeat -l INFO
# 另一个终端校验 200 / 503 后重试成功，并使用新版本更新旧配置。
newrun interface "$HOOK_PROBE" verify "$OUT/webhook-forward.json"
oldrun interface "$HOOK_PROBE" read_updated "$OUT/webhook-forward.json"
```

正常关闭 worker 后交换 oldrun/newrun，以新的结果文件重复，验证反向回滚。
等待重试的交接单独用 `seed_retry` 创建通知：启动发送方版本的 worker，执行 `failed` 等待第一条
503 历史，正常退出并确认 ETA 消息归还；启动另一版本，执行 `verify`，最终必须出现 `[503, 200]`。
再执行原版本的 `read_updated`，核对对方更新的加密配置可读。两个方向均重复。
每次使用新的结果文件名，避免历史记录干扰，不清空其他队列。
