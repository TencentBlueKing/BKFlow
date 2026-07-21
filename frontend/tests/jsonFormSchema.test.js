const assert = require('assert');
const fs = require('fs');
const path = require('path');

const babel = require('@babel/core');

function loadJsonFormSchema() {
  const filePath = path.resolve(__dirname, '../src/utils/jsonFormSchema.js');
  const source = fs.readFileSync(filePath, 'utf8');
  const transformed = babel.transformSync(source, {
    plugins: ['@babel/plugin-transform-modules-commonjs'],
  });
  const module = { exports: {} };
  const localRequire = (id) => {
    if (id === './tools') {
      return {
        __esModule: true,
        default: {
          checkIsJSON(value) {
            if (typeof value !== 'string') return false;
            try {
              JSON.parse(value);
              return true;
            } catch (error) {
              return false;
            }
          },
        },
      };
    }
    return require(id);
  };
  // eslint-disable-next-line no-new-func
  const compile = new Function('require', 'module', 'exports', transformed.code);
  compile(localRequire, module, module.exports);
  return module.exports.default;
}

const jsonFormSchema = loadJsonFormSchema();

function testStructuredFormSchemaTakesPrecedence() {
  const schema = jsonFormSchema({
    id: 'plugin-demo',
    desc: 'demo',
    inputs: [{ key: 'mode', name: 'Mode', type: 'string' }],
    form_schema: {
      type: 'object',
      required: ['mode'],
      properties: {
        mode: {
          type: 'string',
          title: 'Mode',
          'ui:component': {
            name: 'select',
            props: {
              datasource: [{ label: 'Sync', value: 'sync' }],
            },
          },
          'ui:reactions': [{ source: 'other', effect: 'update' }],
        },
      },
    },
  }, { disabled: true });

  assert.strictEqual(schema.properties.mode['ui:component'].name, 'select');
  assert.deepStrictEqual(schema.properties.mode['ui:component'].props.datasource, [
    { label: 'Sync', value: 'sync' },
  ]);
  assert.strictEqual(schema.properties.mode['ui:component'].props.disabled, true);
  assert.deepStrictEqual(schema.properties.mode['ui:reactions'], [{ source: 'other', effect: 'update' }]);
  assert.strictEqual(schema.properties.mode.extend.can_hook, true);
}

function testFlatInputsRemainCompatible() {
  const schema = jsonFormSchema({
    id: 'plugin-demo',
    inputs: [
      { key: 'retry', name: 'Retry', type: 'int', default: 0 },
      { key: 'enabled', name: 'Enabled', type: 'bool', default: false },
      { key: 'targets', name: 'Targets', type: 'list' },
    ],
  });

  assert.strictEqual(schema.properties.retry['ui:component'].props.type, 'number');
  assert.strictEqual(schema.properties.retry.default, 0);
  assert.strictEqual(schema.properties.enabled['ui:component'].name, 'switcher');
  assert.strictEqual(schema.properties.enabled.default, false);
  assert.deepStrictEqual(schema.properties.targets['ui:component'].props.datasource, []);
}

testStructuredFormSchemaTakesPrecedence();
testFlatInputsRemainCompatible();
console.log('jsonFormSchema tests passed');
