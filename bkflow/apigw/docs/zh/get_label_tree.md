### 资源描述

获取标签树

### 输入通用参数说明

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| bk_app_code | string | 是 | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| bk_app_secret | string | 是 | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

#### 接口参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| label_scope | string | 否 | 标签范围筛选，可选值：`task`、`template`、`common` |
| task_ids | string | 否 | 任务ID列表，逗号分隔，如 `1,2,3`。传入后仅返回这些任务已关联的标签及其所有祖先标签 |
| template_ids | string | 否 | 流程模板ID列表，逗号分隔，如 `10,11`。传入后仅返回这些模板已关联的标签及其所有祖先标签 |
| offset | int | 否 | 根节点分页偏移量（仅对根节点分页，不会拆分子树） |
| limit | int | 否 | 根节点分页数量（仅对根节点分页，不会拆分子树），最大200 |

### 说明

- 当 `task_ids` 和 `template_ids` 都不传时：返回指定范围下的完整标签树。
- 当传入 `task_ids` 或 `template_ids` 时：返回“被引用的标签 + 所有祖先标签”组成的树。

### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "label_scope": "task",
    "task_ids": "1001,1002",
    "offset": 0,
    "limit": 50
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": [
        {
            "id": 1,
            "name": "父标签",
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
            "full_path": "父标签",
            "parent_id": null,
            "children": [
                {
                    "id": 2,
                    "name": "子标签",
                    "creator": "tester",
                    "updated_by": "tester",
                    "space_id": 1,
                    "color": "#ffffff",
                    "description": "",
                    "created_at": "2024-08-02T08:53:20.173Z",
                    "updated_at": "2024-08-02T08:53:20.173Z",
                    "label_scope": ["task"],
                    "is_default": false,
                    "has_children": false,
                    "full_path": "父标签/子标签",
                    "parent_id": 1,
                    "children": []
                }
            ]
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
| count | int | 根节点数量（分页前） |
| data | list | 标签树（根节点列表） |

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
| has_children | bool | 是否有子标签（树结构中会根据 children 进行填充） |
| full_path | string | 标签完整路径 |
| parent_id | int/null | 父标签ID |
| children | list | 子节点列表（递归结构） |
