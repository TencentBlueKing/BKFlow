### 租户访问约束

开启多租户时，全租户应用必须通过 `X-Bk-Tenant-Id` 指定本次请求租户；单租户应用可省略该头，使用 JWT 中已认证的应用租户，显式传入时必须一致。本次请求租户必须与资源所属空间租户一致；同一个全租户应用应在各租户分别创建空间。原有应用与空间/模板绑定仍需满足。若 JWT 包含已认证用户，其租户也必须一致。缺少或不匹配时拒绝请求。

应用态接口不要求额外用户身份。SDK 用户态接口仍要求已认证用户，平台管理员和空间管理员同样不能跨租户。关闭多租户模式时保持单租户行为。

### 资源描述

获取任务操作记录

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 路径参数:

| 字段         | 类型    | 必选   | 描述     |
|------------|-------|------|--------|
| space_id   | int   | 是    | 空间ID   |
| task_id    | int   | 是    | 任务ID   |

#### 接口参数

| 字段      | 类型     | 必选 | 描述   |
|---------|--------|----|------|
| node_id | string | 否  | 节点ID |

### 返回结果示例

```json
{
    "result": true,
    "message": "success",
    "data": [
        {
            "id": 5,
            "operator": "xxx",
            "instance_id": 3,
            "operate_date": "2024-09-24T15:29:29.078977+08:00",
            "extra_info": {},
            "node_id": "",
            "operate_type": "create",
            "operate_source": "api",
            "operate_type_name": "创建",
            "operate_source_name": "api 接口"
        }
    ]
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |


#### data[item]

| 字段                  | 类型      | 描述             |
|---------------------|---------|----------------|
| id                  | int     | 操作记录ID         |
| operator            | string  | 操作人            |
| instance_id         | int     | 任务实例ID         |
| operate_date        | string  | 操作时间           |
| extra_info          | object  | 扩展信息           |
| node_id             | string  | 节点ID，为空表示任务级操作 |
| operate_type        | string  | 操作类型           |
| operate_source      | string  | 操作来源           |
| operate_type_name   | string  | 操作类型名称         |
| operate_source_name | string  | 操作来源名称         |