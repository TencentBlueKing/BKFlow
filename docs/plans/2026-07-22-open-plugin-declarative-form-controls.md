# Open Plugin Declarative Form Controls Implementation Plan

> **Goal:** Render the standard declarative controls supplied by API plugin providers, including a real Monaco code editor, while preserving compatibility with flat inputs and safely degrading unknown controls.

## Task 1: Normalize supported controls and fallback behavior

**Files:**
- Modify: `frontend/src/utils/jsonFormSchema.js`
- Modify: `frontend/tests/jsonFormSchema.test.js`

1. Add failing tests for flat `password`, flat `code_editor`, structured `codeEditor`, and unknown-control fallback.
2. Normalize `textarea` and `password` to `bfInput` with the corresponding input type.
3. Normalize `code_editor` to the registered `codeEditor` control.
4. Preserve rules and reactions while replacing unknown controls with the inferred base widget.

Run:

```bash
npm run test:json-form-schema
```

## Task 2: Register the Monaco-backed code editor

**Files:**
- Create: `frontend/src/components/common/ApiCodeEditor.vue`
- Modify: `frontend/src/components/common/ApiUniForm.vue`
- Modify: `tests/plugins/uniform_api/test_api_plugin_vue.py`

1. Add failing source-contract tests for custom component registration and Monaco wrapping.
2. Implement a `v-model` compatible wrapper around `FullCodeEditor`.
3. Register `codeEditor` through `createForm({ components })`.
4. Propagate language, height, readonly, disabled, and minimap options.

## Task 3: Document and verify

**Files:**
- Modify: `docs/specs/2026-06-26-sops-open-plugin-full-capability-design.md`
- Modify: `docs/guide/api_plugin.md`

Document the standard-control vocabulary and the fallback boundary, then run focused Python tests, frontend schema tests, ESLint, and the development build.
