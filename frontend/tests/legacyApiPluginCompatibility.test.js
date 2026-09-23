const assert = require('assert');
const fs = require('fs');
const path = require('path');

const babel = require('@babel/core');

function compileModule(source, mocks) {
  const transformed = babel.transformSync(source, {
    plugins: ['@babel/plugin-transform-modules-commonjs'],
  });
  const module = { exports: {} };
  const fallbackModule = new Proxy({
    __esModule: true,
    default: {},
  }, {
    get(target, key) {
      if (key in target) return target[key];
      return () => ({});
    },
  });
  const localRequire = id => mocks[id] || fallbackModule;
  // eslint-disable-next-line no-new-func
  new Function('require', 'module', 'exports', transformed.code)(localRequire, module, module.exports);
  return module.exports.default || module.exports;
}

function loadJsonFormSchema() {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/utils/jsonFormSchema.js'),
    'utf8',
  );
  return compileModule(source, {
    './tools': {
      __esModule: true,
      default: {
        checkIsJSON(value) {
          if (typeof value !== 'string') return true;
          try {
            JSON.parse(value);
            return true;
          } catch (error) {
            return false;
          }
        },
      },
    },
  });
}

function loadVueComponent(relativePath) {
  const source = fs.readFileSync(path.resolve(__dirname, relativePath), 'utf8');
  const script = source.match(/<script>([\s\S]*?)<\/script>/);
  assert.ok(script, `${relativePath} must contain a script block`);

  const uniformApi = new Proxy({
    __esModule: true,
    isV4OpenPlugin: () => false,
    canApplyPluginDetailResult: () => true,
    resolveUniformApiPluginVersion: () => 'v3.0.0',
    resolveV4OpenPluginVersion: () => '',
    buildUniformApiDetailState: detail => ({
      methodList: detail.methods || [],
      wrapperVersion: detail.version,
    }),
  }, {
    get(target, key) {
      if (key in target) return target[key];
      return () => ({});
    },
  });
  const vuex = {
    __esModule: true,
    mapActions: () => ({}),
    mapGetters: () => ({}),
    mapMutations: () => ({}),
    mapState: () => ({}),
  };
  const atomFilter = {
    __esModule: true,
    default: { isConfigExists: () => false },
  };
  const modernRenderFormSchema = () => [{
    type: 'select',
    tag_code: 'targets',
    attrs: { name: 'Targets' },
  }];

  return compileModule(script[1], {
    vuex,
    axios: {
      __esModule: true,
      default: { CancelToken: { source: () => ({}) } },
    },
    '@/utils/atomFilter.js': atomFilter,
    '@/utils/tools.js': {
      __esModule: true,
      default: {
        deepClone(value) {
          return JSON.parse(JSON.stringify(value));
        },
      },
    },
    '@/utils/jsonFormSchema.js': { __esModule: true, default: loadJsonFormSchema() },
    '@/utils/renderFormSchema.js': { __esModule: true, default: modernRenderFormSchema },
    '@/utils/uniformApi.js': uniformApi,
    '@/utils/legacyApiVariableForm.js': require('./helpers/loadSourceModule')()('utils/legacyApiVariableForm.js'),
    '@/utils/pluginFormLoader.js': {
      __esModule: true,
      hasPluginFormFields: () => true,
    },
  });
}

const legacyDetail = {
  id: 'legacy-v3-plugin',
  desc: 'legacy api plugin form',
  version: 'v3.0.0',
  methods: ['POST'],
  inputs: [
    {
      key: 'targets',
      name: 'Targets',
      type: 'string',
      required: true,
      multiple: true,
      allow_create: true,
      options: [
        { text: 'Host A', value: 'host-a' },
        { text: 'Host B', value: 'host-b' },
      ],
    },
    {
      key: 'comment',
      name: 'Comment',
      type: 'string',
      hint: 'legacy hint',
    },
  ],
  outputs: [],
};

const legacyComponent = {
  code: 'uniform_api',
  version: 'v3.0.0',
  api_meta: {
    meta_url: 'https://plugins.example.com/meta',
    version: 'v3.0.0',
  },
};

function assertLegacySchema(schema, disabled) {
  assert.strictEqual(Array.isArray(schema), false);
  assert.strictEqual(schema.type, 'object');
  assert.deepStrictEqual(schema.required, ['targets']);
  assert.strictEqual(schema.properties.targets.type, 'array');
  assert.strictEqual(schema.properties.targets['ui:component'].props.multiple, true);
  assert.strictEqual(schema.properties.targets['ui:component'].props.allowCreate, true);
  assert.strictEqual(schema.properties.targets['ui:component'].props.disabled, disabled);
  assert.strictEqual(schema.properties.comment['ui:component'].props.placeholder, 'legacy hint');
}

function createCommonContext() {
  return {
    isDestroyed: false,
    isApiPlugin: true,
    isSubFlow: false,
    isViewMode: true,
    pluginCode: 'uniform_api',
    pluginFormRequestId: 0,
    pluginConfigs: {},
    atomFormConfig: {},
    atomOutputConfig: {},
    pluginOutput: { uniform_api: { 'v3.0.0': [] } },
    nodeActivity: { id: 'node-1', component: legacyComponent },
    nodeConfig: { id: 'node-1', component: legacyComponent },
    constants: {},
    inputsFormData: {},
    outputs: [],
    scopeInfo: {},
    spaceId: 'space-1',
    taskId: 'task-1',
    templateId: 'template-1',
    $route: { params: { templateId: 'template-1' } },
    loadAtomConfig: async () => ({}),
    loadUniformApiMeta: async () => ({ result: true, data: legacyDetail }),
    updateBasicInfo: () => {},
    isCurrentPluginDetailRequest: () => true,
  };
}

async function testNodeConfigKeepsLegacySchema() {
  const component = loadVueComponent('../src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue');
  const context = createCommonContext();
  const schema = await component.methods.getAtomConfig.call(context, {
    plugin: 'uniform_api',
    version: 'v3.0.0',
    isThird: false,
    isApiPlugin: true,
    requestId: 1,
    component: legacyComponent,
    requestBasicInfo: {
      metaUrl: legacyComponent.api_meta.meta_url,
      version: 'v3.0.0',
    },
  });
  assertLegacySchema(schema, true);
}

function testLegacyApiPluginKeepsVersionSelectorHidden() {
  const component = loadVueComponent('../src/views/template/TemplateEdit/NodeConfig/BasicInfo.vue');
  const { showPluginVersion } = component.computed;

  assert.strictEqual(showPluginVersion.call({
    isApiPlugin: false,
    basicInfo: {},
  }), true);
  assert.strictEqual(showPluginVersion.call({
    isApiPlugin: true,
    basicInfo: { isOpenPlugin: false },
  }), false);
  assert.strictEqual(showPluginVersion.call({
    isApiPlugin: true,
    basicInfo: { isOpenPlugin: true },
  }), true);
}

async function testTaskExecutePagesKeepLegacySchema() {
  const pages = [
    '../src/views/task/TaskExecute/ExecuteInfo.vue',
    '../src/views/task/TaskExecute/SideDrawerExecuteInfo.vue',
  ];
  for (const page of pages) {
    const component = loadVueComponent(page);
    const context = createCommonContext();
    context.renderConfig = null;
    await component.methods.getNodeConfig.call(context, 'uniform_api', 'v3.0.0', 'v3.0.0');
    assertLegacySchema(context.renderConfig, true);
  }
}

async function testTaskDetailFormsKeepLegacySchemaAndHookState() {
  const pages = [
    '../src/views/task/TaskExecute/ExecuteInfo/ExecuteInfoForm.vue',
    '../src/views/task/TaskExecute/ExecuteInfoCompoment/ExecuteInfoForm.vue',
  ];
  for (const page of pages) {
    const component = loadVueComponent(page);
    const context = createCommonContext();
    context.constants = {
      variable: {
        source_type: 'custom',
        source_info: { 'node-1': ['targets'] },
      },
    };
    context.setFormsSchema = component.methods.setFormsSchema.bind(context);
    const schema = await component.methods.getAtomConfig.call(context, {
      plugin: 'uniform_api',
      version: 'v3.0.0',
      isThird: false,
    });
    assert.strictEqual(Array.isArray(schema), false);
    assert.strictEqual(schema.type, 'object');
    assert.deepStrictEqual(schema.required, ['targets']);
    assert.strictEqual(schema.properties.comment['ui:component'].props.placeholder, 'legacy hint');
    assert.strictEqual(context.inputsFormData.targets, '${targets}');
    assert.strictEqual(schema.properties.targets.extend.hook, true);
    assert.strictEqual(schema.properties.targets['ui:component'].props.disabled, true);
  }
}

async function testMockSettingKeepsLegacySchemaAndHookState() {
  const component = loadVueComponent('../src/views/template/TemplateMock/MockSetting/index.vue');
  const context = createCommonContext();
  context.constants = {
    variable: {
      source_type: 'custom',
      source_info: { 'node-1': ['targets'] },
    },
  };
  context.setFormsSchema = component.methods.setFormsSchema.bind(context);
  const schema = await component.methods.getAtomConfig.call(context, {
    plugin: 'uniform_api',
    version: 'v3.0.0',
    isThird: false,
  });
  assert.strictEqual(Array.isArray(schema), false);
  assert.strictEqual(context.inputsFormData.targets, '${targets}');
  assert.strictEqual(schema.properties.targets.extend.hook, true);
  assert.strictEqual(schema.properties.comment['ui:component'].props.placeholder, 'legacy hint');
}

async function testLegacyInputVariableKeepsApiFieldMetadata() {
  const component = loadVueComponent('../src/views/template/TemplateEdit/NodeConfig/InputParams.vue');
  const emitted = [];
  const context = {
    constants: {},
    isApiPlugin: true,
    apiInputs: [{
      key: 'targets',
      type: 'string',
      meta_desc: 'target metadata',
      form_type: 'select',
      required: true,
    }],
    formsScheme: {},
    formData: { targets: ['host-a'] },
    hookingVarForm: 'targets',
    $emit(...args) {
      emitted.push(args);
    },
  };

  component.methods.createVariable.call(context, {
    key: '${targets}',
    name: 'Targets',
    source_tag: 'uniform_api.targets',
  });

  const created = emitted.find(event => event[0] === 'hookChange')[2];
  assert.deepStrictEqual(created.extra_info, {
    type: 'string',
    meta_desc: 'target metadata',
    form_type: 'select',
    required: true,
    schema: context.apiInputs[0],
  });
}

async function testCreateTaskFallsBackToExtraInfoWithoutApiMeta() {
  const component = loadVueComponent('../src/views/template/TemplateMock/MockExecute/components/TaskParamEdit.vue');
  const variable = {
    name: '用户对话',
    key: '${query}',
    source_tag: 'uniform_api.query',
    extra_info: {
      type: 'string',
      form_type: 'textarea',
      required: true,
    },
  };
  const context = {
    activities: {
      nodebcedb895ae3039b4c8b006e6e79f: {
        component: {
          code: 'uniform_api',
          version: 'v2.0.0',
        },
      },
    },
    spaceId: 69,
    templateId: 2397,
    scopeInfo: {},
    loadUniformApiMeta: async () => {
      throw new Error('meta should not be requested without meta_url');
    },
  };

  const form = await component.methods.getApiAtomConfig.call(
    context,
    { nodebcedb895ae3039b4c8b006e6e79f: ['query'] },
    'uniform_api.query',
    variable,
  );

  assert.strictEqual(form[0].type, 'textarea');
  assert.strictEqual(form[0].tag_code, 'query');
  assert.strictEqual(form[0].attrs.name, '用户对话');

  const modifyParamsComponent = loadVueComponent('../src/views/task/TaskParamEdit.vue');
  const modifyForm = await modifyParamsComponent.methods.getApiAtomConfig.call({
    ...context,
    resolveTemplateId: () => 2397,
  }, variable);
  assert.strictEqual(modifyForm[0].type, 'textarea');
  assert.strictEqual(modifyForm[0].tag_code, 'query');
}

Promise.resolve()
  .then(testNodeConfigKeepsLegacySchema)
  .then(testLegacyApiPluginKeepsVersionSelectorHidden)
  .then(testTaskExecutePagesKeepLegacySchema)
  .then(testTaskDetailFormsKeepLegacySchemaAndHookState)
  .then(testMockSettingKeepsLegacySchemaAndHookState)
  .then(testLegacyInputVariableKeepsApiFieldMetadata)
  .then(testCreateTaskFallsBackToExtraInfoWithoutApiMeta)
  .then(() => {
    console.log('legacy API plugin compatibility tests passed');
  })
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
