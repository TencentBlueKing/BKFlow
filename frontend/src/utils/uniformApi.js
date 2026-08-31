/**
 * Uniform API 的前端兼容边界。
 *
 * component.version 表示 uniform_api 包装器版本，业务插件版本保存在
 * uniform_api_plugin_version 中。只有包装器为 v4.0.0 且来源、插件标识完整的
 * 节点才进入 V4 原生表单链路；V2/V3 节点必须保持原有 component 数据结构。
 * 本文件的纯函数会被模板编辑、任务详情、重试、Mock、批量更新等页面共同复用。
 */
const getComponentDataValue = (data, key) => {
  const item = data[key];
  if (item && typeof item === 'object' && Object.prototype.hasOwnProperty.call(item, 'value')) {
    return item.value;
  }
  return item;
};

const hasValue = value => value !== undefined && value !== null && value !== '';

export const OPEN_PLUGIN_SCHEMA_PROTOCOL_VERSION = 'open_plugin_snapshot.v1';

export const getOpenPluginSchemaSnapshot = (extraInfo, nodeId, templateNodeId) => {
  const snapshots = (extraInfo && extraInfo.plugin_schema_snapshot) || {};
  if (nodeId && snapshots[nodeId]) return snapshots[nodeId];
  if (templateNodeId && snapshots[templateNodeId]) return snapshots[templateNodeId];
  return null;
};

export const buildV4DetailFromSchemaSnapshot = (snapshot) => {
  if (!snapshot || typeof snapshot !== 'object') {
    throw new Error('invalid open plugin schema snapshot');
  }
  const protocol = snapshot.schema_protocol_version;
  if (protocol !== OPEN_PLUGIN_SCHEMA_PROTOCOL_VERSION) {
    throw new Error(`unsupported schema_protocol_version: ${protocol || ''}`);
  }
  return {
    plugin_code: snapshot.plugin_code,
    plugin_version: snapshot.plugin_version,
    plugin_source: snapshot.plugin_source,
    inputs: snapshot.inputs || [],
    outputs: snapshot.outputs || [],
    description: snapshot.description || '',
    forms: { input: null, output: null },
  };
};

export const normalizeUniformApiMethods = (methods) => {
  if (!Array.isArray(methods)) return [];
  return methods
    .filter(method => typeof method === 'string')
    .map(method => method.trim())
    .filter(Boolean);
};

export const normalizeUniformApiExecutionConfig = ({ polling, callback } = {}) => {
  const normalize = (value) => {
    if (value === null || value === undefined) return null;
    if (typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 0) {
      return null;
    }
    return value;
  };
  return {
    polling: normalize(polling),
    callback: normalize(callback),
  };
};

export const buildUniformApiDetailState = (detail = {}, currentBasicInfo = {}) => {
  const methodList = normalizeUniformApiMethods(detail.methods);
  const method = methodList.includes(currentBasicInfo.method) ? currentBasicInfo.method : methodList[0] || '';
  return {
    realMetaUrl: detail.url || '',
    method,
    respDataPath: detail.response_data_path || '',
    version: detail.plugin_version || '',
    uniform_api_plugin_version: detail.plugin_version || '',
    wrapperVersion: detail.wrapper_version || '',
    methodList,
    ...normalizeUniformApiExecutionConfig(detail),
    credentialKey: detail.credential_key || '',
  };
};

export const buildUniformApiIdentityData = (basicInfo = {}) => {
  const data = {};
  if (hasValue(basicInfo.uniform_api_plugin_version)) {
    data.uniform_api_plugin_version = {
      hook: false,
      value: basicInfo.uniform_api_plugin_version,
    };
  }
  if (hasValue(basicInfo.pluginId)) {
    data.uniform_api_plugin_id = {
      hook: false,
      value: basicInfo.pluginId,
    };
  }
  if (hasValue(basicInfo.sourceKey)) {
    data.uniform_api_plugin_source_key = {
      hook: false,
      value: basicInfo.sourceKey,
    };
  }
  return data;
};

export const buildUniformApiComponent = (basicInfo = {}) => {
  const wrapperVersion = basicInfo.wrapperVersion || '';
  const component = {
    code: basicInfo.plugin || basicInfo.code || 'uniform_api',
    version: wrapperVersion || basicInfo.version || '',
    data: buildUniformApiIdentityData(basicInfo),
  };
  if (hasValue(basicInfo.pluginId) || hasValue(basicInfo.sourceKey) || hasValue(wrapperVersion)) {
    component.api_meta = {
      id: basicInfo.pluginId,
      source_key: basicInfo.sourceKey,
      plugin_version: basicInfo.uniform_api_plugin_version,
      wrapper_version: wrapperVersion,
    };
  }
  return component;
};

export const canApplyPluginDetailResult = (requestId, latestRequestId, isDestroyed = false) => (
  !isDestroyed && (requestId === undefined || requestId === latestRequestId)
);

export const isPluginFormStale = (error, isCurrent = () => true) => (
  error?.code === 'FORM_LOAD_STALE'
  || (typeof isCurrent === 'function' && !isCurrent())
);

export const getPluginFormErrorKey = error => (
  `${error?.code || 'FORM_LOAD_FAILED'}:${error?.message || ''}`
);

export const shouldNotifyPluginFormError = (error, isCurrent, lastErrorKey = '') => (
  !isPluginFormStale(error, isCurrent) && getPluginFormErrorKey(error) !== lastErrorKey
);

// 同一表单槽位只允许最后一次请求写回，避免快速切换插件/版本时旧响应覆盖新状态。
export const createPluginFormRequestRegistry = () => {
  const latestByKey = new Map();
  let nextRequestId = 0;

  return {
    start(key, generation) {
      nextRequestId += 1;
      const requestId = nextRequestId;
      latestByKey.set(key, { generation, requestId });
      return {
        isCurrent(currentGeneration) {
          const latest = latestByKey.get(key);
          return latest
            && latest.generation === currentGeneration
            && latest.requestId === requestId;
        },
      };
    },
    invalidate() {
      latestByKey.clear();
    },
  };
};

const cloneJsonValue = (value) => {
  if (value === undefined) return value;
  return JSON.parse(JSON.stringify(value));
};

export const mergeV4ObjectSchema = (
  target = { type: 'object', properties: {}, required: [] },
  formSchema = {},
  { preferredKey = '', sourceKey = '', namespace = 'section' } = {},
) => {
  const result = {
    ...target,
    properties: { ...(target.properties || {}) },
    required: [...(target.required || [])],
  };
  const propertyMap = {};
  const properties = formSchema.properties || {};

  Object.entries(properties).forEach(([key, value]) => {
    const mappedKey = key === sourceKey && preferredKey ? preferredKey : key;
    let resultKey = mappedKey;
    if (Object.prototype.hasOwnProperty.call(result.properties, resultKey)) {
      resultKey = `${mappedKey}__${namespace || 'section'}`;
      let suffix = 2;
      while (Object.prototype.hasOwnProperty.call(result.properties, resultKey)) {
        resultKey = `${mappedKey}__${namespace || 'section'}_${suffix}`;
        suffix += 1;
      }
    }
    result.properties[resultKey] = cloneJsonValue(value);
    propertyMap[key] = resultKey;
  });

  (formSchema.required || []).forEach((key) => {
    const mappedKey = propertyMap[key] || (key === sourceKey && preferredKey ? preferredKey : key);
    if (!result.required.includes(mappedKey)) {
      result.required.push(mappedKey);
    }
  });
  return result;
};

/**
 * 任务参数页只展示当前变量对应的一个 Object 字段，
 * 不能把插件完整 properties 一并合入。
 */
export const mergeV4VariableObjectField = (target, formSchema, variable = {}, tagCode = '') => {
  const properties = (formSchema && formSchema.properties) || {};
  let fieldKey = '';
  if (Object.prototype.hasOwnProperty.call(properties, tagCode)) {
    fieldKey = tagCode;
  } else if (Object.prototype.hasOwnProperty.call(properties, variable.key)) {
    fieldKey = variable.key;
  }
  if (!fieldKey) return target;
  return mergeV4ObjectSchema(target, {
    type: 'object',
    properties: { [fieldKey]: properties[fieldKey] },
    required: (formSchema.required || []).filter(key => key === fieldKey),
  }, {
    preferredKey: variable.key,
    sourceKey: fieldKey,
    namespace: variable.key,
  });
};

export const normalizePluginFormRefs = (refs) => {
  const refList = Array.isArray(refs) ? refs : [refs];
  return refList
    .reduce((result, ref) => result.concat(Array.isArray(ref) ? ref : [ref]), [])
    .filter(Boolean);
};

export const validatePluginFormSections = async (formRefs = []) => {
  const results = await Promise.all(normalizePluginFormRefs(formRefs)
    .filter(form => typeof form.validate === 'function')
    .map(form => form.validate()));
  return results.every(result => result === true);
};

export const mergePluginFormSections = (sections = [], formConfig) => {
  const nextSections = sections.map(section => ({
    ...section,
    scheme: Array.isArray(section.scheme)
      ? [...section.scheme]
      : {
        ...section.scheme,
        properties: { ...(section.scheme?.properties || {}) },
        required: [...(section.scheme?.required || [])],
      },
  }));
  if (!formConfig) return nextSections;

  if (formConfig.properties) {
    const objectSection = nextSections.find(section => section.type === 'object');
    if (objectSection) {
      Object.assign(objectSection.scheme.properties, cloneJsonValue(formConfig.properties));
      objectSection.scheme.required = [
        ...new Set([...(objectSection.scheme.required || []), ...(formConfig.required || [])]),
      ];
    } else {
      nextSections.push({
        type: 'object',
        scheme: {
          ...cloneJsonValue(formConfig),
          properties: cloneJsonValue(formConfig.properties),
          required: [...(formConfig.required || [])],
        },
      });
    }
    return nextSections;
  }

  const arraySection = nextSections.find(section => section.type === 'array');
  if (arraySection) {
    arraySection.scheme.push(cloneJsonValue(formConfig));
  } else {
    nextSections.push({ type: 'array', scheme: [cloneJsonValue(formConfig)] });
  }
  return nextSections;
};

export const withLoadingState = async (setLoading, operation, isCurrent = () => true) => {
  setLoading(true);
  try {
    return await operation();
  } finally {
    if (isCurrent()) {
      setLoading(false);
    }
  }
};

export const resolveUniformApiPluginVersion = (component = {}) => {
  const data = component.data || {};
  const identity = resolveUniformApiIdentity(component);
  return identity.pluginVersion
    || getComponentDataValue(data, 'plugin_version')
    || component.version
    || '';
};

const resolveIdentityValue = (data, hiddenKey, apiMeta, fallbackKeys = []) => {
  if (Object.prototype.hasOwnProperty.call(data, hiddenKey)) {
    return getComponentDataValue(data, hiddenKey);
  }
  return fallbackKeys.map(key => apiMeta[key]).find(hasValue);
};

export const resolveUniformApiIdentity = (component = {}) => {
  const data = component.data || {};
  const apiMeta = component.api_meta || {};
  return {
    pluginId: resolveIdentityValue(data, 'uniform_api_plugin_id', apiMeta, ['id', 'plugin_id']),
    sourceKey: resolveIdentityValue(data, 'uniform_api_plugin_source_key', apiMeta, ['source_key']),
    pluginVersion: resolveIdentityValue(data, 'uniform_api_plugin_version', apiMeta, ['plugin_version']),
  };
};

export const isV4OpenPlugin = (component = {}) => {
  const apiMeta = component.api_meta || {};
  const { sourceKey, pluginId } = resolveUniformApiIdentity(component);
  const wrapperVersion = apiMeta.wrapper_version || component.version;
  return component.code === 'uniform_api'
    && wrapperVersion === 'v4.0.0'
    && Boolean(sourceKey)
    && Boolean(pluginId);
};

export const resolveV4OpenPluginVersion = (component = {}) => (
  resolveUniformApiIdentity(component).pluginVersion || ''
);

/**
 * 从变量恢复源节点 component。
 * 正常勾选变量只保存 source_info，不保存完整 V4 identity，
 * 必须按节点 ID 回查 Pipeline activities。
 */
export const resolveVariableSourceComponent = (variable = {}, {
  activities = {},
  atom,
  version,
} = {}) => {
  if (variable.component) return variable.component;
  if (variable.node_component) return variable.node_component;
  const sourceInfo = variable.source_info || {};
  const sourceNodeId = Object.keys(sourceInfo).find(nodeId => activities[nodeId] && activities[nodeId].component);
  if (sourceNodeId) {
    return activities[sourceNodeId].component;
  }
  return {
    code: variable.plugin_code || atom,
    version: variable.wrapper_version || version,
    data: variable.component_data || variable.data || variable,
    api_meta: variable.api_meta || {},
  };
};

const HIDDEN_UNIFORM_API_DATA_KEYS = new Set([
  'uniform_api_plugin_id',
  'uniform_api_plugin_source_key',
  'uniform_api_plugin_version',
  'uniform_api_plugin_url',
  'uniform_api_plugin_method',
  'uniform_api_plugin_polling',
  'uniform_api_plugin_callback',
  'uniform_api_plugin_credential_key',
]);

/**
 * 按插件原始 tagCode 重建 getInput() 上下文。
 * 已勾选字段取当前变量值，未勾选字段取节点 component.data。
 */
export const buildVariablePluginRuntimeInputs = ({
  variable = {},
  activities = {},
  constants = {},
} = {}) => {
  const sourceInfo = variable.source_info || {};
  const sourceNodeId = Object.keys(sourceInfo).find(nodeId => (
    activities[nodeId]
    && activities[nodeId].component
    && activities[nodeId].component.data
  ));
  if (!sourceNodeId) return {};
  const data = activities[sourceNodeId].component.data || {};
  const inputs = {};
  Object.keys(data).forEach((tagCode) => {
    if (HIDDEN_UNIFORM_API_DATA_KEYS.has(tagCode)) return;
    const hookedKey = Object.keys(constants).find((key) => {
      const info = constants[key] && constants[key].source_info;
      return info && Array.isArray(info[sourceNodeId]) && info[sourceNodeId].includes(tagCode);
    });
    if (hookedKey && Object.prototype.hasOwnProperty.call(constants[hookedKey] || {}, 'value')) {
      inputs[tagCode] = constants[hookedKey].value;
    } else {
      inputs[tagCode] = getComponentDataValue(data, tagCode);
    }
  });
  return inputs;
};

const HIDDEN_OUTPUT_RENDER_KEYS = new Set(['ex_data']);

/**
 * 把节点 outputs（Array 或 Object）转成原生输出表单的 v-model 值。
 * ex_data 是执行异常信息，不进入输出表单。
 */
export const buildOutputRenderData = (outputs) => {
  if (!outputs) return {};
  if (Array.isArray(outputs)) {
    return outputs.reduce((acc, item) => {
      if (item && item.key && !HIDDEN_OUTPUT_RENDER_KEYS.has(item.key)) {
        acc[item.key] = item.value;
      }
      return acc;
    }, {});
  }
  if (typeof outputs === 'object') {
    return Object.keys(outputs).reduce((acc, key) => {
      if (!HIDDEN_OUTPUT_RENDER_KEYS.has(key)) {
        acc[key] = outputs[key];
      }
      return acc;
    }, {});
  }
  return {};
};

/**
 * 从节点详情接口信封或已解包 payload 中读取 inputs / outputs / state。
 * getNodeActInfo 返回 { result, data }，执行数据在 data 上。
 */
export const resolveNodeExecutionPayload = (nodeInfo = {}) => {
  const isEnvelope = Boolean(nodeInfo)
    && typeof nodeInfo === 'object'
    && Object.prototype.hasOwnProperty.call(nodeInfo, 'result')
    && nodeInfo.data
    && typeof nodeInfo.data === 'object'
    && !Array.isArray(nodeInfo.data);
  const payload = isEnvelope ? nodeInfo.data : (nodeInfo || {});
  return {
    inputs: payload.inputs || {},
    outputs: payload.outputs || [],
    state: payload.state,
  };
};

/**
 * 新选择且尚未保存的节点：优先使用目录 latest_version，
 * default_version 只作为异常数据兼容。
 */
export const resolveNewOpenPluginVersion = ({
  defaultVersion,
  latestVersion,
  versions = [],
} = {}) => {
  if (hasValue(latestVersion)) return latestVersion;
  if (hasValue(defaultVersion)) return defaultVersion;
  const last = versions[versions.length - 1];
  if (!last) return '';
  return typeof last === 'string' ? last : (last.version || '');
};

/**
 * 同时处理 Array / Object section，避免页面直接读取内部 formSections。
 */
export const disablePluginFormFields = (sections = [], keys = [], attrs = {}) => {
  const keySet = new Set(keys);
  return sections.map((section) => {
    if (section.type === 'array') {
      return {
        ...section,
        scheme: (section.scheme || []).map((item) => {
          if (!keySet.has(item.tag_code)) return item;
          return {
            ...item,
            attrs: {
              ...(item.attrs || {}),
              ...attrs,
            },
          };
        }),
      };
    }
    if (section.type === 'object') {
      const properties = { ...(section.scheme && section.scheme.properties ? section.scheme.properties : {}) };
      Object.keys(properties).forEach((key) => {
        if (!keySet.has(key)) return;
        const property = { ...properties[key] };
        const uiComponent = { ...(property['ui:component'] || {}) };
        uiComponent.props = {
          ...(uiComponent.props || {}),
          disabled: true,
        };
        property['ui:component'] = uiComponent;
        if (hasValue(attrs.used_tip)) {
          property['x-bkflow-used-tip'] = attrs.used_tip;
        }
        properties[key] = property;
      });
      return {
        ...section,
        scheme: {
          ...section.scheme,
          properties,
        },
      };
    }
    return section;
  });
};

/**
 * Pipeline 保存边界：先合并原节点，只有严格识别为 V4 后才补充 V4 身份字段。
 * 这保证打开并保存 V2/V3 节点时不会被隐式升级，也不会丢失未知的历史字段。
 */
export const buildUniformApiPluginPipelineComponent = ({
  originalComponent = {},
  component = {},
  componentData,
  basicInfo = {},
  credentials,
} = {}) => {
  const original = cloneJsonValue(originalComponent) || {};
  const base = {
    ...original,
    ...cloneJsonValue(component),
    data: {
      ...(original.data || {}),
      ...(cloneJsonValue(componentData) || {}),
    },
  };
  if (credentials !== undefined) {
    base.credentials = cloneJsonValue(credentials);
  }
  if (base.code !== 'uniform_api') return base;

  const basicIdentityData = buildUniformApiIdentityData(basicInfo);
  const v4Candidate = {
    ...base,
    data: { ...base.data, ...basicIdentityData },
  };
  if (!isV4OpenPlugin(v4Candidate)) {
    return base;
  }

  const data = { ...base.data };
  Object.keys(basicIdentityData).forEach((key) => {
    if (!Object.prototype.hasOwnProperty.call(data, key)) {
      data[key] = basicIdentityData[key];
    }
  });
  const identity = resolveUniformApiIdentity({ ...base, data });
  if (!hasValue(identity.pluginVersion)) {
    throw new Error('plugin version is required');
  }
  return { ...base, data };
};

/**
 * 已保存节点必须使用 Pipeline 中记录的精确业务版本；selectedVersion 仅供尚未
 * 产生隐藏身份字段的新节点使用，不能把缺失/下架版本静默替换为默认或最新版本。
 */
export const buildV4PluginDetailRequest = ({
  component = {},
  spaceId,
  templateId,
  scopeType,
  scopeValue,
  selectedVersion,
}) => {
  const data = component.data || {};
  const identity = resolveUniformApiIdentity(component);
  const hasSavedPluginMetadata = [
    'uniform_api_plugin_source_key',
    'uniform_api_plugin_id',
    'uniform_api_plugin_version',
  ].some(key => Object.prototype.hasOwnProperty.call(data, key));
  const pluginVersion = resolveV4OpenPluginVersion(component)
    || (hasSavedPluginMetadata ? '' : selectedVersion);
  if (!pluginVersion) {
    throw new Error('plugin version is required');
  }
  const stringifyContextValue = (value) => {
    if (value === undefined || value === null) return '';
    return String(value);
  };
  return {
    space_id: stringifyContextValue(spaceId),
    template_id: stringifyContextValue(templateId),
    plugin_type: component.code,
    plugin_code: identity.pluginId,
    plugin_version: String(pluginVersion),
    source_key: identity.sourceKey,
    scope_type: scopeType,
    scope_value: stringifyContextValue(scopeValue),
  };
};

export const buildUniformApiMetaParams = ({
  meta_url: metaUrl,
  meta_url_template: metaUrlTemplate,
  version,
  source_key: sourceKey,
  scope_type: scopeType,
  scope_value: scopeValue,
}) => {
  const params = {
    meta_url: metaUrl,
    scope_type: scopeType,
    scope_value: scopeValue,
  };
  if (metaUrlTemplate) {
    params.meta_url_template = metaUrlTemplate;
    params.source_key = sourceKey;
    if (version !== undefined && version !== null && version !== '') {
      params.version = String(version);
    }
  }
  return params;
};

/**
 * V2/V3 目录插件保存时恢复旧版 api_meta，不写入 V4 身份字段。
 * 原节点已有 api_meta 则原样保留，避免覆盖历史扩展字段。
 */
export const buildLegacyUniformApiMeta = ({
  basicInfo = {},
  originalApiMeta,
} = {}) => {
  if (originalApiMeta && typeof originalApiMeta === 'object' && Object.keys(originalApiMeta).length > 0) {
    return cloneJsonValue(originalApiMeta);
  }
  if (!hasValue(basicInfo.pluginId)) return null;
  let name = basicInfo.apiPluginName || basicInfo.name || '';
  if (!hasValue(basicInfo.apiPluginName) && String(name).includes('-')) {
    name = String(name).substring(String(name).indexOf('-') + 1);
  }
  return {
    id: basicInfo.pluginId,
    name,
    meta_url: basicInfo.metaUrl || '',
    api_key: basicInfo.apiKey || '',
    category: {
      id: basicInfo.groupId || '',
      name: basicInfo.groupName || '',
    },
  };
};

const EXTRA_INFO_TYPE_TO_RENDER = {
  bool: 'switch',
  boolean: 'switch',
  int: 'int',
  integer: 'int',
  json: 'textarea',
  list: 'checkbox',
  object: 'textarea',
  string: 'input',
};

/**
 * 已保存 V2 勾选变量没有 api_meta.meta_url 时，用 extra_info 生成 RenderForm 配置。
 * tag_code 使用 source_tag 字段名，便于 formFilter 按 query 命中后再改写为变量 key。
 */
export const buildApiVariableFormFromExtraInfo = (variable = {}) => {
  const extraInfo = variable.extra_info;
  if (!extraInfo || typeof extraInfo !== 'object') return null;
  const { type, form_type: formType, required, meta_desc: metaDesc } = extraInfo;
  if (!type && !formType) return null;

  let renderType = 'input';
  if (formType && formType !== 'input') {
    renderType = formType;
  } else if (type) {
    renderType = EXTRA_INFO_TYPE_TO_RENDER[type] || 'input';
  }

  const sourceTag = variable.source_tag || '';
  const tagCode = sourceTag.includes('.') ? sourceTag.split('.')[1] : (variable.key || '');
  const field = {
    type: renderType,
    tag_code: tagCode,
    attrs: {
      name: variable.name || tagCode,
      desc: variable.desc || metaDesc || '',
    },
  };
  if (required) {
    field.attrs.validation = [{ type: 'required' }];
  }
  return [field];
};
