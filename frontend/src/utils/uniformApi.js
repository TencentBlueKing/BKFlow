const getComponentDataValue = (data, key) => {
  const item = data[key];
  if (item && typeof item === 'object' && Object.prototype.hasOwnProperty.call(item, 'value')) {
    return item.value;
  }
  return item;
};

const hasValue = value => value !== undefined && value !== null && value !== '';

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
    if (version !== undefined && version !== null && version !== '') {
      params.version = String(version);
    }
  }
  return params;
};
