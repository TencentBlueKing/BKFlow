# Open Plugin Unified Form Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make BKFlow built-in plugins, BKFlow third-party plugins, and bk-sops built-in/third-party V4 plugins use the existing `RenderForm` renderer across template editing and task detail views.

**Architecture:** Keep `RenderForm` and its Tag registry unchanged. Extend `renderFormSchema.js` into the uniform API protocol adapter that accepts either flat `inputs` or structured `form_schema` and always returns a `RenderForm` array schema; all uniform API rendering entry points use this adapter. Retain JSON Schema components only for non-plugin compatibility paths.

**Tech Stack:** Vue 2.7, JavaScript, existing `RenderForm` Tag components, Node-based focused tests, pytest source-contract tests.

## Global Constraints

- Do not add a second API-plugin-specific form renderer or code editor.
- Do not execute provider-supplied JavaScript or translate `ui:reactions` into executable functions.
- Preserve flat `inputs` compatibility and fall back to it when `form_schema` is absent or invalid.
- Unknown declarative controls fall back to a type-inferred existing Tag.
- Preserve falsy option/default values such as `0`, `false`, and `""`.
- Use TAPD story `133649781` for every commit.

---

### Task 1: Uniform API to RenderForm adapter

**Files:**
- Modify: `frontend/src/utils/renderFormSchema.js`
- Create: `frontend/tests/renderFormSchema.test.js`
- Modify: `frontend/package.json`

**Interfaces:**
- Consumes: uniform API detail `{ inputs?: Array, form_schema?: Object }` or an existing flat field array.
- Produces: `renderFormSchema(data, config = {}) -> Array<{ type, tag_code, attrs }>`.

- [ ] **Step 1: Write failing adapter tests**

Add a CommonJS/Babel loader like the existing JSON schema test and cover the exact contracts:

```js
const schema = renderFormSchema({
  inputs: [{ key: 'job_content', name: '脚本内容', type: 'string', required: true }],
  form_schema: {
    type: 'object',
    required: ['job_content'],
    properties: {
      job_content: {
        type: 'string',
        title: '脚本内容',
        default: '',
        'ui:component': {
          name: 'codeEditor',
          props: { language: 'shell', height: '400px', showMiniMap: false },
        },
      },
    },
  },
});
assert.strictEqual(schema[0].type, 'code_editor');
assert.strictEqual(schema[0].attrs.language, 'shell');
assert.strictEqual(schema[0].attrs.height, '400px');
assert.deepStrictEqual(schema[0].attrs.validation, [{ type: 'required' }]);
assert.strictEqual(schema[0].attrs.default, '');
```

Also test `textarea`, `password`, `select`, `radio`, `checkbox`, `switcher`, object-array `table`, invalid structured schema fallback, unknown component fallback, and options whose values are `0`, `false`, and `""`.

- [ ] **Step 2: Run the test and verify failure**

Run:

```bash
cd frontend && node tests/renderFormSchema.test.js
```

Expected: FAIL because object detail input and structured component metadata are not supported.

- [ ] **Step 3: Implement the adapter**

Keep the public function name and array-input compatibility. Add focused helpers with these responsibilities:

```js
const COMPONENT_TYPE_MAP = {
  input: 'input',
  'bk-input': 'input',
  bfInput: 'input',
  textarea: 'textarea',
  password: 'password',
  codeEditor: 'code_editor',
  code_editor: 'code_editor',
  'code-editor': 'code_editor',
  select: 'select',
  radio: 'radio',
  checkbox: 'checkbox',
  switcher: 'switch',
  table: 'datatable',
};

function normalizeOption(item) {
  if (item && typeof item === 'object') {
    return {
      text: item.label || item.text || String(item.value),
      value: Object.prototype.hasOwnProperty.call(item, 'value') ? item.value : item,
    };
  }
  return { text: String(item), value: item };
}

function resolveFields(data) {
  if (Array.isArray(data)) return data;
  if (data?.form_schema?.properties && typeof data.form_schema.properties === 'object') {
    return structuredPropertiesToFields(data.form_schema, data.inputs || []);
  }
  return Array.isArray(data?.inputs) ? data.inputs : [];
}

export default function renderFormSchema(data = [], config = {}) {
  return resolveFields(data).map(field => buildRenderFormField(field, config));
}
```

`structuredPropertiesToFields` must merge each property with the same-key flat input, use `form_schema.required`, and preserve declarative component props. `buildRenderFormField` must infer a safe fallback Tag from JSON Schema type and map object arrays recursively to `attrs.columns`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
cd frontend && node tests/renderFormSchema.test.js
```

Expected: `renderFormSchema tests passed`.

- [ ] **Step 5: Register the focused test command and commit**

Add:

```json
"test:render-form-schema": "node tests/renderFormSchema.test.js"
```

Commit:

```bash
git add frontend/src/utils/renderFormSchema.js frontend/tests/renderFormSchema.test.js frontend/package.json
git commit -m "feat(open-plugin): 统一 API 插件表单适配器 --story=133649781"
```

### Task 2: Template editor and variable-hook path

**Files:**
- Modify: `frontend/src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue`
- Modify: `frontend/src/views/template/TemplateEdit/NodeConfig/InputParams.vue`
- Modify: `tests/plugins/uniform_api/test_api_plugin_vue.py`

**Interfaces:**
- Consumes: `renderFormSchema(resp.data, { readOnly })` from Task 1 and raw `resp.data.inputs`.
- Produces: array `inputs` for `InputParams`, while preserving uniform API variable metadata and reuse checks.

- [ ] **Step 1: Write failing source-contract tests**

Assert the real node editor imports and calls `renderFormSchema`, no longer imports `jsonFormSchema`, passes `apiInputs` into `InputParams`, and keeps API-specific variable behavior independent from `isJsonSchema`:

```python
assert "import renderFormSchema from '@/utils/renderFormSchema.js'" in node_config
assert "return renderFormSchema(resp.data" in node_config
assert ':api-inputs="apiInputs"' in node_config
assert "if (this.isApiPlugin)" in input_params
assert "const schema = this.apiInputs.find(item => item.key === form)" in input_params
```

- [ ] **Step 2: Run the test and verify failure**

Run:

```bash
pytest tests/plugins/uniform_api/test_api_plugin_vue.py -v
```

Expected: FAIL because the template editor still uses `jsonFormSchema` and `InputParams` reads object properties.

- [ ] **Step 3: Switch the node editor adapter**

In `NodeConfig.vue`, replace the uniform API import/call with:

```js
import renderFormSchema from '@/utils/renderFormSchema.js';
// ...
this.apiInputs = Array.isArray(resp.data.inputs) ? resp.data.inputs : [];
return renderFormSchema(resp.data, { readOnly: this.isViewMode });
```

Pass `:api-inputs="apiInputs"` to `InputParams`.

- [ ] **Step 4: Preserve API variable behavior with array schemas**

Add an `apiInputs` array prop to `InputParams.vue`. Use `isApiPlugin`, not schema shape, for uniform API metadata comparison and variable defaults:

```js
const currentInput = this.apiInputs.find(item => item.key === form);
const sourceInput = (resp.data.inputs || []).find(item => item.key === form);
isSame = tools.isDataEqual(sourceInput, currentInput);
```

For API variables, keep `form_schema = {}`, `plugin_code = ''`, wrapper version behavior, and build `extra_info` from `apiInputs`:

```js
const schema = this.apiInputs.find(item => item.key === form) || {};
defaultOpts.extra_info = {
  type: schema.type || 'string',
  ...(schema.meta_desc ? { meta_desc: schema.meta_desc } : {}),
  ...(schema.form_type ? { form_type: schema.form_type } : {}),
  ...(schema.required ? { required: true } : {}),
};
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
pytest tests/plugins/uniform_api/test_api_plugin_vue.py -v
cd frontend && npm run test:render-form-schema
```

Commit:

```bash
git add frontend/src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue frontend/src/views/template/TemplateEdit/NodeConfig/InputParams.vue tests/plugins/uniform_api/test_api_plugin_vue.py
git commit -m "fix(open-plugin): 统一模板编辑表单渲染 --story=133649781"
```

### Task 3: Task detail and mock rendering entry points

**Files:**
- Modify: `frontend/src/views/task/TaskExecute/ExecuteInfo.vue`
- Modify: `frontend/src/views/task/TaskExecute/SideDrawerExecuteInfo.vue`
- Modify: `frontend/src/views/task/TaskExecute/ExecuteInfo/ExecuteInfoForm.vue`
- Modify: `frontend/src/views/task/TaskExecute/ExecuteInfoCompoment/ExecuteInfoForm.vue`
- Modify: `frontend/src/views/template/TemplateMock/MockSetting/index.vue`
- Modify: `tests/plugins/uniform_api/test_api_plugin_vue.py`

**Interfaces:**
- Consumes: Task 1 adapter output.
- Produces: array schema in every uniform API read-only/detail/mock path so existing `RenderForm` branches render all four plugin kinds.

- [ ] **Step 1: Add failing entry-point tests**

Read each file and assert it imports `renderFormSchema`, calls `renderFormSchema(resp.data, ...)`, and does not call `jsonFormSchema(resp.data, ...)`. For both `ExecuteInfoForm.vue` files, also assert API initialization computes hooks from array schemas instead of calling object-only `setFormsSchema`.

- [ ] **Step 2: Run the test and verify failure**

Run:

```bash
pytest tests/plugins/uniform_api/test_api_plugin_vue.py -v
```

Expected: FAIL listing the task/mock files that still return object schemas.

- [ ] **Step 3: Switch all uniform API entry points**

Replace each API-only call with:

```js
renderFormSchema(resp.data, { readOnly: true })
```

or, where editability is available:

```js
renderFormSchema(resp.data, { readOnly: this.isViewMode })
```

Do not remove generic JSON-schema components; they remain the fallback for non-plugin callers.

- [ ] **Step 4: Align task detail hook display**

In both `ExecuteInfoForm.vue` variants, remove API calls to object-only `setFormsSchema(renderConfig)`. After assigning the array to `this.inputs`, compute `this.hooked = this.getFormsHookState()` whenever `Array.isArray(this.inputs)` so variable-backed API fields display through the same `RenderForm` behavior as other plugins.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
pytest tests/plugins/uniform_api/test_api_plugin_vue.py -v
cd frontend && npm run test:render-form-schema
```

Commit:

```bash
git add frontend/src/views/task/TaskExecute frontend/src/views/template/TemplateMock/MockSetting/index.vue tests/plugins/uniform_api/test_api_plugin_vue.py
git commit -m "fix(open-plugin): 统一任务详情表单渲染 --story=133649781"
```

### Task 4: Remove the abandoned parallel renderer

**Files:**
- Delete: `frontend/src/components/common/ApiCodeEditor.vue`
- Modify: `frontend/src/components/common/ApiUniForm.vue`
- Modify: `frontend/src/utils/jsonFormSchema.js`
- Delete: `frontend/tests/jsonFormSchema.test.js`
- Modify: `frontend/package.json`
- Modify: `tests/plugins/uniform_api/test_api_plugin_vue.py`

**Interfaces:**
- Consumes: all uniform API rendering paths now use Task 1.
- Produces: no dead API-specific code-editor registration and no V4 structured-form logic duplicated in `jsonFormSchema.js`.

- [ ] **Step 1: Add failing cleanup assertions**

Assert `ApiCodeEditor.vue` does not exist, `ApiUniForm.vue` does not register `codeEditor`, and uniform API runtime entry points do not use `jsonFormSchema`.

- [ ] **Step 2: Run the test and verify failure**

Run:

```bash
pytest tests/plugins/uniform_api/test_api_plugin_vue.py -v
```

Expected: FAIL while the abandoned component and registry remain.

- [ ] **Step 3: Remove only the superseded implementation**

Delete `ApiCodeEditor.vue`, remove its import and `createForm({ components: ... })` registration from `ApiUniForm.vue`, but retain the `meta_url_template` and `version` request parameters already added there. Restore `jsonFormSchema.js` to its pre-structured-form responsibility and remove its dedicated test/script because V4 conversion now belongs exclusively to `renderFormSchema.js`.

- [ ] **Step 4: Run focused tests and commit**

Run:

```bash
pytest tests/plugins/uniform_api/test_api_plugin_vue.py -v
cd frontend && npm run test:render-form-schema
```

Commit:

```bash
git add -A frontend/src/components/common/ApiCodeEditor.vue frontend/src/components/common/ApiUniForm.vue frontend/src/utils/jsonFormSchema.js frontend/tests frontend/package.json tests/plugins/uniform_api/test_api_plugin_vue.py
git commit -m "refactor(open-plugin): 删除重复表单渲染实现 --story=133649781"
```

### Task 5: Full frontend verification and PR update

**Files:**
- Modify if needed: files changed in Tasks 1-4 only.

**Interfaces:**
- Consumes: complete unified rendering implementation.
- Produces: lint-clean, buildable branch pushed to the existing PR.

- [ ] **Step 1: Run focused tests**

```bash
pytest tests/plugins/uniform_api/test_api_plugin_vue.py tests/plugins/uniform_api/test_uniform_api_client.py -v
cd frontend && npm run test:render-form-schema
```

Expected: all pass.

- [ ] **Step 2: Run ESLint on changed frontend files**

```bash
cd frontend && npx eslint \
  src/utils/renderFormSchema.js \
  src/components/common/ApiUniForm.vue \
  src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue \
  src/views/template/TemplateEdit/NodeConfig/InputParams.vue \
  src/views/template/TemplateMock/MockSetting/index.vue \
  src/views/task/TaskExecute/ExecuteInfo.vue \
  src/views/task/TaskExecute/SideDrawerExecuteInfo.vue \
  src/views/task/TaskExecute/ExecuteInfo/ExecuteInfoForm.vue \
  src/views/task/TaskExecute/ExecuteInfoCompoment/ExecuteInfoForm.vue
```

Expected: exit code 0.

- [ ] **Step 3: Build development assets**

```bash
cd frontend && npm run build:development
```

Expected: webpack build succeeds; warnings are recorded separately from errors.

- [ ] **Step 4: Check branch scope and push**

```bash
git status --short
git diff --check origin/fix/open-plugin-form-schema...HEAD
git push origin fix/open-plugin-form-schema
```

Expected: clean worktree, no whitespace errors, existing PR #818 updated without creating a new PR.
