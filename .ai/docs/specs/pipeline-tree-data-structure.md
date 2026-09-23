# Pipeline Tree 数据结构参考

> 本文档描述 pipeline_tree 的核心数据结构，供 AI Agent 在处理流程引擎相关代码时参考。
> 数据来源：模板保存时生成的 pipeline_tree JSON，以及任务执行时的 execution_data。

## 总览

`pipeline_tree` 是描述一个流程拓扑结构的 JSON 对象，核心字段包括：

```json
{
  "activities": {},
  "gateways": {},
  "flows": {},
  "start_event": {},
  "end_event": {},
  "constants": {},
  "outputs": [],
  "line": [],
  "location": []
}
```

## Activity 结构

### ServiceActivity（标准节点）

`activities` 中每个 key 为 node_id，值为节点定义。标准节点的 `type` 为 `"ServiceActivity"`：

```json
{
  "node_id_xxx": {
    "type": "ServiceActivity",
    "id": "node_id_xxx",
    "name": "节点名称",
    "component": {
      "code": "组件编码",
      "version": "版本号",
      "data": {
        "param_key": {
          "hook": false,
          "value": "参数值"
        }
      }
    },
    "optional": false,
    "error_ignorable": false,
    "retryable": true,
    "skippable": true,
    "timeout_config": { "enable": false, "seconds": 10, "action": "forced_fail" },
    "incoming": ["flow_id"],
    "outgoing": "flow_id"
  }
}
```

### SubProcess（子流程节点）

子流程节点的 `type` 为 `"SubProcess"`，内嵌完整的 `pipeline` 结构：

```json
{
  "subprocess_node_id": {
    "type": "SubProcess",
    "id": "subprocess_node_id",
    "name": "子流程名称",
    "pipeline": {
      "activities": {},
      "gateways": {},
      "flows": {},
      "start_event": {},
      "end_event": {},
      "constants": {},
      "outputs": []
    },
    "incoming": ["flow_id"],
    "outgoing": "flow_id"
  }
}
```

## Component 结构（重点）

`component` 是 ServiceActivity 的核心，定义了该节点使用的插件和参数。

### 关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | string | 组件编码，如 `"bk_http_request"`、`"remote_plugin"`、`"uniform_api"` |
| `version` | string | 组件版本，如 `"v1.0"`、`"1.0.0"`、`"legacy"` |
| `data` | object | **组件参数字典**（是参数的标准存放位置） |

### data 字段格式

`data` 中每个 key 是参数名，值为参数定义对象：

```json
{
  "data": {
    "param_name": {
      "hook": false,
      "value": "参数的实际值"
    },
    "another_param": {
      "hook": true,
      "value": "${全局变量key}"
    }
  }
}
```

- `hook`: 是否勾选为全局变量，`true` 表示该参数从流程全局变量注入
- `value`: 参数值。当 `hook=false` 时为直接值；当 `hook=true` 时为变量引用 key

### remote_plugin 类型的特殊处理

当 `component.code` 为 `"remote_plugin"` 时，它是一个代理节点，实际调用的插件信息存放在 `data` 中：

```json
{
  "component": {
    "code": "remote_plugin",
    "version": "1.0.0",
    "data": {
      "plugin_code": { "hook": false, "value": "bk-sops-plugin" },
      "plugin_version": { "hook": false, "value": "1.0.0" },
      "...其他插件参数...": {}
    }
  }
}
```

**注意事项：**

- 统计采集时需从 `data.plugin_code.value` 获取实际插件编码，而非使用 `"remote_plugin"` 作为插件标识
- `data` 是标准参数路径；部分旧代码可能错误使用了 `inputs` 路径，已修正为优先读 `data`，兼容 `inputs`
- `plugin_version` 同理，从 `data.plugin_version.value` 获取
- `data.plugin_name.value` 可选，存放插件的中文名称

### uniform_api 类型的特殊处理

当 `component.code` 为 `"uniform_api"` 时，新版 API 插件会在 `component.api_meta` 中存放实际的 API 插件信息：

```json
{
  "component": {
    "code": "uniform_api",
    "version": "v2.0.0",
    "data": {
      "uniform_api_plugin_url": { "hook": false, "value": "http://example.com/api" },
      "uniform_api_plugin_method": { "hook": false, "value": "POST" }
    },
    "api_meta": {
      "id": "实际的API插件ID",
      "name": "API插件名称",
      "meta_url": "元数据地址",
      "api_key": "API标识键",
      "category": {
        "id": "分类ID",
        "name": "分类名称"
      }
    }
  }
}
```

**注意事项：**

- 统计采集时需从 `api_meta.id` 获取实际插件编码，而非使用 `"uniform_api"`
- `api_meta.name` 存放插件名称，`api_meta.category.name` 存放分类名称
- 完整的展示名称格式为 `"分类名称-插件名称"`
- 旧版 uniform_api（v1.0.0）没有 `api_meta` 字段，此时保持 `"uniform_api"` 作为编码
- `api_meta` 是 `component` 的直接子字段，不在 `data` 内部

## 常见 Component 类型示例

### 1. HTTP 请求插件

```json
{
  "code": "bk_http_request",
  "version": "v1.0",
  "data": {
    "bk_http_request_method": { "hook": false, "value": "GET" },
    "bk_http_request_url": { "hook": false, "value": "https://example.com/api" },
    "bk_http_request_header": { "hook": false, "value": [] },
    "bk_http_request_body": { "hook": false, "value": "" }
  }
}
```

### 2. 统一 API 调用插件

```json
{
  "code": "uniform_api",
  "version": "v1.0",
  "data": {
    "uniform_api_plugin_url": { "hook": false, "value": "http://api.example.com" },
    "uniform_api_plugin_name": { "hook": false, "value": "示例API" },
    "uniform_api_request_method": { "hook": false, "value": "POST" },
    "uniform_api_request_body": { "hook": false, "value": "{}" }
  }
}
```

### 3. 远程插件（代理调用）

```json
{
  "code": "remote_plugin",
  "version": "1.0.0",
  "data": {
    "plugin_code": { "hook": false, "value": "bk-sops-plugin" },
    "plugin_version": { "hook": false, "value": "1.0.0" },
    "inputs": { "hook": false, "value": "{\"key\": \"value\"}" }
  }
}
```

### 4. 信息展示插件

```json
{
  "code": "bk_display",
  "version": "v1.0",
  "data": {
    "bk_display_message": { "hook": false, "value": "展示内容" }
  }
}
```

## Gateway 结构

网关类型定义在 `gateways` 字段中：

| 类型 | 说明 |
|------|------|
| `ExclusiveGateway` | 排他网关（二选一） |
| `ParallelGateway` | 并行网关（全部执行） |
| `ConditionalParallelGateway` | 条件并行网关 |
| `ConvergeGateway` | 汇聚网关 |

```json
{
  "gateway_id": {
    "type": "ExclusiveGateway",
    "id": "gateway_id",
    "name": "判断条件",
    "conditions": {
      "flow_id_1": { "evaluate": "${result} == True" },
      "flow_id_2": { "evaluate": "${result} == False" }
    },
    "incoming": ["flow_id"],
    "outgoing": ["flow_id_1", "flow_id_2"]
  }
}
```

## bamboo_engine 状态树结构

任务执行后，通过 `bamboo_engine.api.get_pipeline_states()` 获取的状态树结构：

```json
{
  "<root_id>": {
    "id": "<root_id>",
    "state": "FINISHED",
    "root_id": "<root_id>",
    "parent_id": "<root_id>",
    "version": "v1",
    "loop": 1,
    "retry": 0,
    "skip": false,
    "error_ignorable": false,
    "error_ignored": false,
    "created_time": "datetime",
    "started_time": "datetime",
    "archived_time": "datetime",
    "children": {
      "<node_id>": {
        "id": "<node_id>",
        "state": "FINISHED",
        "started_time": "datetime",
        "archived_time": "datetime",
        "retry": 0,
        "skip": false,
        "children": {}
      }
    }
  }
}
```

**注意事项：**

- 顶层 key 是 `root_id`（即 `instance_id`），不是直接的 children 结构
- 时间字段使用 `started_time` / `archived_time`，不是 `start_time` / `finish_time`
- `elapsed_time` 不在返回中，需要通过 `archived_time - started_time` 计算
- 子流程的 children 在对应 SubProcess 节点的 `children` 中递归嵌套
