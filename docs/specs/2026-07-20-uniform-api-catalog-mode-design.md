# Uniform API Catalog Mode Design

## Goal

Allow each Uniform API entry to use the synchronized open-plugin catalog as a
query acceleration layer while keeping remote querying available.

## Configuration

Each `uniform_api.api` entry accepts `catalog_mode`:

- `remote` (default): always query the configured remote URL.
- `cache_first`: return the local catalog when the base catalog is initialized;
  otherwise query remote and asynchronously request a catalog synchronization.
- `cache_only`: return the local catalog, or raise an explicit error when the
  base catalog is not initialized. It never queries remote.

The fixed `plugin_source` query parameter is read from each configured
`meta_apis` or `api_categories` URL. No duplicate source-type configuration is
introduced.

## Cache Semantics

Catalog initialization is checked by `space_id + source_key + plugin_source`
before availability, category, keyword, or pagination filters are applied.
Therefore, an initialized catalog whose filtered result is empty returns an
empty result and does not fall back to remote.

Only available and space-enabled plugins are visible. Platform source grants
remain mandatory. List responses retain the Uniform API list schema, and
category responses are derived from the same visible plugin set.

Remote fallback schedules an existing source synchronization task behind a
short cache-based deduplication lock. Plugin detail, execution, polling, and
callback requests remain remote.
