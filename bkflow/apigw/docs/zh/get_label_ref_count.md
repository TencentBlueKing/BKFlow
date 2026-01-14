### 资源描述

获取标签引用数量

### 输入通用参数说明

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| bk_app_code | string | 是 | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| bk_app_secret | string | 是 | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

#### 接口参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| label_ids | string | 是 | 标签ID列表，逗号分隔，如 `1,2,3` |

### 说明

- 若传入的 `label_id` 为根标签且存在子标签：返回该根标签的引用数量为“**所有子标签**”的引用数量之和。
- 任务引用数量通过任务模块接口获取。

### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "label_ids": "1,2,3"
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "1": {
            "template_count": 2,
            "task_count": 5
        },
        "2": {
            "template_count": 0,
            "task_count": 1
        }
    },
    "code": 0
}
```

### 返回结果参数说明

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| result | bool | 返回结果，true为成功，false为失败 |
| code | int | 返回码，0表示成功，其他值表示失败 |
| message | string | 错误信息 |
| data | dict | 返回数据，key 为 label_id 字符串 |

#### data[label_id]

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| template_count | int | 模板引用数量 |
| task_count | int | 任务引用数量 |
