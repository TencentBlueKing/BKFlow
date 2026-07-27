const assert = require('assert');
const fs = require('fs');
const path = require('path');

const babel = require('@babel/core');

function loadAtomForm({ response, postError } = {}) {
  const source = fs.readFileSync(path.resolve(__dirname, '../src/store/modules/atomForm.js'), 'utf8');
  const transformed = babel.transformSync(source, {
    plugins: ['@babel/plugin-transform-modules-commonjs'],
  });
  const axios = {
    post() {
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
        return Promise.resolve({ input: [{ tag_code: 'native' }] });
      },
    },
    '@/utils/transAtom.js': { __esModule: true, default() {} },
  };
  const localRequire = id => mocks[id] || require(id);
  const module = { exports: {} };
  // eslint-disable-next-line no-new-func
  new Function('require', 'module', 'exports', transformed.code)(localRequire, module, module.exports);
  return { actions: module.exports.default.actions, axios, contextCalls, formCalls };
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
    }),
    error => error.code === 'FORM_LOAD_STALE',
  );
  assert.deepStrictEqual(loaded.contextCalls, []);
  assert.deepStrictEqual(loaded.formCalls, []);
}

Promise.resolve()
  .then(testLoadsNativeFormFromSuccessEnvelope)
  .then(testRejectsResultFalseEnvelope)
  .then(testPropagatesAxiosRejection)
  .then(testStaleDetailDoesNotApplyContextOrLoadForms)
  .then(() => {
    console.log('atomForm tests passed');
  })
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
