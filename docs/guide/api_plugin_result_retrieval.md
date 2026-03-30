# API插件执行结果获取机制详解

本文档详细说明BKFlow在API插件的**Polling模式**和**Callback模式**下如何获取插件执行结果。

## 概述

API插件支持两种异步结果获取模式：
1. **Polling模式（轮询模式）**：BKFlow主动定期查询外部系统获取任务状态
2. **Callback模式（回调模式）**：外部系统完成任务后主动通知BKFlow

两种模式的核心实现都在 `bkflow/pipeline_plugins/components/collections/uniform_api/v2_0_0.py` 文件中的 `UniformAPIService` 类。

---

## 一、Polling模式（轮询模式）

### 1.1 工作流程

Polling模式的工作流程如下：

```
1. 触发阶段（Trigger）
   BKFlow → 外部API → 返回task_tag

2. 轮询阶段（Polling）
   BKFlow → 轮询API（带task_tag）→ 返回状态
   ├─ 成功 → 结束节点
   ├─ 失败 → 节点失败
   └─ 运行中 → 继续轮询
```

### 1.2 代码实现流程

#### 阶段1：触发任务（`_dispatch_schedule_trigger`）

**位置**：`bkflow/pipeline_plugins/components/collections/uniform_api/v2_0_0.py:117-235`

**关键步骤**：

1. **调用触发API**（第175-182行）
   ```python
   request_result: HttpRequestResult = client.request(
       url=url,
       method=method,
       data=api_data,
       headers=headers,
       timeout=settings.BKAPP_API_PLUGIN_REQUEST_TIMEOUT,
   )
   ```

2. **检查是否配置了polling**（第226-231行）
   ```python
   if polling:
       # 10s interval for polling
       self.interval.init_interval = 10  # 设置轮询间隔为10秒
       data.outputs.trigger_data = resp_data  # 保存触发响应数据
       data.set_outputs("need_polling", True)  # 标记需要轮询
       return True  # 返回True，节点进入schedule状态
   ```

3. **保存触发响应**：将API返回的完整响应保存在 `data.outputs.trigger_data` 中，后续用于提取 `task_tag`

#### 阶段2：轮询状态（`_dispatch_schedule_polling`）

**位置**：`bkflow/pipeline_plugins/components/collections/uniform_api/v2_0_0.py:237-364`

**关键步骤**：

1. **检查轮询次数限制**（第238-244行）
   ```python
   if self.interval.reach_limit():
       # 如果超过一天（默认最大轮询次数），节点自动失败
       data.set_outputs("ex_data",
           "[uniform_api polling] reach max count of schedule, "
           "please ensure the task can be finished in one day")
       return False
   ```

2. **提取task_tag**（第291-300行）
   ```python
   trigger_data = data.get_one_of_outputs("trigger_data", {})
   task_tag_value = jmespath.search(polling_config.task_tag_key, trigger_data)
   # 使用JMESPath从触发响应中提取task_tag
   # 例如：如果task_tag_key是"task_tag"，则从响应中提取task_tag字段的值
   ```

3. **调用轮询API**（第305-312行）
   ```python
   api_data = {"task_tag": task_tag_value, **extra_data}
   request_result: HttpRequestResult = client.request(
       url=polling_config.url,
       method="get",  # 轮询接口必须是GET方法
       data=api_data,
       headers=headers,
       timeout=settings.BKAPP_API_PLUGIN_REQUEST_TIMEOUT,
   )
   ```

4. **状态判断**（第338-364行）

   按照优先级判断状态：**成功 > 失败 > 运行中**

   ```python
   status_data = request_result.json_resp

   # 判断成功状态
   if jmespath.search(polling_config.success_tag.key, status_data) == polling_config.success_tag.value:
       self.logger.info("[uniform_api polling] get success status")
       if polling_config.success_tag.data_key:
           # 如果配置了data_key，提取成功时的数据
           data.outputs.data = jmespath.search(polling_config.success_tag.data_key, status_data)
       self.finish_schedule()  # 结束调度，节点完成
       return True

   # 判断失败状态
   if jmespath.search(polling_config.fail_tag.key, status_data) == polling_config.fail_tag.value:
       # 设置错误信息
       data.outputs.ex_data = jmespath.search(polling_config.fail_tag.msg_key, status_data) or default_msg
       return False  # 节点失败

   # 判断运行中状态
   if jmespath.search(polling_config.running_tag.key, status_data) == polling_config.running_tag.value:
       self.logger.info(f"[uniform_api polling] get running status: {status_data}")
       return True  # 继续轮询，等待下次schedule调用
   ```

5. **设置HTTP状态码**（第319行）
   ```python
   data.outputs.status_code = request_result.resp.status_code
   ```
   无论轮询结果如何，都会将轮询API响应的HTTP状态码设置为节点的 `status_code` 输出。

### 1.5 Polling模式下的节点输出

在polling模式下，节点的输出数据（`data.outputs`）包含以下字段：

| 输出字段 | 说明 | 设置时机 | 数据来源 |
|---------|------|---------|---------|
| **`status_code`** | HTTP响应状态码 | 每次轮询都会设置 | 轮询API响应的HTTP状态码（第319行） |
| **`data`** | 响应内容 | 仅在成功且配置了`data_key`时设置 | 使用JMESPath从轮询响应中提取`success_tag.data_key`指定的字段（第342-343行） |
| **`ex_data`** | 错误信息 | 失败时设置 | 失败时的错误消息 |
| **`trigger_data`** | 触发响应数据 | 触发阶段设置 | 触发API的完整响应（用于提取task_tag） |

**重要说明**：

1. **`status_code`**：总是会被设置，值为轮询API响应的HTTP状态码（如200、404等）

2. **`data`**：只有在以下条件**同时满足**时才会被设置：
   - 轮询返回成功状态（通过`success_tag`判断匹配）
   - 在配置中指定了`success_tag.data_key`字段
   - 使用JMESPath表达式从轮询响应中提取`data_key`指定的字段值

   如果**没有配置`data_key`**，则`data.outputs.data`不会被设置（可能为`None`或保持默认值）

3. **示例**：

   假设轮询API返回：
   ```json
   {
     "result": true,
     "status": "success",
     "data": {
       "task_id": "12345",
       "result": "completed"
     }
   }
   ```

   配置：
   ```json
   {
     "success_tag": {
       "key": "status",
       "value": "success",
       "data_key": "data"  // 指定提取data字段
     }
   }
   ```

   则节点输出：
   - `status_code`: `200`（HTTP状态码）
   - `data`: `{"task_id": "12345", "result": "completed"}`（从响应中提取的data字段）

### 1.3 调度机制

- **轮询间隔**：10秒（`self.interval.init_interval = 10`）
- **最大轮询时间**：1天（通过 `StepIntervalGenerator` 的 `reach_limit()` 方法控制）
- **调度入口**：`plugin_schedule` 方法（第92-101行）
  ```python
  def plugin_schedule(self, data, parent_data, callback_data=None):
      need_polling = data.get_one_of_outputs("need_polling", False)
      need_callback = data.get_one_of_outputs("need_callback", False)
      action = "trigger"
      if need_polling:
          action = "polling"
      if need_callback:
          action = "callback"
      dispatched_func = getattr(self, f"_dispatch_schedule_{action}")
      return dispatched_func(data, parent_data, callback_data)
  ```

### 1.4 配置示例

在 `detail meta api` 中需要配置：

```json
{
  "polling": {
    "url": "{{polling_url}}",
    "task_tag_key": "task_tag",  // 或 "data.task_tag"（支持多级字段）
    "success_tag": {"key": "status", "value": "success"},
    "fail_tag": {"key": "status", "value": "fail"},
    "running_tag": {"key": "status", "value": "running"}
  }
}
```

---

## 二、Callback模式（回调模式）

### 2.1 工作流程

Callback模式的工作流程如下：

```
1. 触发阶段（Trigger）
   BKFlow → 外部API（传递node_id等信息）→ 返回成功

2. 等待回调阶段
   BKFlow节点进入等待状态（不轮询）

3. 回调阶段
   外部系统完成任务 → 调用BKFlow回调接口 → BKFlow处理回调数据
   ├─ 成功 → 结束节点
   └─ 失败 → 节点失败
```

### 2.2 代码实现流程

#### 阶段1：触发任务（`_dispatch_schedule_trigger`）

**位置**：`bkflow/pipeline_plugins/components/collections/uniform_api/v2_0_0.py:117-235`

**关键步骤**：

1. **准备回调信息**（第118-120行）
   ```python
   extra_data = {
       "caller": operator,
       "scope_type": parent_data.get_one_of_inputs("task_scope_type"),
       "scope_value": parent_data.get_one_of_inputs("task_scope_value"),
       "task_id": parent_data.get_one_of_inputs("task_id"),
       "task_name": parent_data.get_one_of_inputs("task_name"),
       "space_id": space_id,
       "node_id": self.id,  # 节点ID，外部系统需要记录此ID
   }
   api_data.update({"bkflow_extra_info": extra_data})
   ```
   这些信息会被传递给外部API，外部系统需要记录 `node_id` 用于后续回调。

2. **调用触发API**（第175-182行）
   与polling模式相同，调用外部API触发任务。

3. **检查是否配置了callback**（第221-224行）
   ```python
   if callback:
       self.interval = None  # 不设置轮询间隔，节点进入等待状态
       data.set_outputs("need_callback", True)  # 标记需要回调
       return True  # 返回True，节点进入schedule状态（等待回调）
   ```

#### 阶段2：处理回调（`_dispatch_schedule_callback`）

**位置**：`bkflow/pipeline_plugins/components/collections/uniform_api/v2_0_0.py:366-397`

**关键步骤**：

1. **接收回调数据**（第367行）
   ```python
   self.logger.info(f"[uniform_api callback] callback_data: {callback_data}")
   ```
   `callback_data` 参数由外部系统通过回调接口传入。

2. **验证回调配置**（第368-375行）
   ```python
   callback = data.get_one_of_inputs("uniform_api_plugin_callback")
   callback_config: CallbackConfig = CallbackConfig(**callback)
   ```

3. **状态判断**（第377-397行）
   ```python
   # 判断成功状态
   if jmespath.search(callback_config.success_tag.key, callback_data) == callback_config.success_tag.value:
       self.logger.info("[uniform_api callback] get success status")
       if callback_config.success_tag.data_key:
           # 提取成功时的数据
           data.outputs.data = jmespath.search(callback_config.success_tag.data_key, callback_data)
       self.finish_schedule()  # 结束调度，节点完成
       return True

   # 判断失败状态
   if jmespath.search(callback_config.fail_tag.key, callback_data) == callback_config.fail_tag.value:
       default_msg = f"[uniform_api callback] get fail status: {callback_data}"
       data.outputs.ex_data = (
           jmespath.search(callback_config.fail_tag.msg_key, callback_data)
           if callback_config.fail_tag.msg_key
           else default_msg
       )
       return False  # 节点失败
   ```

### 2.3 回调接口调用路径

外部系统调用BKFlow回调接口的完整路径：

#### 路径1：通过APIGW接口（推荐）

**接口**：`operate_task_node`

**位置**：`bkflow/apigw/views/operate_task_node.py:38-54`

**调用方式**：
```http
POST /api/v1/task/{task_id}/node_operate/{node_id}/callback/
Content-Type: application/json

{
  "version": "v2.0.0",  // 节点版本
  "data": {              // 回调数据
    "status": "success"
  }
}
```

**处理流程**：
1. APIGW接口接收请求（`operate_task_node`）
2. 调用 `TaskComponentClient.node_operate()`（第53行）
3. 转发到engine模块的 `node_operate` 接口
4. 最终调用 `TaskNodeOperation.callback()`（`bkflow/task/operations.py:412-417`）
5. 调用 `bamboo_engine_api.callback()` 触发节点的 `plugin_schedule` 方法
6. `UniformAPIService.plugin_schedule()` 检测到 `need_callback=True`，调用 `_dispatch_schedule_callback`

#### 路径2：通过内部回调URL（带token）

**接口**：`callback`

**位置**：`bkflow/interface/views.py:106-137`

**URL生成**：`bkflow/pipeline_plugins/utils.py:31-37`
```python
def get_node_callback_url(space_id, task_id, node_id, node_version=""):
    f = Fernet(env.CALLBACK_KEY)
    callback_entry = BKAPP_INNER_CALLBACK_ENTRY + "callback/%s/"
    return (
        callback_entry
        % f.encrypt(bytes("{}:{}:{}:{}".format(space_id, task_id, node_id, node_version), encoding="utf8")).decode()
    )
```

**调用方式**：
```http
POST /callback/{encrypted_token}/
Content-Type: application/json

{
  "status": "success"
}
```

**处理流程**：
1. 解密token获取 `space_id`, `task_id`, `node_id`, `node_version`（第108-111行）
2. 解析请求体获取 `callback_data`（第116行）
3. 调用 `TaskComponentClient.node_operate()`（第128行）
4. 后续流程与路径1相同

### 2.4 配置示例

在 `detail meta api` 中需要配置：

```json
{
  "callback": {
    "success_tag": {"key": "status", "value": "success"},
    "fail_tag": {"key": "status", "value": "fail"}
  }
}
```

**注意**：Callback模式不需要配置 `running_tag`，因为节点会一直等待直到收到回调。

---

## 三、两种模式对比

| 特性 | Polling模式 | Callback模式 |
|------|------------|-------------|
| **主动/被动** | BKFlow主动查询 | 外部系统主动通知 |
| **轮询间隔** | 10秒 | 无（不轮询） |
| **最大等待时间** | 1天 | 无限制（理论上） |
| **资源消耗** | 较高（定期请求） | 较低（被动接收） |
| **实时性** | 最多延迟10秒 | 实时（任务完成即回调） |
| **适用场景** | 外部系统无法主动回调 | 外部系统可以主动回调 |
| **配置复杂度** | 需要配置polling_url和状态标识 | 只需配置状态标识 |

---

## 四、关键技术点

### 4.1 JMESPath表达式

两种模式都使用JMESPath从响应数据中提取字段：

- **提取task_tag**：`polling_config.task_tag_key`（如 `"task_tag"` 或 `"data.task_tag"`）
- **判断状态**：`success_tag.key`、`fail_tag.key`、`running_tag.key`
- **提取数据**：`success_tag.data_key`、`fail_tag.msg_key`

### 4.2 节点状态管理

- **`need_polling`**：标记节点需要轮询
- **`need_callback`**：标记节点需要回调
- **`trigger_data`**：保存触发API的响应数据（用于提取task_tag）
- **`finish_schedule()`**：结束节点的调度状态，节点完成

### 4.3 调度机制

- **`__need_schedule__ = True`**：标记插件需要调度
- **`interval = StepIntervalGenerator(init_interval=0)`**：控制调度间隔
- **`plugin_schedule()`**：调度入口，根据 `need_polling` 和 `need_callback` 决定执行哪个处理函数

---

## 五、总结

1. **Polling模式**：BKFlow通过定期调用轮询接口获取任务状态，适合外部系统无法主动回调的场景。

2. **Callback模式**：外部系统完成任务后主动调用BKFlow的回调接口，适合外部系统可以主动通知的场景。

3. **两种模式的核心区别**：
   - Polling：BKFlow主动查询，有轮询间隔和最大等待时间限制
   - Callback：外部系统主动通知，无轮询间隔，实时性更好

4. **实现位置**：核心逻辑在 `UniformAPIService` 类中，通过 `plugin_schedule` 方法统一调度，根据配置选择对应的处理函数。

