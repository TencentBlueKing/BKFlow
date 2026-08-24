const assert = require('assert');
const fs = require('fs');
const path = require('path');

const babel = require('@babel/core');

function loadUniformApi() {
  const source = fs.readFileSync(path.resolve(__dirname, '../src/utils/uniformApi.js'), 'utf8');
  const transformed = babel.transformSync(source, {
    plugins: ['@babel/plugin-transform-modules-commonjs'],
  });
  const module = { exports: {} };
  // eslint-disable-next-line no-new-func
  new Function('require', 'module', 'exports', transformed.code)(require, module, module.exports);
  return module.exports;
}

function loadAtomForm({ response, postError, formError } = {}) {
  const source = fs.readFileSync(path.resolve(__dirname, '../src/store/modules/atomForm.js'), 'utf8');
  const transformed = babel.transformSync(source, {
    plugins: ['@babel/plugin-transform-modules-commonjs'],
  });
  const postCalls = [];
  const axios = {
    post(...args) {
      postCalls.push(args);
      if (postError) return Promise.reject(postError);
      return Promise.resolve(response);
    },
  };
  const contextCalls = [];
  const formCalls = [];
  const mocks = {
    vue: { __esModule: true, default: { set() {} } },
    axios: { __esModule: true, default: axios },
    '@/config/setting.js': {
      __esModule: true,
      applyPluginFormContext(...args) {
        contextCalls.push(args);
      },
    },
    '@/utils/pluginFormLoader.js': {
      __esModule: true,
      loadPluginForms(...args) {
        formCalls.push(args);
        if (formError && formCalls.length === 1) return Promise.reject(formError);
        return Promise.resolve({ input: [{ tag_code: 'native' }] });
      },
    },
    '@/utils/transAtom.js': { __esModule: true, default() {} },
    '@/utils/uniformApi.js': { __esModule: true, ...loadUniformApi() },
  };
  const localRequire = id => mocks[id] || require(id);
  const module = { exports: {} };
  // eslint-disable-next-line no-new-func
  new Function('require', 'module', 'exports', transformed.code)(localRequire, module, module.exports);
  return { actions: module.exports.default.actions, axios, contextCalls, formCalls, postCalls };
}

async function testLoadsNativeFormFromSuccessEnvelope() {
  const detail = {
    form_context: { site_url: 'https://bksops.example.com/' },
    forms: { input: null },
  };
  const loaded = loadAtomForm({ response: { data: { result: true, data: detail } } });
  const payload = {
    request: { plugin_code: 'demo' },
    runtimeContext: { inputs: { demo: 'value' } },
    readOnly: true,
  };
  const result = await loaded.actions.loadV4OpenPluginForm({}, payload);
  assert.deepStrictEqual(result, { input: [{ tag_code: 'native' }] });
  assert.deepStrictEqual(loaded.contextCalls, [[detail.form_context, payload.runtimeContext]]);
  assert.strictEqual(loaded.formCalls[0][0], detail);
  assert.strictEqual(loaded.formCalls[0][1].readOnly, true);
  assert.strictEqual(typeof loaded.formCalls[0][1].isCurrent, 'function');
}

async function testRejectsResultFalseEnvelope() {
  const loaded = loadAtomForm({ response: { data: { result: false, message: 'detail failed' } } });
  await assert.rejects(
    () => loaded.actions.loadV4OpenPluginForm({}, { request: {} }),
    error => error.message === 'detail failed',
  );
  assert.deepStrictEqual(loaded.contextCalls, []);
  assert.deepStrictEqual(loaded.formCalls, []);
}

async function testPropagatesAxiosRejection() {
  const requestError = new Error('network failed');
  const loaded = loadAtomForm({ postError: requestError });
  await assert.rejects(
    () => loaded.actions.loadV4OpenPluginForm({}, { request: {} }),
    error => error === requestError,
  );
}

async function testStaleDetailDoesNotApplyContextOrLoadForms() {
  const detail = {
    form_context: { site_url: 'https://bksops.example.com/' },
    forms: { input: null },
  };
  const loaded = loadAtomForm({ response: { data: { result: true, data: detail } } });
  await assert.rejects(
    () => loaded.actions.loadV4OpenPluginForm({}, {
      request: { plugin_code: 'stale' },
      runtimeContext: {},
      isCurrent: () => false,
      readOnly: true,
      snapshot: {
        schema_protocol_version: 'open_plugin_snapshot.v1',
        plugin_code: 'job_execute_task',
        inputs: [],
      },
    }),
    error => error.code === 'FORM_LOAD_STALE',
  );
  assert.deepStrictEqual(loaded.contextCalls, []);
  assert.deepStrictEqual(loaded.formCalls, []);
}

async function testReadOnlySnapshotPrefersLiveDetail() {
  const detail = {
    form_context: { site_url: 'https://bksops.example.com/' },
    forms: { input: { type: 'component_js', url: 'https://bksops.example.com/job.js' } },
  };
  const loaded = loadAtomForm({ response: { data: { result: true, data: detail } } });
  const snapshot = {
    schema_protocol_version: 'open_plugin_snapshot.v1',
    plugin_code: 'job_execute_task',
    plugin_version: '1.2.0',
    plugin_source: 'builtin',
    inputs: [{ name: 'bk_biz_id' }],
    outputs: [],
    description: 'job',
  };
  const rootState = {
    task: {
      taskExtraInfoById: {
        85414: {
          plugin_schema_snapshot: { node_1: snapshot },
        },
      },
    },
  };
  const result = await loaded.actions.loadV4OpenPluginForm({ rootState }, {
    request: { plugin_code: 'demo' },
    readOnly: true,
    taskId: 85414,
    nodeId: 'node_1',
    runtimeContext: { inputs: {} },
  });
  assert.deepStrictEqual(result, { input: [{ tag_code: 'native' }] });
  assert.strictEqual(loaded.postCalls.length, 1);
  assert.strictEqual(loaded.postCalls[0][0], '/api/plugin/detail/');
  assert.strictEqual(loaded.formCalls[0][0], detail);
}

async function testReadOnlySnapshotFallsBackWhenDetailRequestFails() {
  const requestError = new Error('network failed');
  const loaded = loadAtomForm({ postError: requestError });
  const snapshot = {
    schema_protocol_version: 'open_plugin_snapshot.v1',
    plugin_code: 'job_execute_task',
    plugin_version: '1.2.0',
    plugin_source: 'builtin',
    inputs: [{ name: 'bk_biz_id' }],
    outputs: [],
  };
  const result = await loaded.actions.loadV4OpenPluginForm({}, {
    request: { plugin_code: 'demo' },
    readOnly: true,
    snapshot,
    runtimeContext: { inputs: {} },
  });
  assert.deepStrictEqual(result, { input: [{ tag_code: 'native' }] });
  assert.strictEqual(loaded.postCalls.length, 1);
  assert.strictEqual(loaded.formCalls[0][0].forms.input, null);
  assert.strictEqual(loaded.formCalls[0][0].plugin_code, 'job_execute_task');
}

async function testReadOnlySnapshotFallsBackWhenNativeFormFails() {
  const nativeFormError = new Error('native form asset failed');
  const detail = {
    form_context: { site_url: 'https://bksops.example.com/' },
    forms: { input: { type: 'component_js', url: 'https://bksops.example.com/job.js' } },
  };
  const loaded = loadAtomForm({
    response: { data: { result: true, data: detail } },
    formError: nativeFormError,
  });
  const snapshot = {
    schema_protocol_version: 'open_plugin_snapshot.v1',
    plugin_code: 'job_execute_task',
    plugin_version: '1.2.0',
    plugin_source: 'builtin',
    inputs: [{ name: 'bk_biz_id' }],
    outputs: [],
  };
  const result = await loaded.actions.loadV4OpenPluginForm({}, {
    request: { plugin_code: 'demo' },
    readOnly: true,
    snapshot,
    runtimeContext: { inputs: {} },
  });
  assert.deepStrictEqual(result, { input: [{ tag_code: 'native' }] });
  assert.strictEqual(loaded.postCalls.length, 1);
  assert.strictEqual(loaded.formCalls.length, 2);
  assert.strictEqual(loaded.formCalls[0][0], detail);
  assert.strictEqual(loaded.formCalls[1][0].forms.input, null);
}

async function testUnknownProtocolVersionFails() {
  const loaded = loadAtomForm({ postError: new Error('network failed') });
  await assert.rejects(
    () => loaded.actions.loadV4OpenPluginForm({}, {
      request: { plugin_code: 'demo' },
      readOnly: true,
      snapshot: { schema_protocol_version: 'unknown.v9', inputs: [] },
    }),
    error => /schema_protocol_version/.test(error.message),
  );
  assert.strictEqual(loaded.postCalls.length, 1);
}

async function testReadOnlyWithoutSnapshotFallsBackToLiveDetail() {
  const detail = { forms: { input: null }, inputs: [] };
  const loaded = loadAtomForm({ response: { data: { result: true, data: detail } } });
  await loaded.actions.loadV4OpenPluginForm({}, {
    request: { plugin_code: 'demo' },
    readOnly: true,
    runtimeContext: {},
  });
  assert.strictEqual(loaded.postCalls.length, 1);
  assert.strictEqual(loaded.postCalls[0][0], '/api/plugin/detail/');
}

async function testEditableStillRequestsLiveDetailEvenWithSnapshot() {
  const detail = { forms: { input: null } };
  const loaded = loadAtomForm({ response: { data: { result: true, data: detail } } });
  await loaded.actions.loadV4OpenPluginForm({}, {
    request: { plugin_code: 'demo' },
    readOnly: false,
    snapshot: {
      schema_protocol_version: 'open_plugin_snapshot.v1',
      plugin_code: 'job_execute_task',
      inputs: [],
    },
    runtimeContext: {},
  });
  assert.strictEqual(loaded.postCalls.length, 1);
}

Promise.resolve()
  .then(testLoadsNativeFormFromSuccessEnvelope)
  .then(testRejectsResultFalseEnvelope)
  .then(testPropagatesAxiosRejection)
  .then(testStaleDetailDoesNotApplyContextOrLoadForms)
  .then(testReadOnlySnapshotPrefersLiveDetail)
  .then(testReadOnlySnapshotFallsBackWhenDetailRequestFails)
  .then(testReadOnlySnapshotFallsBackWhenNativeFormFails)
  .then(testUnknownProtocolVersionFails)
  .then(testReadOnlyWithoutSnapshotFallsBackToLiveDetail)
  .then(testEditableStillRequestsLiveDetailEvenWithSnapshot)
  .then(() => {
    console.log('atomForm tests passed');
  })
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
