### 资源描述

获取标签列表

### 输入通用参数说明

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| bk_app_code | string | 是 | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| bk_app_secret | string | 是 | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

#### 接口参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| offset | int | 否 | 偏移量，默认0 |
| limit | int | 否 | 返回数量，默认100，最大200 |
| label_scope | string | 否 | 标签范围筛选，可选值：`task`、`template`、`common` |
| parent_id | int | 否 | 父标签ID。不传时，接口会返回根标签（并兼容把子标签的父节点也包含在返回结果中） |
| name | string | 否 | 标签名称，模糊匹配 |
| is_default | bool | 否 | 是否默认标签 |
| order_by | string | 否 | 排序字段，默认 `-updated_at`，允许值：`created_at`、`updated_at`、`name`、`-created_at`、`-updated_at`、`-name` |

### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "offset": 0,
    "limit": 20,
    "label_scope": "task"
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": [
        {
            "id": 1,
            "name": "标签名",
            "creator": "tester",
            "updated_by": "tester",
            "space_id": 1,
            "color": "#ffffff",
            "description": "",
            "created_at": "2024-08-02T08:53:20.173Z",
            "updated_at": "2024-08-02T08:53:20.173Z",
            "label_scope": ["task"],
            "is_default": false,
            "has_children": true,
            "full_path": "标签名",
            "parent_id": null
        }
    ],
    "count": 1,
    "code": 0
}
```

### 返回结果参数说明

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| result | bool | 返回结果，true为成功，false为失败 |
| code | int | 返回码，0表示成功，其他值表示失败 |
| message | string | 错误信息 |
| count | int | 数据总数 |
| data | list | 返回数据 |

#### data[item]

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
