### 资源描述

撤回 token

该接口将匹配记录的 `expired_time` 更新为当前时间，不删除记录，也不终止已运行的任务。多个过滤条件共同生效。

接口要求网关应用认证及资源权限，并校验应用与空间的绑定关系；不要求网关用户认证。请求中的 `user` 是撤销对象的过滤条件。

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| access_token  | string | 否  | 用户或应用 access_token，详情参考 AccessToken API                    |

#### 接口参数

注意: 以下参数将作为对应空间下 token 失效的过滤参数，如果不传任何参数，则所有 token 失效（将 token 的过期时间设置为当前时间）。所以，在调用此接口时，请保证过滤范围尽量精确。

| 字段              | 类型     | 必选      | 描述                           |
|-----------------|--------|---------|------------------------------|
| resource_type   | string | 否       | 资源类型：TEMPLATE、TASK、SCOPE、LABEL；LABEL 目前不能通过 apply_token 签发 |
| resource_id     | string | 否       | 资源的ID                        |
| permission_type | string | 否       | 权限类型                         |
| user            | string | 否       | 被授权用户名 |
| token           | string | 否       | token                        |

### permission_type 说明:

过滤字段接受 VIEW、EDIT、OPERATE、MOCK，表示只撤销相同权限类型的记录，不会按权限包含关系扩大过滤范围。例如，传 `permission_type=VIEW` 不会一并撤销 EDIT 或 OPERATE 票据。

通常模板使用 VIEW / EDIT / MOCK，任务使用 VIEW / OPERATE，作用域使用 VIEW / EDIT / OPERATE / MOCK。需要撤销某用户对目标资源的全部票据时，应省略 `permission_type` 并保留用户、资源等范围条件。

### 请求参数示例

以下为精确撤销一张票据的业务请求体；应用认证材料需按网关协议另行提供。

```json
{
  "token": "<BKFLOW_TOKEN>"
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": "1 tokens revoke success",
    "message": "",
    "code": 0
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | string | 匹配并更新的记录数量说明，不代表这些记录此前全部有效 |

### 当前实现边界

当前撤销依赖到期时间，没有独立的不可恢复撤销标记；续期路径对过期记录的检查也不完整，存在原票据被续活的风险。因此，撤销成功只表示到期时间已更新，不能当作永久禁止原票据恢复的保证。接入方需结合部署版本核对续期行为及后续资源访问结果。
