### 资源描述

查看流程快照列表（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| HTTP_BKFLOW_TOKEN | string | 是  | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 接口申请。该 token 用于验证用户对指定空间资源的访问权限（需要提供 template_id 或 task_id） |

### 接口参数

| 字段          | 类型     | 必选 | 描述      |
|-------------|--------|----|---------|
| template_id | string | 是  | 流程ID    |
| version     | string | 否  | 流程快照版本号 |
| operator    | string | 否  | 操作人     |
| desc        | string | 否  | 流程版本描述  |


### 请求参数示例

```
POST /sdk/template/snapshot/list_snapshot/
```

### 返回结果示例

```json
{
     "count": 3,
     "next": null,
     "previous": null,
     "results": [
          {
               "id": 123,
               "create_time": "2025-05-22 11:00:20+0800",
               "update_time": "2025-05-22 11:00:20+0800",
               "version": null,
               "template_id": 1023,
               "desc": "基于 1.0.0 版本的草稿",
               "draft": true,
               "creator": "xxx",
               "operator": "xxx",
               "md5sum": "18ce84fe15xlt0075edc4413a9f5575b"
          }
     ]
}
```

### 返回结果参数说明

| 字段       | 类型       | 描述       |
|----------|----------|----------|
| count    | int      | 分页返回数据总数 |
| result   | list     | 返回数据     |


#### data 字段说明

| 字段             | 类型     | 描述              |
|----------------|--------|-----------------|
| create_time    | string | 数据创建时间          |
| update_time    | string | 数据更新时间          |
| version        | string | 流程版本号（草稿版本无版本号） |
| template_id    | string | 关联的模板id         |
| desc           | string | 流程版本描述          |
| draft          | bool   | 是否是操作版本         |
| creator        | string | 创建人             |
| operator       | string | 操作人             |
| md5sum         | string | 流程数据的md5值       |
