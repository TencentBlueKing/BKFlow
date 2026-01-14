### 资源描述

更新标签

### 输入通用参数说明

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| bk_app_code | string | 是 | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| bk_app_secret | string | 是 | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

#### 接口参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| name | string | 否 | 标签名称 |
| color | string | 否 | 标签颜色，格式如 `#ffffff` |
| label_scope | list | 否 | 标签范围（多选），可选值：`task`、`template`、`common`。更新父标签范围时，必须覆盖所有子标签的范围 |
| description | string | 否 | 标签描述 |

### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "name": "新标签名",
    "color": "#ffffff",
    "label_scope": ["task", "common"],
    "description": ""
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "id": 1,
        "name": "新标签名",
        "creator": "tester",
        "updated_by": "tester",
        "space_id": 1,
        "color": "#ffffff",
        "description": "",
        "created_at": "2024-08-02T08:53:20.173Z",
        "updated_at": "2024-08-02T08:53:20.173Z",
        "label_scope": ["task", "common"],
        "is_default": false,
        "has_children": false,
        "full_path": "新标签名",
        "parent_id": null
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
| data | dict | 返回数据 |

#### data

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| id | int | 标签ID |
| name | string | 标签名称 |
| creator | string | 创建者 |
| updated_by | string | 更新者 |
| space_id | int | 空间ID（默认标签可能为 -1） |
| color | string | 标签颜色 |
| description | string | 标签描述 |
| created_at | string | 创建时间 |
| updated_at | string | 更新时间 |
| label_scope | list | 标签范围 |
| is_default | bool | 是否默认标签 |
| has_children | bool | 是否有子标签 |
| full_path | string | 标签完整路径 |
| parent_id | int/null | 父标签ID |
