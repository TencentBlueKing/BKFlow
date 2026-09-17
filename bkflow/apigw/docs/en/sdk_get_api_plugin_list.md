### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get Uniform API plugins (SDK endpoint)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### HTTP header parameters

| Parameter         | Type   | Required | Description                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW-TOKEN | string | Yes  | Access token obtained from `/space/{space_id}/apply_token/`. This token verifies the user's permission to access resources in the specified space (template_id or task_id is required). |

### Path parameters

| Field            | Type     | Required | Description      |
|---------------|--------|----|---------|
| space_id      | string | Yes  | Space ID    |

### Endpoint parameters

| Field          | Type      | Required | Description                                                                                  |
|-------------|---------|----|-------------------------------------------------------------------------------------|
| template_id | int     | No  | Template ID                                                                                |
| task_id     | string  | No  | Task ID                                                                                |
| limit       | int     | No  | Page size; default: 50                                                                          |
| offset      | int     | No  | Pagination offset; default: 0                                                                         |
| scope_type  | string  | No  | Business scope type                                                                              |
| scope_value | string  | No  | Business scope value                                                                               |
| category    | string  | No  | Category identifier for filtering plugins                                                                      |
| key         | string  | No  | Group/keyword identifier                                                                            |
| api_name    | string  | No  | Uniform API api_key; defaults to the integrator's default API_KEY and selects the Uniform API list configuration             |

Note: supply at least one of template_id and task_id.

### Request example

```
GET /sdk/plugin_query/uniform_api/list/{space_id}/?template_id=10&category=model&limit=50&offset=0
```

### Response example

The response structure depends on the integrating platform's `catalog_mode`, with two forms:

- **Remote passthrough (remote, default):** the backend forwards the upstream Uniform API response. The integrator defines its structure, including optional fields such as `display_content`.
- **Cache mode (cache_first / cache_only with initialized catalog cache):** the backend returns locally cached open plugin catalog data in a fixed structure (see the cache example below).

> The default mode is remote. Cache mode is used only when the integrator configures `catalog_mode` as `cache_first` or `cache_only` and initializes the catalog cache; requests do not all switch automatically. Actual responses use the standard gateway wrapper `{ "result": true, "code": "0", "message": "", "data": {...} }`. Descriptions below refer to the inner data structure.

#### Remote passthrough example

```json
{
  "result": true,
  "code": "0",
  "message": "",
  "data": {
    "total": 1,
    "apis": [
      {
        "id": "model-65",
        "name": "test",
        "alias": "test",
        "meta_url": "xxx",
        "category": "model",
        "group": "llm",
        "plugin_type": "uniform_api",
        "version": "v3.0.0",
        "display_content": {
          "llm_code": "test",
          "llm_name": "test",
          "base_model": "qwen",
          "context_length": "128K",
          "created_at": "2026-04-15 21:35:10",
          "created_by": "xxx",
          "description": "基于模型能力与资源情况推荐的大语言模型，当前指向 qwen3-5-397B",
          "icon": "xxx",
          "tag_names": [["工具调用"],["图生文"],["多轮会话"],["知识摘要"]]
        },
        "source_key": "aidev"
      }
    ]
  }
}
```

#### Cache mode example

```json
{
  "result": true,
  "code": "0",
  "message": "",
  "data": {
    "total": 1,
    "apis": [
      {
        "id": "plugin-xxx",
        "name": "通用HTTP请求",
        "plugin_source": "builtin",
        "plugin_code": "http_request",
        "wrapper_version": "1.0.0",
        "default_version": "1.0.0",
        "latest_version": "1.2.0",
        "versions": ["1.0.0", "1.1.0", "1.2.0"],
        "meta_url_template": "http://example.com/meta/{plugin_code}",
        "source_key": "aidev",
        "category": "network",
        "category_name": "网络",
        "description": "通用HTTP请求插件"
      }
    ]
  }
}
```

### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| code    | string | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | dict   | Response data                  |

#### Data fields

| Field   | Type  | Description            |
|------|-----|---------------|
| total | int | Total plugin count          |
| apis | list | Uniform API plugin list (see fields for each mode below) |

#### apis[item] fields in remote passthrough mode

> The upstream integrator defines this structure. Fields below are examples; use the actual upstream response. Extensions such as `display_content` depend on the upstream implementation and may differ by category.

| Field             | Type     | Description                                   |
|----------------|--------|--------------------------------------|
| id             | string | Plugin ID                                 |
| name           | string | Plugin name                                 |
| alias          | string | Plugin alias                                 |
| meta_url       | string | Metadata URL                               |
| category       | string | Category identifier                                 |
| group          | string | Group identifier                                 |
| plugin_type    | string | Plugin type, fixed to uniform_api                  |
| version        | string | Plugin version                                 |
| display_content | dict  | Display content defined by the upstream implementation; fields vary (see example display_content fields) |
| source_key     | string | Uniform API source identifier, matching the integrator's source_key         |

#### Example display_content fields (upstream-dependent)

| Field             | Type      | Description                                   |
|----------------|---------|--------------------------------------|
| llm_code       | string  | LLM code                                |
| llm_name       | string  | LLM name                                |
| base_model      | string  | Base model                                 |
| context_length  | string  | Context length (such as 128K)                        |
| created_at      | string  | Creation time (YYYY-MM-DD HH:mm:ss)          |
| created_by      | string  | Created by                                  |
| description     | string  | Plugin description                                 |
| icon            | string  | Icon URL                                 |
| tag_names       | list   | Tag list, with each tag in a single-element array (such as `[["Tool calling"],["Image to text"]]`) |

#### apis[item] fields in cache mode

> Returned only when `catalog_mode` is `cache_first` / `cache_only` and the catalog cache is initialized. Uses the fixed local open plugin catalog structure from `_build_cached_catalog_data`.

| Field              | Type     | Description                                       |
|-----------------|--------|------------------------------------------|
| id              | string | Plugin ID (plugin_id)                         |
| name            | string | Plugin name (plugin_name)                     |
| plugin_source   | string | Plugin source (such as builtin)                            |
| plugin_code     | string | Plugin code                                  |
| wrapper_version | string | Wrapper version                                     |
| default_version | string | Default version                                     |
| latest_version  | string | Latest version                                     |
| versions        | list   | Available version list                                   |
| meta_url_template | string | Metadata URL template (with a `{plugin_code}` placeholder)           |
| source_key      | string | Uniform API source identifier                              |
| category        | string | Category identifier (group_name)                       |
| category_name   | string | Category name (group_display_name)                 |
| description     | string | Plugin description                                     |

> Cache mode **does not include** fields such as `alias`, `meta_url`, `group`, `plugin_type`, `version`, or `display_content`. An SDK reading these from the remote example will get missing/empty values in cache mode. Check the target space's `catalog_mode` before calling.
