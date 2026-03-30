---
name: bkflow-plugin-system
description: Use when developing or integrating API plugins, understanding plugin meta protocol, implementing dynamic form generation, configuring plugin credentials, or adding new plugin types to BKFlow.
---

# BKFlow 插件系统

## Overview

BKFlow 支持三种插件类型：内置插件、蓝鲸插件和 API 插件。API 插件是最灵活的扩展机制，允许接入系统通过暴露符合特定协议的接口，让 BKFlow 自动生成动态表单插件，无需修改 BKFlow 代码。

## API 插件协议

API 插件通过在空间配置 `uniform_api` 注册两个接口地址：

- `api_categories`：返回 API 分类列表
- `meta_apis`：返回 API 元数据列表（含指向详情的 `meta_url`）

### 分类接口协议（GET）

输入：`?scope_value=xx&scope_type=xx`

```json
{
  "result": true,
  "message": "",
  "data": [
    {"name": "c1", "key": "c1"}
  ]
}
```

### 元数据列表接口协议（GET）

输入：`?limit=50&offset=0&scope_type=xx&scope_value=xx&category=xx`（支持分页和过滤）

```json
{
  "result": true,
  "message": "",
  "data": [
    {
      "id": "api1",
      "meta_url": "xxxx/api1",
      "name": "api1",
      "category": "xxx"
    }
  ]
}
```

### 元数据详情接口协议（GET）

```json
{
  "result": true,
  "message": "",
  "data": {
    "id": "api1",
    "name": "api1",
    "url": "https://xxx.apigw.xxx.com/...",
    "methods": ["GET"],
    "inputs": [
      {
        "key": "field_key",
        "name": "展示名",
        "desc": "描述",
        "required": true,
        "type": "string",
        "form_type": "input",
        "options": ["a", "b"],
        "default": "xxx",
        "meta_desc": "冗余注释"
      }
    ],
    "outputs": [
      {
        "key": "key1",
        "name": "xxx",
        "type": "string",
        "meta_desc": "xxx"
      }
    ],
    "response_data_path": "a.b[0].c",
    "polling": {
      "url": "xxx.com",
      "key": "task_id_output_key",
      "success_tag": {"key": "status", "value": "success"},
      "fail_tag": {"key": "status", "value": "fail"}
    }
  }
}
```

字段说明：

- `type`：`string` / `int` / `bool` / `list` / `json`
- `form_type`：可选，覆盖默认表单类型
- `options`：`type` 为 `list` 或 `form_type` 为 `select` 时需要
- `meta_desc`：勾选为变量时携带到 `extra_info`

### 特殊 form_type

- `table`：表格输入，需要在字段下增加 `table.fields` 描述（仅支持一层嵌套，不支持嵌套 table）
- `time_range`：时间范围选择器
- `select`：下拉选择（有 options 时自动推断）

### response_data_path 约束

若配置了 `response_data_path`，BKFlow 会从响应中按路径提取数据作为插件输出。如果根据路径检索响应不存在，插件执行报错，接入系统需确保路径与实际响应结构匹配。

## API 插件隔离

- API 插件以空间 ID 进行隔离，不同空间可以配置不同的 API 插件集合
- 通过 `uniform_api` 空间配置注册，不同空间可注册不同 `api_key`

## API 插件凭证

API 插件执行时发送 HTTP 请求需要携带凭证：

1. 在 BKFlow 注册凭证（空间级别）
2. 在空间配置 `api_gateway_credential_name` 指定使用哪个凭证
3. 执行时读取空间配置，使用对应空间注册的凭证以接入方系统身份发起请求

## Mock 支持

插件支持 mock 配置项，开启后不进行接口调用，直接将 mock 数据赋值到对应输出。用于节点无法实际执行的场景调试。

## 蓝鲸插件同步机制

`bk_plugin` 模块包含异步任务，定期从蓝鲸插件服务同步拉取插件信息。接入系统开发者在蓝鲸开发者中心发布的插件会通过此机制同步到 BKFlow。
