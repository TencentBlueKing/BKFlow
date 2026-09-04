const assert = require('assert');
const fs = require('fs');
const path = require('path');

const babel = require('@babel/core');

function loadComponent() {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/views/admin/Space/Template/CreateTaskSideslider.vue'),
    'utf8',
  );
  const script = source.match(/<script>([\s\S]*?)<\/script>/);
  assert.ok(script, 'CreateTaskSideslider.vue must contain a script block');

  const transformed = babel.transformSync(script[1], {
    plugins: ['@babel/plugin-transform-modules-commonjs'],
  });
  const module = { exports: {} };
  const fallbackModule = {
    __esModule: true,
    default: {},
  };
  const mocks = {
    vuex: {
      __esModule: true,
      mapActions: () => ({}),
      mapMutations: () => ({}),
      mapState: () => ({}),
    },
    'moment-timezone': {
      __esModule: true,
      default: () => ({ format: () => '20260825180000' }),
    },
    '@/constants/index.js': { STRING_LENGTH: {} },
    '@/utils/tools.js': {
      __esModule: true,
      default: { checkIsJSON: () => true },
    },
  };
  const localRequire = id => mocks[id] || fallbackModule;
  // eslint-disable-next-line no-new-func
  new Function('require', 'module', 'exports', transformed.code)(localRequire, module, module.exports);
  return module.exports.default || module.exports;
}

async function testCreateTaskAwaitsValidationAndVariableData() {
  const component = loadComponent();
  const calls = [];
  const context = {
    taskFormData: {
      mode: 'form',
      name: 'task',
      labels: [],
    },
    spaceId: 245,
    createLoading: false,
    $refs: {
      createTaskForm: {
        validate: async () => true,
      },
      taskParamEdit: {
        validate: async () => true,
        getVariableData: async () => ({
          ip: { key: '${ip}', value: '0:9.136.163.56' },
        }),
      },
    },
    createTask: async (payload) => {
      calls.push(payload);
      return { result: false };
    },
    getParameterConstants: component.methods.getParameterConstants,
  };

  await component.methods.createTaskConfirm.call(context);

  assert.equal(calls.length, 1);
  assert.deepStrictEqual(calls[0].params.constants, {
    '${ip}': '0:9.136.163.56',
  });
}

async function testCreateTaskStopsWhenParameterValidationFails() {
  const component = loadComponent();
  let createCalled = false;
  const context = {
    taskFormData: { mode: 'form', labels: [] },
    createLoading: false,
    $refs: {
      createTaskForm: { validate: async () => true },
      taskParamEdit: { validate: async () => false },
    },
    createTask: async () => {
      createCalled = true;
    },
  };

  await component.methods.createTaskConfirm.call(context);

  assert.equal(createCalled, false);
}

Promise.resolve()
  .then(testCreateTaskAwaitsValidationAndVariableData)
  .then(testCreateTaskStopsWhenParameterValidationFails)
  .then(() => console.log('CreateTaskSideslider tests passed'))
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
