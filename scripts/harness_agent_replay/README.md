# 本地模型工具回放

保留模型对照实验的程序，不携带原始环境快照、模型回答或个人客户端配置。模型调用真实发生，但工具结果来自固定快照，程序不会连接 BKFlow、发布或执行流程；不能将其结果当成真实 MCP 端到端验收。

## 只做离线校验

使用项目 Python 环境中的 `PyYAML` 和 `jsonschema`。在仓库根目录执行：

```sh
python scripts/harness_agent_replay/replay.py \
  --fixture /path/to/reviewed-fixture.json --space-id 1 --self-test
```

快照须由调用方先做脱敏审核，不自动搜索用户目录。现有回放场景为 4 页、10 个节点、15 条历史事件；每页请求 `node_limit=3, limit=100`，放大单页数量后受字节预算限制，首页仍只返回 9 个节点。JSON 须包含 `envelope`、`base_artifact`、`pages`、`system_prompt`、`user_prompt`。`base_artifact` 包含 `session`、`history`、`read_guidance` 和 `context`；节点页使用 `get_debug_session` 返回结构。空间 ID 和提示词中的空间必须一致。先运行离线校验，确认逐页内容、游标及只读拒绝与原快照相同。

原始快照可能含内部标识、流程输入和输出，不作为公共仓库的示例提交。结果文件也不应未经审核提交。

## 调用本地模型

显式指定 `--variant full` 或 `--variant compact` 才会调用模型。通过进程环境提供 `HARNESS_REPLAY_ENDPOINT`、`HARNESS_REPLAY_MODEL`、`HARNESS_REPLAY_API_KEY`，密钥不要写入代码、命令参数、知识库或报告。默认入口为 `http://127.0.0.1:8000/v1/chat/completions`，使用兼容 Chat Completions 的本地代理。

```sh
python scripts/harness_agent_replay/replay.py \
  --fixture /path/to/reviewed-fixture.json --space-id 1 \
  --variant full --output /path/to/new-result.json
```

仅支持本机 HTTP 入口，不使用环境代理、不跟随重定向。即使入口在本机，代理仍可能将提示词和工具快照转发到模型服务；调用前须确认数据权限、模型通道及费用。程序不读取个人工具数据库。

`full` 保留快照字段；`compact` 实验性压缩返回，仅用于模型对照，不改变 BKFlow 的服务端协议。每轮最多 6 次工具调用、8 轮模型请求。只允许回放当前空间和会话的 `get_debug_session`，拒绝其他工具。输出记录调用次数、分页覆盖、耗时、用量及最终回答，不保存认证头。
