# Uniform API Catalog Mode Plan

Spec: `docs/specs/2026-07-20-uniform-api-catalog-mode-design.md`

1. Add configuration validation tests for `remote`, `cache_first`, and
   `cache_only`, including the default and invalid values.
2. Add catalog service tests for initialization checks and complete cached list
   fields.
3. Add query tests covering remote mode, cache hits, filtered-empty results,
   cache-first fallback, cache-only errors, and category derivation.
4. Implement catalog mode parsing and cached list/category conversion.
5. Deduplicate asynchronous synchronization requests after successful remote
   fallback.
6. Run focused Uniform API and open-plugin catalog regression tests.

Test command:

```bash
export $(cat tests/interface.env | xargs)
.venv/bin/pytest tests/interface/space/test_space_config.py \
  tests/interface/plugin/services/test_open_plugin_catalog.py \
  tests/interface/test_uniform_api_catalog_mode.py -v
```
