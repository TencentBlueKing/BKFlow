import renderFormSchema from './renderFormSchema.js';
import transAtom from './transAtom.js';

/**
 * V4 原生表单描述符的唯一分发入口。
 *
 * component_js/renderform 仍遵循历史 $.atoms 注册协议，jsonschema 和
 * api_plugin_json 复用现有渲染器。服务端已经返回原生描述符时，任何加载或注册
 * 错误都必须暴露给页面，不能静默降级成 API JSON 表单而掩盖协议问题。
 */
export class PluginFormLoadError extends Error {
  constructor(code, message, cause = null) {
    super(message);
    this.code = code;
    this.cause = cause;
  }
}

export class PluginFormStaleError extends PluginFormLoadError {
  constructor() {
    super('FORM_LOAD_STALE', 'stale plugin form request');
  }
}

const assertPluginFormCurrent = (isCurrent) => {
  if (typeof isCurrent === 'function' && !isCurrent()) {
    throw new PluginFormStaleError();
  }
};

const getGlobalAtoms = () => (
  (window.$ && window.$.atoms)
  || (window.jQuery && window.jQuery.atoms)
  || $.atoms
);

const clearGlobalAtom = (key) => {
  const atoms = getGlobalAtoms();
  if (atoms && Object.prototype.hasOwnProperty.call(atoms, key)) {
    delete atoms[key];
  }
};

const loadScript = url => new Promise((resolve, reject) => {
  try {
    const request = $.getScript(url, resolve);
    if (request && typeof request.done === 'function') {
      request.done(resolve);
      if (typeof request.fail === 'function') request.fail(reject);
    }
  } catch (error) {
    reject(error);
  }
});

const loadJavaScriptFormNow = async (descriptor, transformComponent, isCurrent) => {
  try {
    if (descriptor.base) {
      clearGlobalAtom(descriptor.key);
      await loadScript(descriptor.base);
      assertPluginFormCurrent(isCurrent);
    }
    clearGlobalAtom(descriptor.key);
    if (descriptor.is_embedded) {
      (0, eval)(descriptor.data); // eslint-disable-line no-eval
    } else {
      await loadScript(descriptor.data);
    }
    assertPluginFormCurrent(isCurrent);
    const atoms = getGlobalAtoms();
    if (!Object.prototype.hasOwnProperty.call(atoms, descriptor.key)) {
      throw new PluginFormLoadError(
        'FORM_REGISTRATION_FAILED',
        `form ${descriptor.key} was not registered`,
      );
    }
    return transformComponent ? transAtom(atoms, descriptor.key) : atoms[descriptor.key];
  } catch (error) {
    if (error instanceof PluginFormLoadError && error.code === 'FORM_REGISTRATION_FAILED') {
      throw error;
    }
    if (error instanceof PluginFormLoadError && error.code === 'FORM_LOAD_FAILED') {
      throw error;
    }
    if (error instanceof PluginFormStaleError) {
      throw error;
    }
    throw new PluginFormLoadError('FORM_LOAD_FAILED', `failed to load form ${descriptor.key}`, error);
  }
};

// JavaScript 表单共享全局 $.atoms；相同 key 必须串行加载，防止相互清理或覆盖注册结果。
const javaScriptFormQueues = new Map();

const loadJavaScriptForm = (descriptor, transformComponent, isCurrent) => {
  const previous = javaScriptFormQueues.get(descriptor.key) || Promise.resolve();
  const current = previous
    .catch(() => {})
    .then(() => {
      assertPluginFormCurrent(isCurrent);
      return loadJavaScriptFormNow(descriptor, transformComponent, isCurrent);
    });
  const queued = current.finally(() => {
    if (javaScriptFormQueues.get(descriptor.key) === queued) {
      javaScriptFormQueues.delete(descriptor.key);
    }
  });
  javaScriptFormQueues.set(descriptor.key, queued);
  return queued;
};

const isNonEmptyString = value => typeof value === 'string' && value.length > 0;

const isFormObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);

const isValidDescriptor = (descriptor) => {
  if (!descriptor || typeof descriptor.type !== 'string') return false;
  switch (descriptor.type) {
    case 'component_js':
      return isNonEmptyString(descriptor.data) && isNonEmptyString(descriptor.key);
    case 'renderform':
      if (typeof descriptor.data === 'string') {
        return isNonEmptyString(descriptor.data) && isNonEmptyString(descriptor.key);
      }
      return Array.isArray(descriptor.data) || isFormObject(descriptor.data);
    case 'jsonschema':
    case 'api_plugin_json':
      return isFormObject(descriptor.data);
    default:
      return false;
  }
};

const loadFormDescriptor = async (descriptor, detail, options) => {
  if (!isValidDescriptor(descriptor)) {
    throw new PluginFormLoadError('FORM_PROTOCOL_INVALID', 'invalid plugin form descriptor');
  }
  switch (descriptor.type) {
    case 'component_js':
      return loadJavaScriptForm(descriptor, true, options.isCurrent);
    case 'renderform':
      if (typeof descriptor.data === 'string') {
        return loadJavaScriptForm(
          { ...descriptor, is_embedded: descriptor.is_embedded !== false },
          false,
          options.isCurrent,
        );
      }
      if (Array.isArray(descriptor.data) || (descriptor.data && typeof descriptor.data === 'object')) {
        return descriptor.data;
      }
      throw new PluginFormLoadError('FORM_PROTOCOL_INVALID', 'invalid renderform data');
    case 'jsonschema':
      return descriptor.data;
    case 'api_plugin_json':
      return renderFormSchema(detail, { readOnly: options.readOnly });
    default:
      throw new PluginFormLoadError('FORM_PROTOCOL_INVALID', `unsupported form type ${descriptor.type}`);
  }
};

/**
 * forms.input 缺失时才使用 api_plugin_json 兼容回退；显式表单描述符不参与回退。
 * isCurrent 会贯穿异步脚本加载，用于阻止过期请求继续修改全局上下文或页面状态。
 */
export const loadPluginForms = async (detail = {}, { readOnly = false, isCurrent } = {}) => {
  assertPluginFormCurrent(isCurrent);
  const forms = detail.forms || {};
  const inputDescriptor = forms.input === null || typeof forms.input === 'undefined'
    ? { type: 'api_plugin_json', data: detail }
    : forms.input;
  const outputDescriptor = forms.output;
  const input = await loadFormDescriptor(inputDescriptor, detail, { readOnly, isCurrent });
  assertPluginFormCurrent(isCurrent);
  const output = outputDescriptor === null || typeof outputDescriptor === 'undefined'
    ? null
    : await loadFormDescriptor(outputDescriptor, detail, { readOnly, isCurrent });
  assertPluginFormCurrent(isCurrent);
  return {
    detail,
    input,
    output,
    inputType: inputDescriptor.type,
    outputType: outputDescriptor && outputDescriptor.type,
    isRenderOutputForm: outputDescriptor !== null && typeof outputDescriptor !== 'undefined',
  };
};

export const hasPluginFormFields = (scheme) => {
  if (Array.isArray(scheme)) return scheme.length > 0;
  return Boolean(scheme && scheme.properties && Object.keys(scheme.properties).length > 0);
};

const fieldNotFound = fieldKey => new PluginFormLoadError(
  'FORM_FIELD_NOT_FOUND',
  `form field ${fieldKey} was not found`,
);

export const selectPluginFormField = (scheme, fieldKey) => {
  if (Array.isArray(scheme)) {
    const field = scheme.find(item => (
      item.tag_code === fieldKey || (item.attrs && item.attrs.name === fieldKey)
    ));
    if (!field) throw fieldNotFound(fieldKey);
    return field;
  }
  if (scheme && scheme.properties && Object.prototype.hasOwnProperty.call(scheme.properties, fieldKey)) {
    return {
      ...scheme,
      properties: { [fieldKey]: scheme.properties[fieldKey] },
      required: (scheme.required || []).filter(key => key === fieldKey),
    };
  }
  throw fieldNotFound(fieldKey);
};
