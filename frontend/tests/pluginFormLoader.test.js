const assert = require('assert');
const fs = require('fs');
const path = require('path');

const babel = require('@babel/core');

function loadModule(relativePath, mocks = {}) {
  const filePath = path.resolve(__dirname, relativePath);
  const source = fs.readFileSync(filePath, 'utf8');
  const transformed = babel.transformSync(source, {
    plugins: ['@babel/plugin-transform-modules-commonjs'],
  });
  const module = { exports: {} };
  const localRequire = id => mocks[id] || require(id);
  // eslint-disable-next-line no-new-func
  const compile = new Function('require', 'module', 'exports', transformed.code);
  compile(localRequire, module, module.exports);
  return module.exports;
}

function createScriptLoader(scriptCalls, scripts = {}) {
  return (url, callback) => {
    scriptCalls.push(url);
    if (scripts[url]) {
      scripts[url]();
    }
    if (callback) {
      callback();
    }
    return {
      done(handler) {
        handler();
        return this;
      },
      fail() {
        return this;
      },
    };
  };
}

function createDeferredScriptLoader(scriptCalls) {
  return (url, callback) => {
    const task = { url, callback, doneHandlers: [], failHandlers: [] };
    scriptCalls.push(task);
    return {
      done(handler) {
        task.doneHandlers.push(handler);
        return this;
      },
      fail(handler) {
        task.failHandlers.push(handler);
        return this;
      },
    };
  };
}

function resolveScript(task, register) {
  if (register) register();
  task.callback();
  task.doneHandlers.forEach(handler => handler());
}

function rejectScript(task, error) {
  task.failHandlers.forEach(handler => handler(error));
}

const flushPromises = () => new Promise(resolve => setImmediate(resolve));

async function testLoadsAllSupportedFormKinds() {
  const scriptCalls = [];
  const renderCalls = [];
  const translatedAtoms = {
    job_fast_execute_script: [{ tag_code: 'script', translated: true }],
  };
  const globalAtoms = {};
  const jquery = {
    atoms: globalAtoms,
    getScript: createScriptLoader(scriptCalls, {
      'https://bksops.example.com/static/job.js': () => {
        globalAtoms.job_fast_execute_script = [{ tag_code: 'script' }];
      },
    }),
  };
  global.window = { $: jquery, jQuery: jquery };
  global.$ = jquery;
  global.jQuery = jquery;

  const renderFormSchema = (detail, config) => {
    renderCalls.push({ detail, config });
    return [{ tag_code: 'fallback' }];
  };
  const {
    hasPluginFormFields,
    loadPluginForms,
  } = loadModule('../src/utils/pluginFormLoader.js', {
    './renderFormSchema.js': { __esModule: true, default: renderFormSchema },
    './transAtom.js': {
      __esModule: true,
      default: (atoms, key) => translatedAtoms[key] || atoms[key],
    },
  });

  const componentDetail = {
    forms: {
      input: {
        type: 'component_js',
        base: 'https://bksops.example.com/static/base.js',
        data: 'https://bksops.example.com/static/job.js',
        key: 'job_fast_execute_script',
        is_embedded: false,
      },
      output: null,
    },
  };
  const component = await loadPluginForms(componentDetail, { readOnly: false });
  assert.deepStrictEqual(component.input, translatedAtoms.job_fast_execute_script);
  assert.deepStrictEqual(scriptCalls, [
    'https://bksops.example.com/static/base.js',
    'https://bksops.example.com/static/job.js',
  ]);
  assert.strictEqual(component.inputType, 'component_js');

  globalAtoms.demo = [{ tag_code: 'demo' }];
  const renderformDetail = {
    forms: {
      input: {
        type: 'renderform',
        data: 'window.$.atoms.demo = window.$.atoms.demo;',
        key: 'demo',
      },
    },
  };
  const renderform = await loadPluginForms(renderformDetail);
  assert.deepStrictEqual(renderform.input, globalAtoms.demo);

  const directRenderform = {
    properties: {
      enabled: { type: 'boolean' },
    },
  };
  const direct = await loadPluginForms({
    forms: {
      input: {
        type: 'renderform',
        data: directRenderform,
      },
    },
  });
  assert.strictEqual(direct.input, directRenderform);

  const jsonschemaDetail = {
    forms: {
      input: {
        type: 'jsonschema',
        data: {
          type: 'object',
          properties: {
            script: { type: 'string' },
          },
        },
      },
      output: {
        type: 'jsonschema',
        data: {
          type: 'object',
          properties: {
            job_id: { type: 'integer' },
          },
        },
      },
    },
  };
  const jsonschema = await loadPluginForms(jsonschemaDetail);
  assert.strictEqual(jsonschema.input, jsonschemaDetail.forms.input.data);
  assert.strictEqual(jsonschema.output, jsonschemaDetail.forms.output.data);
  assert.strictEqual(jsonschema.isRenderOutputForm, true);

  const noNativeFormDetail = {
    inputs: [{ key: 'script', name: '脚本内容', type: 'string' }],
    forms: { input: null, output: null },
  };
  const fallback = await loadPluginForms(noNativeFormDetail, { readOnly: true });
  assert.strictEqual(Array.isArray(fallback.input), true);
  assert.strictEqual(fallback.inputType, 'api_plugin_json');
  assert.deepStrictEqual(renderCalls, [{
    detail: noNativeFormDetail,
    config: { readOnly: true },
  }]);

  assert.strictEqual(hasPluginFormFields([{ tag_code: 'x' }]), true);
  assert.strictEqual(hasPluginFormFields({ properties: { x: { type: 'string' } } }), true);
  assert.strictEqual(hasPluginFormFields({ properties: {} }), false);
}

function testSelectPluginFormField() {
  const { selectPluginFormField } = loadModule('../src/utils/pluginFormLoader.js', {
    './renderFormSchema.js': { __esModule: true, default: () => [] },
    './transAtom.js': { __esModule: true, default: atoms => atoms },
  });
  const renderFormArray = [
    { tag_code: 'job_content', attrs: { name: 'job_content' } },
    { tag_code: 'job_timeout', attrs: { name: 'job_timeout' } },
  ];
  const jsonSchemaObject = {
    type: 'object',
    properties: {
      job_content: { type: 'string' },
      job_timeout: { type: 'integer' },
    },
    required: ['job_content', 'job_timeout'],
  };

  assert.deepStrictEqual(
    selectPluginFormField(renderFormArray, 'job_content'),
    renderFormArray[0],
  );
  assert.deepStrictEqual(
    selectPluginFormField(jsonSchemaObject, 'job_content'),
    {
      type: 'object',
      properties: {
        job_content: jsonSchemaObject.properties.job_content,
      },
      required: ['job_content'],
    },
  );
  assert.deepStrictEqual(
    selectPluginFormField([{ attrs: { name: 'job_content' } }], 'job_content'),
    { attrs: { name: 'job_content' } },
  );
  assert.throws(
    () => selectPluginFormField(jsonSchemaObject, 'missing'),
    error => error.code === 'FORM_FIELD_NOT_FOUND',
  );
}

async function testNativeFailuresAreExplicitAndNeverFallback() {
  const renderCalls = [];
  const jquery = {
    atoms: {},
    getScript: createScriptLoader([]),
  };
  global.window = { $: jquery, jQuery: jquery };
  global.$ = jquery;
  global.jQuery = jquery;

  const {
    loadPluginForms,
  } = loadModule('../src/utils/pluginFormLoader.js', {
    './renderFormSchema.js': {
      __esModule: true,
      default: (...args) => {
        renderCalls.push(args);
        return [];
      },
    },
    './transAtom.js': {
      __esModule: true,
      default: (atoms, key) => atoms[key],
    },
  });

  await assert.rejects(
    () => loadPluginForms({
      forms: {
        input: {
          type: 'component_js',
          data: 'https://bksops.example.com/static/missing.js',
          key: 'missing',
          is_embedded: false,
        },
      },
    }),
    error => error.code === 'FORM_REGISTRATION_FAILED',
  );
  await assert.rejects(
    () => loadPluginForms({
      forms: {
        input: {
          type: 'component_js',
          data: 'throw new Error("native form exploded")',
          key: 'broken',
          is_embedded: true,
        },
      },
    }),
    error => error.code === 'FORM_LOAD_FAILED',
  );
  await assert.rejects(
    () => loadPluginForms({
      inputs: [{ key: 'fallback', type: 'string' }],
      forms: { input: {} },
    }),
    error => error.code === 'FORM_PROTOCOL_INVALID',
  );
  const invalidDescriptors = [
    { type: 'component_js', data: '', key: 'broken' },
    { type: 'component_js', data: 'https://example.com/form.js', key: '' },
    { type: 'renderform', data: '', key: 'broken' },
    { type: 'renderform', data: 'window.$.atoms.broken = [];', key: '' },
    { type: 'jsonschema', data: null },
    { type: 'jsonschema', data: [] },
    { type: 'component_js', data: null, key: 'broken' },
    { type: 'unknown', data: 'value', key: 'broken' },
  ];
  for (const descriptor of invalidDescriptors) {
    await assert.rejects(
      () => loadPluginForms({ forms: { input: descriptor } }),
      error => error.code === 'FORM_PROTOCOL_INVALID',
    );
  }
  assert.deepStrictEqual((await loadPluginForms({
    forms: { input: { type: 'renderform', data: [{ tag_code: 'array' }] } },
  })).input, [{ tag_code: 'array' }]);

  const transformErrorJquery = {
    atoms: { broken: [] },
    getScript: createScriptLoader([], {
      'https://bksops.example.com/static/form.js': () => {
        transformErrorJquery.atoms.broken = [];
      },
    }),
  };
  global.window = { $: transformErrorJquery, jQuery: transformErrorJquery };
  global.$ = transformErrorJquery;
  const transformErrorLoader = loadModule('../src/utils/pluginFormLoader.js', {
    './renderFormSchema.js': { __esModule: true, default: () => [] },
    './transAtom.js': {
      __esModule: true,
      default: () => {
        throw new Error('transform failed');
      },
    },
  });
  await assert.rejects(
    () => transformErrorLoader.loadPluginForms({
      forms: {
        input: {
          type: 'component_js',
          data: 'https://bksops.example.com/static/form.js',
          key: 'broken',
          is_embedded: false,
        },
      },
    }),
    error => error.code === 'FORM_LOAD_FAILED',
  );

  const missingAtomsJquery = {
    atoms: undefined,
    getScript: createScriptLoader([]),
  };
  global.window = { $: missingAtomsJquery, jQuery: undefined };
  global.$ = missingAtomsJquery;
  const missingAtomsLoader = loadModule('../src/utils/pluginFormLoader.js', {
    './renderFormSchema.js': { __esModule: true, default: () => [] },
    './transAtom.js': { __esModule: true, default: atoms => atoms },
  });
  await assert.rejects(
    () => missingAtomsLoader.loadPluginForms({
      forms: {
        input: {
          type: 'component_js',
          data: 'https://bksops.example.com/static/form.js',
          key: 'broken',
          is_embedded: false,
        },
      },
    }),
    error => error.code === 'FORM_LOAD_FAILED',
  );
  assert.deepStrictEqual(renderCalls, []);
}

async function testNativeScriptStaleResultIsRejectedBeforeReadingAtoms() {
  let isCurrent = true;
  const jquery = {
    atoms: {},
    getScript(_url, _callback) {
      return {
        done(handler) {
          isCurrent = false;
          handler();
          return this;
        },
        fail() {
          return this;
        },
      };
    },
  };
  global.window = { $: jquery, jQuery: jquery };
  global.$ = jquery;
  global.jQuery = jquery;

  const { loadPluginForms } = loadModule('../src/utils/pluginFormLoader.js', {
    './renderFormSchema.js': { __esModule: true, default: () => [] },
    './transAtom.js': { __esModule: true, default: atoms => atoms },
  });

  await assert.rejects(
    () => loadPluginForms({
      forms: {
        input: {
          type: 'component_js',
          data: 'https://example.com/stale.js',
          key: 'stale',
        },
      },
    }, { isCurrent: () => isCurrent }),
    error => error.code === 'FORM_LOAD_STALE',
  );
}

async function testSameKeyJavaScriptFormsAreSerializedAndOldCompletionCannotOverwriteNewForm() {
  const scriptCalls = [];
  const globalAtoms = {};
  const jquery = {
    atoms: globalAtoms,
    getScript: createDeferredScriptLoader(scriptCalls),
  };
  global.window = { $: jquery, jQuery: jquery };
  global.$ = jquery;
  global.jQuery = jquery;

  const { loadPluginForms } = loadModule('../src/utils/pluginFormLoader.js', {
    './renderFormSchema.js': { __esModule: true, default: () => [] },
    './transAtom.js': { __esModule: true, default: (atoms, key) => atoms[key] },
  });
  let firstRequestCurrent = true;
  const first = loadPluginForms({
    forms: { input: { type: 'component_js', data: 'first.js', key: 'shared' } },
  }, { isCurrent: () => firstRequestCurrent });
  const second = loadPluginForms({
    forms: { input: { type: 'component_js', data: 'second.js', key: 'shared' } },
  });

  await flushPromises();
  assert.deepStrictEqual(scriptCalls.map(task => task.url), ['first.js']);
  firstRequestCurrent = false;
  resolveScript(scriptCalls[0], () => {
    globalAtoms.shared = { source: 'first' };
  });
  await assert.rejects(first, error => error.code === 'FORM_LOAD_STALE');

  await flushPromises();
  assert.deepStrictEqual(scriptCalls.map(task => task.url), ['first.js', 'second.js']);
  assert.strictEqual(globalAtoms.shared, undefined);
  resolveScript(scriptCalls[1], () => {
    globalAtoms.shared = { source: 'second' };
  });

  const secondResult = await second;
  assert.deepStrictEqual(secondResult.input, { source: 'second' });
  assert.deepStrictEqual(globalAtoms.shared, { source: 'second' });
}

async function testQueuedStaleJavaScriptFormIsSkippedBeforeExecutingItsScript() {
  const scriptCalls = [];
  const globalAtoms = {};
  const jquery = {
    atoms: globalAtoms,
    getScript: createDeferredScriptLoader(scriptCalls),
  };
  global.window = { $: jquery, jQuery: jquery };
  global.$ = jquery;
  global.jQuery = jquery;

  const { loadPluginForms } = loadModule('../src/utils/pluginFormLoader.js', {
    './renderFormSchema.js': { __esModule: true, default: () => [] },
    './transAtom.js': { __esModule: true, default: (atoms, key) => atoms[key] },
  });
  const first = loadPluginForms({
    forms: { input: { type: 'component_js', data: 'first.js', key: 'shared' } },
  });
  const stale = loadPluginForms({
    forms: { input: { type: 'component_js', data: 'stale.js', key: 'shared' } },
  }, { isCurrent: () => false });
  const staleResult = assert.rejects(stale, error => error.code === 'FORM_LOAD_STALE');

  await flushPromises();
  resolveScript(scriptCalls[0], () => {
    globalAtoms.shared = { source: 'first' };
  });
  await first;
  await staleResult;
  assert.deepStrictEqual(scriptCalls.map(task => task.url), ['first.js']);
  assert.deepStrictEqual(globalAtoms.shared, { source: 'first' });
}

async function testSameKeyFormIsReadBeforeTheNextScriptCanReplaceItsAtom() {
  const scriptCalls = [];
  const globalAtoms = {};
  const jquery = {
    atoms: globalAtoms,
    getScript: createDeferredScriptLoader(scriptCalls),
  };
  global.window = { $: jquery, jQuery: jquery };
  global.$ = jquery;
  global.jQuery = jquery;

  const { loadPluginForms } = loadModule('../src/utils/pluginFormLoader.js', {
    './renderFormSchema.js': { __esModule: true, default: () => [] },
    './transAtom.js': { __esModule: true, default: (atoms, key) => atoms[key] },
  });
  const first = loadPluginForms({
    forms: { input: { type: 'component_js', data: 'first.js', key: 'shared' } },
  });
  const second = loadPluginForms({
    forms: { input: { type: 'component_js', data: 'second.js', key: 'shared' } },
  });

  await flushPromises();
  resolveScript(scriptCalls[0], () => {
    globalAtoms.shared = { source: 'first' };
  });
  const firstResult = await first;
  assert.deepStrictEqual(firstResult.input, { source: 'first' });

  await flushPromises();
  resolveScript(scriptCalls[1], () => {
    globalAtoms.shared = { source: 'second' };
  });
  const secondResult = await second;
  assert.deepStrictEqual(firstResult.input, { source: 'first' });
  assert.deepStrictEqual(secondResult.input, { source: 'second' });
}

async function testSameKeyQueueContinuesAfterAsynchronousScriptRejection() {
  const scriptCalls = [];
  const globalAtoms = {};
  const unhandledRejections = [];
  const handleUnhandledRejection = reason => unhandledRejections.push(reason);
  const jquery = {
    atoms: globalAtoms,
    getScript: createDeferredScriptLoader(scriptCalls),
  };
  global.window = { $: jquery, jQuery: jquery };
  global.$ = jquery;
  global.jQuery = jquery;

  const { loadPluginForms } = loadModule('../src/utils/pluginFormLoader.js', {
    './renderFormSchema.js': { __esModule: true, default: () => [] },
    './transAtom.js': { __esModule: true, default: (atoms, key) => atoms[key] },
  });
  process.on('unhandledRejection', handleUnhandledRejection);
  try {
    const scriptError = new Error('first script failed');
    const first = loadPluginForms({
      forms: { input: { type: 'component_js', data: 'first.js', key: 'shared' } },
    });
    const firstResult = assert.rejects(
      first,
      error => error.code === 'FORM_LOAD_FAILED' && error.cause === scriptError,
    );
    const second = loadPluginForms({
      forms: { input: { type: 'component_js', data: 'second.js', key: 'shared' } },
    });

    await flushPromises();
    assert.deepStrictEqual(scriptCalls.map(task => task.url), ['first.js']);
    rejectScript(scriptCalls[0], scriptError);
    await firstResult;

    await flushPromises();
    assert.deepStrictEqual(scriptCalls.map(task => task.url), ['first.js', 'second.js']);
    resolveScript(scriptCalls[1], () => {
      globalAtoms.shared = { source: 'second' };
    });
    const secondResult = await second;
    await flushPromises();

    assert.deepStrictEqual(secondResult.input, { source: 'second' });
    assert.deepStrictEqual(globalAtoms.shared, { source: 'second' });
    assert.deepStrictEqual(unhandledRejections, []);
  } finally {
    process.removeListener('unhandledRejection', handleUnhandledRejection);
  }
}

async function testJavaScriptFormNeverReusesAnExistingAtomWhenScriptDoesNotRegisterIt() {
  const globalAtoms = { shared: { source: 'old' } };
  const jquery = {
    atoms: globalAtoms,
    getScript: createScriptLoader([]),
  };
  global.window = { $: jquery, jQuery: jquery };
  global.$ = jquery;
  global.jQuery = jquery;

  const { loadPluginForms } = loadModule('../src/utils/pluginFormLoader.js', {
    './renderFormSchema.js': { __esModule: true, default: () => [] },
    './transAtom.js': { __esModule: true, default: (atoms, key) => atoms[key] },
  });

  await assert.rejects(
    () => loadPluginForms({
      forms: { input: { type: 'component_js', data: 'missing.js', key: 'shared' } },
    }),
    error => error.code === 'FORM_REGISTRATION_FAILED',
  );
  assert.strictEqual(globalAtoms.shared, undefined);
}

async function testDifferentJavaScriptFormKeysCanLoadInParallel() {
  const scriptCalls = [];
  const globalAtoms = {};
  const jquery = {
    atoms: globalAtoms,
    getScript: createDeferredScriptLoader(scriptCalls),
  };
  global.window = { $: jquery, jQuery: jquery };
  global.$ = jquery;
  global.jQuery = jquery;

  const { loadPluginForms } = loadModule('../src/utils/pluginFormLoader.js', {
    './renderFormSchema.js': { __esModule: true, default: () => [] },
    './transAtom.js': { __esModule: true, default: (atoms, key) => atoms[key] },
  });
  const first = loadPluginForms({
    forms: { input: { type: 'component_js', data: 'first.js', key: 'first' } },
  });
  const second = loadPluginForms({
    forms: { input: { type: 'component_js', data: 'second.js', key: 'second' } },
  });

  await flushPromises();
  assert.deepStrictEqual(scriptCalls.map(task => task.url).sort(), ['first.js', 'second.js']);
  resolveScript(scriptCalls.find(task => task.url === 'second.js'), () => {
    globalAtoms.second = { source: 'second' };
  });
  resolveScript(scriptCalls.find(task => task.url === 'first.js'), () => {
    globalAtoms.first = { source: 'first' };
  });
  const [firstResult, secondResult] = await Promise.all([first, second]);
  assert.deepStrictEqual(firstResult.input, { source: 'first' });
  assert.deepStrictEqual(secondResult.input, { source: 'second' });
}

function testAppliesContextAndRestrictsCredentialOrigins() {
  const prefilters = [];
  let ajaxSuccessRegistrations = 0;
  let ajaxErrorRegistrations = 0;
  const jqueryTarget = {
    ajaxSuccess() {
      ajaxSuccessRegistrations += 1;
    },
    ajaxError() {
      ajaxErrorRegistrations += 1;
    },
  };
  const jquery = () => jqueryTarget;
  jquery.ajaxPrefilter = handler => prefilters.push(handler);
  global.document = {};
  global.window = {
    SITE_URL: 'https://bkflow.example.com/',
    location: {
      href: 'https://bkflow.example.com/template/2329/',
    },
  };
  global.$ = jquery;

  const {
    applyPluginFormContext,
  } = loadModule('../src/config/setting.js', {
    '@/utils/bus.js': { __esModule: true, default: { $emit() {} } },
    '@/store/index.js': {
      __esModule: true,
      default: { state: { template: { constants: [] } } },
    },
    '@/config/i18n/index.js': {
      __esModule: true,
      default: { t: value => value },
    },
  });

  const formContext = {
    site_url: 'https://bksops.example.com/app/',
    project: { id: 245 },
    biz_cc_id: 0,
    component: false,
    variable: '',
    template: 0,
    instance: false,
    bk_plugin_api_host: {
      sops: 'https://plugins.example.com/api/',
    },
  };
  applyPluginFormContext(formContext, {
    inputs: {
      zero: 0,
      disabled: false,
      empty: '',
    },
    outputs: [{ key: 'job_id', value: 123 }],
    state: 'FINISHED',
  });
  assert.strictEqual($.context.site_url, formContext.site_url);
  assert.strictEqual($.context.project, formContext.project);
  assert.strictEqual($.context.biz_cc_id, 0);
  assert.strictEqual($.context.component, false);
  assert.strictEqual($.context.variable, '');
  assert.strictEqual($.context.template, 0);
  assert.strictEqual($.context.instance, false);
  assert.strictEqual($.context.bk_plugin_api_host, formContext.bk_plugin_api_host);
  assert.strictEqual($.context.getBkBizId(), 0);
  assert.strictEqual($.context.getProjectId(), 245);
  assert.strictEqual($.context.getInput('zero'), 0);
  assert.strictEqual($.context.getInput('disabled'), false);
  assert.strictEqual($.context.getInput('empty'), '');
  assert.strictEqual($.context.getInput('missing'), null);

  applyPluginFormContext(formContext, {
    inputs: {},
    outputs: [],
    state: null,
  });

  assert.strictEqual(ajaxSuccessRegistrations, 1);
  assert.strictEqual(ajaxErrorRegistrations, 1);
  assert.strictEqual(prefilters.length, 1);

  const siteRequest = {
    url: 'https://bksops.example.com/api/plugin/',
    xhrFields: { responseType: 'json' },
  };
  prefilters[0](siteRequest);
  assert.deepStrictEqual(siteRequest.xhrFields, {
    responseType: 'json',
    withCredentials: true,
  });

  const pluginRequest = {
    url: 'https://plugins.example.com/api/run/',
  };
  prefilters[0](pluginRequest);
  assert.deepStrictEqual(pluginRequest.xhrFields, {
    withCredentials: true,
  });

  const unrelatedRequest = {
    url: 'https://unrelated.example.com/api/',
  };
  prefilters[0](unrelatedRequest);
  assert.strictEqual(unrelatedRequest.xhrFields, undefined);
}

Promise.resolve()
  .then(testSelectPluginFormField)
  .then(testLoadsAllSupportedFormKinds)
  .then(testNativeFailuresAreExplicitAndNeverFallback)
  .then(testNativeScriptStaleResultIsRejectedBeforeReadingAtoms)
  .then(testSameKeyJavaScriptFormsAreSerializedAndOldCompletionCannotOverwriteNewForm)
  .then(testQueuedStaleJavaScriptFormIsSkippedBeforeExecutingItsScript)
  .then(testSameKeyFormIsReadBeforeTheNextScriptCanReplaceItsAtom)
  .then(testSameKeyQueueContinuesAfterAsynchronousScriptRejection)
  .then(testJavaScriptFormNeverReusesAnExistingAtomWhenScriptDoesNotRegisterIt)
  .then(testDifferentJavaScriptFormKeysCanLoadInParallel)
  .then(testAppliesContextAndRestrictsCredentialOrigins)
  .then(() => {
    console.log('pluginFormLoader tests passed');
  })
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
