import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(new URL('../src/utils/uniformApi.js', import.meta.url), 'utf8');
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const {
  buildUniformApiMetaParams,
  resolveUniformApiPluginVersion,
} = await import(moduleUrl);

test('resolveUniformApiPluginVersion uses the saved business version', () => {
  const component = {
    version: 'v4.0.0',
    data: {
      uniform_api_plugin_version: { value: 'v1.0' },
    },
    api_meta: {
      plugin_version: 'legacy',
    },
  };

  assert.equal(resolveUniformApiPluginVersion(component), 'v1.0');
});

test('resolveUniformApiPluginVersion supports metadata and legacy fallbacks', () => {
  assert.equal(resolveUniformApiPluginVersion({
    version: 'v4.0.0',
    api_meta: { plugin_version: 'v2.0' },
  }), 'v2.0');
  assert.equal(resolveUniformApiPluginVersion({ version: 'v3.0.0' }), 'v3.0.0');
});

test('buildUniformApiMetaParams preserves opaque plugin versions', () => {
  assert.deepEqual(buildUniformApiMetaParams({
    meta_url: '',
    meta_url_template: 'https://example.com/plugins/demo/?version={version}',
    version: 'v1.0',
    scope_type: 'biz',
    scope_value: '2',
  }), {
    meta_url: '',
    meta_url_template: 'https://example.com/plugins/demo/?version={version}',
    version: 'v1.0',
    scope_type: 'biz',
    scope_value: '2',
  });
});
