### 资源描述

获取任务详情

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

#### 接口参数

| 字段              | 类型     | 必选 | 描述                           |
|-----------------|--------|----|------------------------------|
| limit           | int    | 否  | 每页的数量, limit 最大数量为200        |
| offset          | int    | 否  | 偏移量                          |
| name            | string | 否  | 流程名   模糊匹配                   |
| creator         | string | 否  | 创建者   精确匹配                   |
| updated_by      | string | 否  | 更新人   精确匹配                   |
| scope_type      | string | 否  | 流程范围   精确匹配                  |
| scope_value     | string | 否  | 流程范围值   精确匹配                 |
| create_at_start | string | 否  | 创建起始时间，如 2023-08-25 07:49:45 |
| create_at_end   | string | 否  | 创建结束时间，如 2023-08-25 07:49:46 |
| order_by        | string | 否  | 排序字段，默认按照创建时间降序              |

### 返回结果示例

```json
{
    "result": true,
    "data": [
        {
            "id": 618,
            "space_id": 1,
            "name": "测试模板",
            "desc": null,
            "notify_config": {},
            "scope_type": null,
            "scope_value": null,
            "source": null,
            "version": "",
            "is_enabled": true,
            "extra_info": {},
            "creator": "",
            "create_at": "2024-07-30T06:27:52.642Z",
            "update_at": "2024-07-30T07:30:28.005Z",
            "updated_by": ""
        }
    ],
    "count": 10,
    "code": 0
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |

##### data[item]

| 字段            | 类型     | 描述     |
|---------------|--------|--------|
| id            | int    | 流程id   |
| space_id      | int    | 流程空间id |
| name          | string | 流程名称   |
| desc          | string | 流程描述   |
| notify_config | dict   | 流程通知配置 |
| scope_type    | string | 流程范围类型 |
| scope_value   | string | 流程范围值  |
| source        | string | 流程来源   |
| version       | string | 流程版本   |
| is_enabled    | bool   | 流程是否启用 |
| extra_info    | dict   | 流程扩展信息 |
| creator       | string | 流程创建者  |
| create_at     | string | 流程创建时间 |
| update_at     | string | 流程更新时间 |
| updated_by    | string | 流程更新者  |
