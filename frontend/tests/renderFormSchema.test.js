const assert = require('assert');
const fs = require('fs');
const path = require('path');

const babel = require('@babel/core');

function loadRenderFormSchema() {
  const filePath = path.resolve(__dirname, '../src/utils/renderFormSchema.js');
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

const renderFormSchema = loadRenderFormSchema();

function testStructuredCodeEditorUsesExistingRenderFormTag() {
  const schema = renderFormSchema({
    inputs: [{ key: 'job_content', name: '脚本内容', type: 'string', required: true }],
    form_schema: {
      type: 'object',
      required: ['job_content'],
      properties: {
        job_content: {
          type: 'string',
          title: '脚本内容',
          description: '待执行脚本',
          default: '',
          'ui:component': {
            name: 'codeEditor',
            props: { language: 'shell', height: '400px', showMiniMap: false },
          },
        },
      },
    },
  });

  assert.strictEqual(schema[0].type, 'code_editor');
  assert.strictEqual(schema[0].tag_code, 'job_content');
  assert.strictEqual(schema[0].attrs.name, '脚本内容');
  assert.strictEqual(schema[0].attrs.desc, '待执行脚本');
  assert.strictEqual(schema[0].attrs.language, 'shell');
  assert.strictEqual(schema[0].attrs.height, '400px');
  assert.strictEqual(schema[0].attrs.showMiniMap, false);
  assert.deepStrictEqual(schema[0].attrs.validation, [{ type: 'required' }]);
  assert.strictEqual(schema[0].attrs.default, '');
}

function testStructuredStandardControlsAndFallback() {
  const schema = renderFormSchema({
    form_schema: {
      type: 'object',
      properties: {
        body: {
          type: 'string',
          'ui:component': { name: 'textarea', props: { rows: 6 } },
        },
        secret: {
          type: 'string',
          'ui:component': { name: 'password', props: {} },
        },
        enabled: {
          type: 'boolean',
          default: false,
          'ui:component': { name: 'unknown-switch', props: { theme: 'dark' } },
        },
      },
    },
  }, { readOnly: true });

  assert.strictEqual(schema[0].type, 'textarea');
  assert.strictEqual(schema[0].attrs.rows, 6);
  assert.strictEqual(schema[0].attrs.readOnly, true);
  assert.strictEqual(schema[1].type, 'password');
  assert.strictEqual(schema[2].type, 'switch');
  assert.strictEqual(schema[2].attrs.default, false);
  assert.strictEqual(Object.prototype.hasOwnProperty.call(schema[2].attrs, 'theme'), false);
}

function testStructuredOptionsPreserveFalsyValues() {
  const schema = renderFormSchema({
    form_schema: {
      type: 'object',
      properties: {
        mode: {
          type: 'integer',
          'ui:component': {
            name: 'select',
            props: {
              datasource: [
                { label: 'Zero', value: 0 },
                { label: 'Disabled', value: false },
                { label: 'Empty', value: '' },
              ],
            },
          },
        },
        choices: {
          type: 'array',
          items: { type: 'string', enum: ['', 'A'] },
          'ui:component': { name: 'checkbox', props: {} },
        },
      },
    },
  });

  assert.deepStrictEqual(schema[0].attrs.items, [
    { text: 'Zero', value: 0 },
    { text: 'Disabled', value: false },
    { text: 'Empty', value: '' },
  ]);
  assert.deepStrictEqual(schema[1].attrs.items, [
    { name: '', value: '' },
    { name: 'A', value: 'A' },
  ]);
}

function testStructuredObjectArrayUsesDatatableColumns() {
  const schema = renderFormSchema({
    form_schema: {
      type: 'object',
      properties: {
        headers: {
          type: 'array',
          items: {
            type: 'object',
            required: ['name'],
            properties: {
              name: { type: 'string', title: '名称' },
              value: {
                type: 'string',
                title: '值',
                'ui:component': { name: 'password', props: {} },
              },
            },
          },
          'ui:component': { name: 'table', props: { editable: true } },
        },
      },
    },
  });

  assert.strictEqual(schema[0].type, 'datatable');
  assert.strictEqual(schema[0].attrs.editable, true);
  assert.strictEqual(schema[0].attrs.columns[0].type, 'input');
  assert.deepStrictEqual(schema[0].attrs.columns[0].attrs.validation, [{ type: 'required' }]);
  assert.strictEqual(schema[0].attrs.columns[1].type, 'password');
}

function testFlatInputsAndInvalidStructuredSchemaRemainCompatible() {
  const inputs = [
    { key: 'retry', name: '重试次数', type: 'int', default: 0, required: true },
    { key: 'enabled', name: '是否启用', type: 'bool', default: false },
  ];

  const flatSchema = renderFormSchema(inputs);
  const fallbackSchema = renderFormSchema({ inputs, form_schema: { type: 'object', properties: null } });

  assert.deepStrictEqual(fallbackSchema, flatSchema);
  assert.strictEqual(flatSchema[0].attrs.default, 0);
  assert.strictEqual(flatSchema[1].attrs.default, false);
}

testStructuredCodeEditorUsesExistingRenderFormTag();
testStructuredStandardControlsAndFallback();
testStructuredOptionsPreserveFalsyValues();
testStructuredObjectArrayUsesDatatableColumns();
testFlatInputsAndInvalidStructuredSchemaRemainCompatible();
console.log('renderFormSchema tests passed');
