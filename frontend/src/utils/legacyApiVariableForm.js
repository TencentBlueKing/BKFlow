import renderFormSchema from './renderFormSchema';
import { checkDataType, getDefaultValueFormat } from './checkDataType';

const cloneSchema = value => JSON.parse(JSON.stringify(value));
const SCHEMA_ERROR = 'LEGACY_API_VARIABLE_SCHEMA_INCOMPLETE';

function incompleteSchema(variable) {
  const error = new Error(SCHEMA_ERROR);
  error.code = SCHEMA_ERROR;
  error.variableName = variable.name || variable.key || variable.source_tag || '';
  return error;
}

export const getApiVariableFormErrorMessage = (error, translate) => {
  if (error?.code !== SCHEMA_ERROR) return '';
  return translate('API 插件变量「{name}」的表单定义不完整，请重新选择插件并勾选参数后保存流程', { name: error.variableName });
};

/** 保存原始字段定义，保留选项、表格列、默认值等无法从字段类型还原的信息。 */
export const buildApiVariableExtraInfo = (schema = {}) => {
  const extraInfo = { type: schema.sourceType || schema.type || 'string' };
  const metaDesc = schema.metaDesc || schema.meta_desc;
  const formType = schema.formType || schema.form_type;
  if (metaDesc) extraInfo.meta_desc = metaDesc;
  if (formType) extraInfo.form_type = formType;
  if (schema.required || schema['ui:rules']) extraInfo.required = true;
  if (schema.key) extraInfo.schema = cloneSchema(schema);
  return extraInfo;
};

function validateFieldSchema(field, variable) {
  const [form] = renderFormSchema([field]);
  if (['select', 'checkbox', 'radio'].includes(form.type)
    && !Array.isArray(field.options) && !Array.isArray(field.options?.items)) {
    throw incompleteSchema(variable);
  }
  if (form.type === 'datatable') {
    if (!Array.isArray(field.table?.fields) || !field.table.fields.length) {
      throw incompleteSchema(variable);
    }
    field.table.fields.forEach((column) => {
      if (!column || !column.key) throw incompleteSchema(variable);
      validateFieldSchema(column, variable);
    });
  }
}

/** 无 meta_url 的历史变量复用统一转换器；无法恢复复杂控件时禁止静默降级。 */
export const buildApiVariableFormFromExtraInfo = (variable = {}) => {
  const extraInfo = variable.extra_info;
  if (!extraInfo || typeof extraInfo !== 'object') throw incompleteSchema(variable);
  const schema = extraInfo.schema || extraInfo;
  const type = schema.sourceType || schema.type || extraInfo.type;
  const formType = schema.formType || schema.form_type || extraInfo.form_type;
  if (!type && !formType) throw incompleteSchema(variable);
  const field = {
    ...cloneSchema(schema),
    key: (variable.source_tag || '').split('.')[1] || variable.key,
    name: variable.name || schema.name || variable.key,
    desc: variable.desc || schema.desc || extraInfo.meta_desc || '',
    type,
    form_type: formType,
    required: schema.required || !!schema['ui:rules'] || !!extraInfo.required,
  };
  validateFieldSchema(field, variable);
  const form = renderFormSchema([field]);
  // 旧数据可能只留下 string 类型，却丢失了多选等配置，不能把原数组/对象清空。
  const valueType = checkDataType(variable.value);
  if (!extraInfo.schema && ['Array', 'Object'].includes(valueType)) {
    const expectedType = getDefaultValueFormat(form[0]).type;
    const acceptedTypes = Array.isArray(expectedType) ? expectedType : [expectedType];
    if (!acceptedTypes.includes(valueType)) throw incompleteSchema(variable);
  }
  return form;
};
