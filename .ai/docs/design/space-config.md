---
name: bkflow-space-config
description: Use when configuring a BKFlow space, adding new space config fields, implementing space variable features, or understanding the space config storage architecture — especially when modifying SpaceConfig models or the interface/engine dual-write logic.
---

# BKFlow 空间配置

## Overview

空间配置（SpaceConfig）是 BKFlow 业务隔离的核心机制，控制画布行为、Token 有效期、API 插件注册、插件可见性等空间级别的行为。配置架构支持将部分配置下沉至 engine 模块存储，以减轻 interface 的读取压力。

## 空间配置字段参考

### uniform_api 配置示例

```json
{
  "api": {
    "{api_key}": {
      "meta_apis": "{meta_apis url}",
      "api_categories": "{api_categories url}",
      "display_name": "{display_name}"
    }
  }
}
```

### space_plugin_config 配置示例

```json
{
  "default": {
    "mode": "deny_list",
    "plugin_codes": ["display"]
  }
}
```

## SpaceConfig 架构设计

### BaseSpaceConfig 基类

所有空间配置项继承自 `BaseSpaceConfig`，关键字段：

```python
class BaseSpaceConfig(metaclass=SpaceConfigMeta):
    name = None           # 配置名称（唯一标识）
    desc = None           # 描述
    is_public = True      # 是否公开给接入系统
    value_type = SpaceConfigValueType.TEXT.value
    default_value = None
    config_type = SpaceConfigType.INTERFACE  # 存储位置
```

### config_type 存储策略

配置类型决定配置存储和读取逻辑。

**设计意图**：engine 模块任务执行时读多写少，将部分配置（如空间变量）直接下放到 engine 存储，避免频繁读取 interface 造成压力。

## 空间变量（SpaceEngineConfig）

空间变量是一种特殊的 engine 侧空间配置，支持空间全局变量和按 scope 分组的变量：

```json
// 配置 name: "engine_space_config"
// config_type: ENGINE（存储在 engine 侧，读取时从 engine 侧读取）
{
  "space": {"{key1}": "{value1}"},
  "scope": {
    "{scope_type}_{scope_value}": {"{key1}": "{value1}"}
  }
}
```

**约束**：

- 空间变量存储在 engine 模块，不经过 interface
- 读取遵循相同逻辑：从 engine 侧读取
- scope key 格式：`{scope_type}_{scope_value}`

## 流程模板的 scope 概念

流程模板包含 `scope_type` 和 `scope_value` 字段，用于标识该模板属于接入系统的哪个业务范围（如业务 ID），由接入系统自定义语义，BKFlow 不做强约束。

## 模板版本管理

- 模板支持多版本，通过 `version` 字段区分，`source` 字段标识同一来源
- 同一 space + source 组合下，version 不允许重复
- 单个流程可以有多个启用版本，支持基于指定版本创建任务
- 接口支持模板回滚

## 配置变更约束

- `canvas_mode` 变更只对新建流程生效，已有流程的画布模式不变
- `gateway_expression` 变更后，已有流程使用原语法创建的分支条件仍然有效
- `space_plugin_config` 仅控制画布编辑界面的插件展示，不影响实际执行权限
- Token 过期时间最小为 1 小时
