const assert = require('node:assert/strict');
const test = require('node:test');
const createLoader = require('./helpers/loadSourceModule');

const load = createLoader();
const { buildApiVariableFormFromExtraInfo } = load('utils/legacyApiVariableForm.js');
const renderFormSchema = load('utils/renderFormSchema.js').default;
const { getDefaultValueFormat } = load('utils/checkDataType.js');

function variable(extraInfo, value = '') {
  return {
    key: '${payload}', name: 'Payload', value,
    source_tag: 'uniform_api.payload', source_info: { node1: ['payload'] },
    extra_info: extraInfo,
  };
}

test('text fallback preserves the hooked field name and required rule', () => {
  const [form] = buildApiVariableFormFromExtraInfo(variable({ type: 'string', form_type: 'textarea', required: true }));
  assert.equal(form.type, 'textarea');
  assert.equal(form.tag_code, 'payload');
  assert.deepEqual(form.attrs.validation, [{ type: 'required' }]);
});

test('table snapshot restores registered controls, columns and array values', () => {
  const schema = { key: 'payload', type: 'list', form_type: 'table', table: { fields: [
    { key: 'count', type: 'int', required: true },
    { key: 'mode', type: 'string', form_type: 'select', options: [0, false, ''] },
  ] } };
  const [form] = buildApiVariableFormFromExtraInfo(variable({ type: 'list', form_type: 'table', schema }, [{ count: 2 }]));
  assert.equal(form.type, 'datatable');
  assert.equal(getDefaultValueFormat(form).type, 'Array');
  assert.equal(form.attrs.columns[0].type, 'int');
  assert.deepEqual(form.attrs.columns[1].attrs.items.map(item => item.value), [0, false, '']);
});

test('select snapshots preserve choices, multiple mode and falsy defaults', () => {
  const schema = { key: 'payload', type: 'string', form_type: 'select', options: [false, 0], multiple: true, allow_create: true, default: 0 };
  const [form] = buildApiVariableFormFromExtraInfo(variable({ type: 'string', form_type: 'select', schema }, [0]));
  assert.deepEqual(form.attrs.items.map(item => item.value), [false, 0]);
  assert.equal(form.attrs.multiple, true);
  assert.equal(form.attrs.allowCreate, true);
  assert.equal(form.attrs.default, 0);
});

test('incomplete historical choices and tables fail before rendering any editable control', () => {
  for (const extraInfo of [
    { type: 'string', form_type: 'select' },
    { type: 'list' },
    { type: 'list', form_type: 'table' },
    { type: 'list', form_type: 'table', schema: { type: 'list', form_type: 'table', table: { fields: [{ key: 'nested', type: 'list' }] } } },
  ]) {
    const input = variable(extraInfo, ['preserved']);
    assert.throws(() => buildApiVariableFormFromExtraInfo(input), error => error.code === 'LEGACY_API_VARIABLE_SCHEMA_INCOMPLETE');
    assert.deepEqual(input.value, ['preserved']);
  }
});

test('fallback uses the same JSON validation and aliases as metadata rendering', () => {
  for (const formType of ['switcher', 'codeEditor', 'time_range']) {
    const field = { key: 'payload', type: 'string', form_type: formType };
    assert.equal(buildApiVariableFormFromExtraInfo(variable(field))[0].type, renderFormSchema([field])[0].type);
  }
  const [form] = buildApiVariableFormFromExtraInfo(variable({ type: 'json', required: true }, 'invalid-json'));
  const validator = form.attrs.validation.find(rule => rule.type === 'custom');
  assert.ok(validator);
  assert.equal(validator.args('invalid-json').result, false);
  assert.equal(validator.args('{"ok":false}').result, true);
});

const stub = { __esModule: true, default: {} };
const loadPage = createLoader({
  vuex: { mapState: () => ({}), mapActions: () => ({}), mapMutations: () => ({}) },
  'vee-validate': { Validator() {} },
  '@/constants/index.js': {},
  '@/components/common/RenderForm/RenderForm.vue': stub,
  '@/views/template/TemplateEdit/NodeConfig/JsonschemaInputParams.vue': stub,
  '@/components/common/base/NoData.vue': stub,
  './ReuseVarDialog.vue': stub,
  './JsonschemaInputParams.vue': stub,
  './CronRuleSelect': stub,
  './FormGroup.vue': stub,
  '@/components/common/FullCodeEditor.vue': stub,
  '../../TemplateMock/MockExecute/components/TaskParamEdit.vue': stub,
  '@/utils/cron.js': stub,
  '@/utils/uuid.js': { random4: () => 'id' },
  '@/utils/pluginFormLoader.js': {
    hasPluginFormFields: schema => Array.isArray(schema) ? schema.length > 0 : Object.keys(schema.properties || {}).length > 0,
  },
});

function contextFor(component, input) {
  const context = {
    constants: { [input.key]: input }, variables: { [input.key]: input },
    activities: { node1: { component: { code: 'uniform_api', version: 'v2.0.0' } } },
    atomFormConfig: {}, scopeInfo: {}, spaceId: 69, templateId: 2397,
    formGeneration: 0, pluginFormRequestId: 0, isDestroyed: false,
    formSections: [], renderData: {}, $refs: {},
    loadV4VariableForm: async () => null,
    $nextTick: fn => fn(), $emit() {}, $t: (text, args) => text.replace('{name}', args?.name || ''),
  };
  for (const [key, method] of Object.entries(component.methods)) {
    if (!(key in context)) context[key] = method.bind(context);
  }
  return context;
}

test('hook creation persists a complete detached schema for later task rendering', () => {
  const component = loadPage('views/template/TemplateEdit/NodeConfig/InputParams.vue').default;
  const field = { key: 'payload', type: 'string', form_type: 'select', multiple: true, options: [0, false], default: 0 };
  let saved;
  const context = { constants: {}, isApiPlugin: true, apiInputs: [field], formData: {}, hookingVarForm: 'payload',
    $emit: (event, action, value) => { if (event === 'hookChange') saved = value; },
  };
  component.methods.createVariable.call(context, { key: '${payload}', name: 'Payload', source_tag: 'uniform_api.payload', value: [0] });
  assert.deepEqual(saved.extra_info.schema, field);
  assert.notEqual(saved.extra_info.schema, field);
  field.options.push('later');
  assert.deepEqual(saved.extra_info.schema.options, [0, false]);
});

for (const page of ['views/task/TaskParamEdit.vue', 'views/template/TemplateMock/MockExecute/components/TaskParamEdit.vue']) {
  test(`${page}: incomplete schemas block submit without changing saved values`, async () => {
    const component = loadPage(page).default;
    const input = { ...variable({ type: 'list', form_type: 'table' }, [{ count: 2 }]), show_type: 'show', custom_type: '' };
    const context = contextFor(component, input);
    if (context.loadFormData) await context.loadFormData();
    else await context.getFormData();
    assert.equal(context.formLoadError, 'LEGACY_API_VARIABLE_SCHEMA_INCOMPLETE');
    assert.match(context.formLoadErrorMessage, /Payload/);
    assert.equal(context.isConfigLoading, false);
    assert.equal(await context.validate(), false);
    assert.deepEqual(input.value, [{ count: 2 }]);
    assert.deepEqual(context.formSections, []);
  });

  test(`${page}: text and custom variables still render together`, async () => {
    const component = loadPage(page).default;
    const input = { ...variable({ type: 'string', form_type: 'textarea' }, 'hello'), show_type: 'show', custom_type: '' };
    const context = contextFor(component, input);
    context.variables.custom = { key: '${custom}', source_tag: '', custom_type: 'input', value: 'original', show_type: 'show', validation: '' };
    context.atomFormConfig.input = { legacy: [{ type: 'input', tag_code: 'input', attrs: {} }] };
    await context.getFormData();
    assert.deepEqual(context.formSections[0].scheme.map(field => field.tag_code), ['${payload}', '${custom}']);
    assert.deepEqual(context.renderData, { '${payload}': 'hello', '${custom}': 'original' });
  });
}

test('global variable editor blocks saving an incomplete schema', async () => {
  const component = loadPage('views/template/TemplateEdit/TemplateSetting/TabGlobalVariables/VariableEdit.vue').default;
  const input = variable({ type: 'string', form_type: 'select' }, 'keep');
  const context = contextFor(component, input);
  context.theEditingData = input;
  context.$validator = { validateAll: () => { throw new Error('must block before saving'); } };
  await context.getAtomConfig();
  assert.match(context.atomConfigErrorMessage, /Payload/);
  assert.equal(await context.onSaveVariable(), false);
  assert.equal(input.value, 'keep');
});

test('global variable editor uses the saved schema when metadata cannot be fetched', async (t) => {
  t.mock.method(console, 'warn', () => {});
  const component = loadPage('views/template/TemplateEdit/TemplateSetting/TabGlobalVariables/VariableEdit.vue').default;
  const schema = { key: 'payload', type: 'string', form_type: 'select', options: [0, false] };
  const input = variable({ type: 'string', form_type: 'select', schema }, 0);
  const context = contextFor(component, input);
  context.theEditingData = input;
  context.activities.node1.component.api_meta = { meta_url: 'https://plugins.example.com/meta' };
  context.loadUniformApiMeta = async () => { throw new Error('metadata offline'); };
  await context.getAtomConfig();
  assert.deepEqual(context.renderConfig[0].attrs.items.map(item => item.value), [0, false]);
  assert.equal(context.atomConfigErrorMessage, '');
});

test('an expired create-task request cannot replace a newer form with an error', async () => {
  const component = loadPage('views/template/TemplateMock/MockExecute/components/TaskParamEdit.vue').default;
  const input = { ...variable({ type: 'string', form_type: 'textarea' }, 'keep'), show_type: 'show', custom_type: '' };
  const context = contextFor(component, input);
  let rejectOld;
  let requested;
  const started = new Promise(resolve => { requested = resolve; });
  const originalGetApiAtomConfig = context.getApiAtomConfig;
  context.getApiAtomConfig = () => {
    requested();
    return new Promise((resolve, reject) => { rejectOld = reject; });
  };
  const old = context.loadFormData();
  await started;
  context.getApiAtomConfig = originalGetApiAtomConfig;
  await context.loadFormData();
  const error = new Error('schema missing');
  Object.assign(error, { code: 'LEGACY_API_VARIABLE_SCHEMA_INCOMPLETE', variableName: 'old' });
  rejectOld(error);
  await old;
  assert.equal(context.formLoadError, null);
  assert.equal(context.formSections[0].scheme[0].type, 'textarea');
  assert.equal(context.renderData['${payload}'], 'keep');
});

test('timed trigger confirmation waits for failed parameter validation before saving', async () => {
  const component = loadPage('views/template/TemplateEdit/TemplateSetting/TimedTriggerConfig.vue').default;
  let updates = 0;
  const context = {
    $refs: { cronRuleSelect: { isError: false }, taskParamEdit: { validate: async () => false } },
    currentTriggerConfig: { config: { mode: 'form' } },
    triggerData: [{ config: { constants: { '${payload}': 'keep' } } }],
    currentTriggerIndex: 0, initTrigger: {}, isShowTriggerDialog: true,
    $set: () => { updates += 1; }, $emit: () => { updates += 1; },
  };
  await component.methods.onTriggerConfirm.call(context, 'edit');
  assert.equal(updates, 0);
  assert.equal(context.isShowTriggerDialog, true);
  assert.equal(context.triggerData[0].config.constants['${payload}'], 'keep');
});

test('switch rendering preserves true and false without emitting empty-string updates', () => {
  const formItem = loadPage('components/common/RenderForm/FormItem.vue').default;
  const atomFilter = load('utils/atomFilter.js').default;
  const [scheme] = buildApiVariableFormFromExtraInfo(variable({ type: 'bool', form_type: 'switcher' }, false));
  for (const value of [true, false]) {
    const context = { scheme, hook: false, updateForm: () => assert.fail('boolean value must not be reset') };
    assert.equal(formItem.methods.getFormValue.call(context, value), value);
  }
  assert.equal(atomFilter.getFormItemDefaultValue([scheme]).payload, false);
});

test('historical string fields with lost multiple/options metadata never coerce array values', () => {
  const input = variable({ type: 'string' }, ['original-choice']);
  assert.throws(() => buildApiVariableFormFromExtraInfo(input), error => error.code === 'LEGACY_API_VARIABLE_SCHEMA_INCOMPLETE');
  assert.deepEqual(input.value, ['original-choice']);
});
