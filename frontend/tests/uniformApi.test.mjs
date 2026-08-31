import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

async function main() {
  const source = await readFile(new URL('../src/utils/uniformApi.js', import.meta.url), 'utf8');
  const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
  const {
    buildV4PluginDetailRequest,
    buildUniformApiComponent,
    buildUniformApiDetailState,
    buildUniformApiMetaParams,
    buildUniformApiPluginPipelineComponent,
    canApplyPluginDetailResult,
    createPluginFormRequestRegistry,
    getPluginFormErrorKey,
    isPluginFormStale,
    isV4OpenPlugin,
    mergeV4ObjectSchema,
    mergePluginFormSections,
    normalizePluginFormRefs,
    validatePluginFormSections,
    resolveV4OpenPluginVersion,
    resolveUniformApiIdentity,
    resolveUniformApiPluginVersion,
    resolveVariableSourceComponent,
    resolveNewOpenPluginVersion,
    disablePluginFormFields,
    getOpenPluginSchemaSnapshot,
    buildV4DetailFromSchemaSnapshot,
    mergeV4VariableObjectField,
    buildVariablePluginRuntimeInputs,
    buildOutputRenderData,
    resolveNodeExecutionPayload,
    shouldNotifyPluginFormError,
    withLoadingState,
    buildLegacyUniformApiMeta,
    buildApiVariableFormFromExtraInfo,
  } = await import(moduleUrl);

  const savedComponent = {
    code: 'uniform_api',
    version: 'v4.0.0',
    api_meta: {
      wrapper_version: 'v4.0.0',
      source_key: 'sops',
      id: 'builtin__job_fast_execute_script',
    },
    data: {
      uniform_api_plugin_version: { value: 'v2.0' },
    },
  };

  test('resolveUniformApiPluginVersion uses the saved business version', () => {
    const component = {
      version: 'v4.0.0',
      data: {
        uniform_api_plugin_version: { value: 'v1.0' },
      },
      api_meta: {
        plugin_version: 'legacy',
      },
    };

    assert.equal(resolveUniformApiPluginVersion(component), 'v1.0');
  });

  test('withLoadingState clears loading for success, result=false, stale result, and exception', async () => {
    const run = async operation => {
      const states = [];
      let result;
      let error;
      try {
        result = await withLoadingState(
          loading => states.push(loading),
          operation,
        );
      } catch (caught) {
        error = caught;
      }
      assert.deepEqual(states, [true, false]);
      return { result, error };
    };

    assert.deepEqual(await run(async () => ({ result: true })), {
      result: { result: true },
      error: undefined,
    });
    assert.deepEqual(await run(async () => ({ result: false })), {
      result: { result: false },
      error: undefined,
    });
    assert.deepEqual(await run(async () => ({ stale: true })), {
      result: { stale: true },
      error: undefined,
    });
    const failure = await run(async () => {
      throw new Error('detail failed');
    });
    assert.equal(failure.result, undefined);
    assert.equal(failure.error?.message, 'detail failed');
  });

  test('isPluginFormStale only suppresses expired or explicitly stale requests', () => {
    assert.equal(isPluginFormStale({ code: 'FORM_LOAD_STALE' }, () => true), true);
    assert.equal(isPluginFormStale(new Error('request expired'), () => false), true);
    assert.equal(isPluginFormStale({ code: 'FORM_LOAD_FAILED' }, () => true), false);
    assert.equal(isPluginFormStale({ code: 'FORM_LOAD_FAILED' }, () => false), true);
  });

  test('plugin form errors notify once and only for current non-stale requests', () => {
    const error = { code: 'FORM_LOAD_FAILED', message: 'detail failed' };
    const errorKey = getPluginFormErrorKey(error);

    assert.equal(shouldNotifyPluginFormError(error, () => true, ''), true);
    assert.equal(shouldNotifyPluginFormError(error, () => true, errorKey), false);
    assert.equal(shouldNotifyPluginFormError({ code: 'FORM_LOAD_STALE' }, () => true, ''), false);
    assert.equal(shouldNotifyPluginFormError(error, () => false, ''), false);
  });

  test('per-key plugin form requests preserve independent work and expire correctly', () => {
    const registry = createPluginFormRequestRegistry();
    const firstA = registry.start('source-a:plugin-a:v1', 1);
    const firstB = registry.start('source-b:plugin-b:v1', 1);

    assert.equal(firstA.isCurrent(1), true);
    assert.equal(firstB.isCurrent(1), true);

    const secondA = registry.start('source-a:plugin-a:v1', 1);
    assert.equal(firstA.isCurrent(1), false);
    assert.equal(secondA.isCurrent(1), true);
    assert.equal(firstB.isCurrent(1), true);

    assert.equal(secondA.isCurrent(2), false);
    assert.equal(firstB.isCurrent(2), false);
  });

  test('destroyed plugin detail requests cannot apply even when their request id is current', () => {
    assert.equal(canApplyPluginDetailResult(1, 1), true);
    assert.equal(canApplyPluginDetailResult(1, 1, true), false);
    assert.equal(canApplyPluginDetailResult(undefined, undefined, true), false);
  });

  test('withLoadingState keeps loading true when an older request finishes first', async () => {
    const deferred = () => {
      let resolve;
      let reject;
      const promise = new Promise((res, rej) => {
        resolve = res;
        reject = rej;
      });
      return { promise, resolve, reject };
    };
    const states = [];
    let currentRequestId = 'A';
    const requestA = deferred();
    const requestB = deferred();
    const start = (requestId, request) => withLoadingState(
      loading => states.push([requestId, loading]),
      () => request.promise,
      () => requestId === currentRequestId,
    );

    const resultA = start('A', requestA);
    currentRequestId = 'B';
    const resultB = start('B', requestB);
    assert.deepEqual(states, [['A', true], ['B', true]]);

    requestA.resolve({ result: true });
    await resultA;
    assert.deepEqual(states, [['A', true], ['B', true]]);

    requestB.resolve({ result: true });
    await resultB;
    assert.deepEqual(states, [['A', true], ['B', true], ['B', false]]);
  });

  test('withLoadingState ignores an older stale or failed request while a newer request is pending', async () => {
    const deferred = () => {
      let resolve;
      let reject;
      const promise = new Promise((res, rej) => {
        resolve = res;
        reject = rej;
      });
      return { promise, resolve, reject };
    };
    const run = async (finishOlderRequest) => {
      const states = [];
      let currentRequestId = 'A';
      const requestA = deferred();
      const requestB = deferred();
      const start = (requestId, request) => withLoadingState(
        loading => states.push([requestId, loading]),
        () => request.promise,
        () => requestId === currentRequestId,
      );
      const resultA = start('A', requestA);
      currentRequestId = 'B';
      const resultB = start('B', requestB);

      finishOlderRequest(requestA);
      await resultA.catch(() => undefined);
      assert.deepEqual(states, [['A', true], ['B', true]]);

      requestB.resolve({ result: true });
      await resultB;
      assert.deepEqual(states, [['A', true], ['B', true], ['B', false]]);
    };

    await run(request => request.resolve({ stale: true }));
    await run(request => request.reject(new Error('stale detail failed')));
  });

  test('resolveUniformApiPluginVersion supports metadata and legacy fallbacks', () => {
    assert.equal(resolveUniformApiPluginVersion({
      version: 'v4.0.0',
      api_meta: { plugin_version: 'v2.0' },
    }), 'v2.0');
    assert.equal(resolveUniformApiPluginVersion({ version: 'v3.0.0' }), 'v3.0.0');
  });

  test('buildUniformApiMetaParams preserves opaque plugin versions', () => {
    assert.deepEqual(buildUniformApiMetaParams({
      meta_url: '',
      meta_url_template: 'https://example.com/plugins/demo/?version={version}',
      version: 'v1.0',
      source_key: 'sops',
      scope_type: 'biz',
      scope_value: '2',
    }), {
      meta_url: '',
      meta_url_template: 'https://example.com/plugins/demo/?version={version}',
      version: 'v1.0',
      source_key: 'sops',
      scope_type: 'biz',
      scope_value: '2',
    });
  });

  test('isV4OpenPlugin requires the V4 wrapper and open-plugin identity', () => {
    assert.equal(isV4OpenPlugin(savedComponent), true);
    assert.equal(isV4OpenPlugin({
      code: 'component',
      version: '1.0.0',
      data: {},
      api_meta: {},
    }), false);
    assert.equal(isV4OpenPlugin({
      code: 'remote_plugin',
      version: '1.0.0',
      data: {
        plugin_code: { value: 'demo' },
      },
      api_meta: {},
    }), false);
    assert.equal(isV4OpenPlugin({
      code: 'uniform_api',
      version: 'v3.0.0',
      api_meta: {
        source_key: 'sops',
        id: 'builtin__job_fast_execute_script',
      },
    }), false);
    assert.equal(isV4OpenPlugin({
      code: 'uniform_api',
      version: 'v4.0.0',
      api_meta: { wrapper_version: 'v4.0.0', source_key: 'sops' },
    }), false);
  });

  test('resolveUniformApiIdentity prioritizes hidden pipeline data over api_meta', () => {
    assert.deepEqual(resolveUniformApiIdentity({
      code: 'uniform_api',
      data: {
        uniform_api_plugin_id: { value: 'hidden-id' },
        uniform_api_plugin_source_key: { value: 'hidden-source' },
        uniform_api_plugin_version: { value: 'hidden-version' },
      },
      api_meta: {
        id: 'meta-id',
        plugin_id: 'meta-plugin-id',
        source_key: 'meta-source',
        plugin_version: 'meta-version',
      },
    }), {
      pluginId: 'hidden-id',
      sourceKey: 'hidden-source',
      pluginVersion: 'hidden-version',
    });
  });

  test('buildUniformApiPluginPipelineComponent round-trips V2 and V3 without adding V4 fields', () => {
    const v2Component = {
      code: 'uniform_api',
      version: 'v2.0.0',
      data: {
        uniform_api_plugin_url: { hook: false, value: '/v2/run' },
        uniform_api_plugin_method: { hook: false, value: 'POST' },
      },
      api_meta: {
        id: 'legacy-v2',
        plugin_version: 'v2.0',
        wrapper_version: 'v2.0.0',
        source_key: 'legacy-source',
      },
    };
    const v3Component = {
      code: 'uniform_api',
      version: 'v3.0.0',
      data: {
        uniform_api_plugin_url: { hook: false, value: '/v3/run' },
        uniform_api_plugin_method: { hook: false, value: 'POST' },
        uniform_api_plugin_polling: { hook: false, value: { enabled: true } },
      },
      api_meta: {
        id: 'legacy-v3',
        plugin_version: 'v3.0',
        wrapper_version: 'v3.0.0',
        source_key: 'legacy-source',
      },
    };

    assert.deepEqual(buildUniformApiPluginPipelineComponent({
      originalComponent: v2Component,
      componentData: v2Component.data,
      basicInfo: { pluginId: 'new-id', sourceKey: 'new-source', uniform_api_plugin_version: 'new-version' },
    }), v2Component);
    assert.deepEqual(buildUniformApiPluginPipelineComponent({
      originalComponent: v3Component,
      componentData: v3Component.data,
      basicInfo: { pluginId: 'new-id', sourceKey: 'new-source', uniform_api_plugin_version: 'new-version' },
    }), v3Component);
  });

  test('buildUniformApiPluginPipelineComponent preserves V4 identity priority and execution fields', () => {
    const v4Component = {
      code: 'uniform_api',
      version: 'v4.0.0',
      data: {
        uniform_api_plugin_id: { hook: false, value: 'hidden-id' },
        uniform_api_plugin_source_key: { hook: false, value: 'hidden-source' },
        uniform_api_plugin_version: { hook: false, value: 'hidden-version' },
      },
      api_meta: {
        id: 'meta-id',
        plugin_id: 'meta-plugin-id',
        source_key: 'meta-source',
        plugin_version: 'meta-version',
        wrapper_version: 'v4.0.0',
      },
    };
    const executionData = {
      ...v4Component.data,
      uniform_api_plugin_url: { hook: false, value: 'https://sops.example/run' },
      uniform_api_plugin_method: { hook: false, value: 'POST' },
      uniform_api_plugin_polling: { hook: false, value: { path: '/status' } },
      uniform_api_plugin_callback: { hook: false, value: { path: '/callback' } },
      uniform_api_plugin_credential_key: { hook: false, value: 'credential-key' },
    };
    const result = buildUniformApiPluginPipelineComponent({
      originalComponent: v4Component,
      componentData: executionData,
      basicInfo: {
        pluginId: 'basic-info-id',
        sourceKey: 'basic-info-source',
        uniform_api_plugin_version: 'basic-info-version',
        apiKey: 'must-not-be-source',
      },
    });

    assert.deepEqual(result.data.uniform_api_plugin_id, v4Component.data.uniform_api_plugin_id);
    assert.deepEqual(result.data.uniform_api_plugin_source_key, v4Component.data.uniform_api_plugin_source_key);
    assert.deepEqual(result.data.uniform_api_plugin_version, v4Component.data.uniform_api_plugin_version);
    assert.deepEqual(result.data.uniform_api_plugin_url, executionData.uniform_api_plugin_url);
    assert.deepEqual(result.data.uniform_api_plugin_method, executionData.uniform_api_plugin_method);
    assert.deepEqual(result.data.uniform_api_plugin_polling, executionData.uniform_api_plugin_polling);
    assert.deepEqual(result.data.uniform_api_plugin_callback, executionData.uniform_api_plugin_callback);
    assert.deepEqual(result.data.uniform_api_plugin_credential_key, executionData.uniform_api_plugin_credential_key);
  });

  test('buildUniformApiPluginPipelineComponent supports hidden-only V4 identity and rejects missing version', () => {
    const hiddenOnly = {
      code: 'uniform_api',
      version: 'v4.0.0',
      data: {
        uniform_api_plugin_id: { value: 'hidden-id' },
        uniform_api_plugin_source_key: { value: 'hidden-source' },
        uniform_api_plugin_version: { value: 'hidden-version' },
      },
      api_meta: { wrapper_version: 'v4.0.0' },
    };
    assert.deepEqual(buildUniformApiPluginPipelineComponent({
      originalComponent: hiddenOnly,
      componentData: hiddenOnly.data,
      basicInfo: {},
    }), hiddenOnly);

    assert.throws(() => buildUniformApiPluginPipelineComponent({
      originalComponent: {
        ...hiddenOnly,
        data: {
          uniform_api_plugin_id: { value: 'hidden-id' },
          uniform_api_plugin_source_key: { value: 'hidden-source' },
        },
      },
      componentData: {},
      basicInfo: {},
    }), /plugin version is required/);
  });

  test('NodeConfig uses the executable pipeline component helper for API plugin saves', async () => {
    const nodeConfigSource = await readFile(
      new URL('../src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue', import.meta.url),
      'utf8',
    );
    assert.match(nodeConfigSource, /buildUniformApiPluginPipelineComponent\(/);
    assert.match(nodeConfigSource, /buildLegacyUniformApiMeta\(/);
  });

  test('task param editors fall back to extra_info for V2 API variables', async () => {
    const mockTaskParam = await readFile(
      new URL('../src/views/template/TemplateMock/MockExecute/components/TaskParamEdit.vue', import.meta.url),
      'utf8',
    );
    const taskParam = await readFile(
      new URL('../src/views/task/TaskParamEdit.vue', import.meta.url),
      'utf8',
    );
    const variableEdit = await readFile(
      new URL('../src/views/template/TemplateEdit/TemplateSetting/TabGlobalVariables/VariableEdit.vue', import.meta.url),
      'utf8',
    );
    assert.match(mockTaskParam, /buildApiVariableFormFromExtraInfo\(/);
    assert.match(taskParam, /buildApiVariableFormFromExtraInfo\(/);
    assert.match(variableEdit, /buildApiVariableFormFromExtraInfo\(/);
  });

  test('resolveV4OpenPluginVersion never treats the wrapper version as the plugin version', () => {
    assert.equal(resolveV4OpenPluginVersion(savedComponent), 'v2.0');
    assert.equal(resolveV4OpenPluginVersion({
      code: 'uniform_api',
      version: 'v4.0.0',
      api_meta: {
        wrapper_version: 'v4.0.0',
        source_key: 'sops',
        id: 'builtin__job_fast_execute_script',
      },
    }), '');
  });

  test('buildV4PluginDetailRequest uses the exact saved plugin version', () => {
    assert.deepEqual(buildV4PluginDetailRequest({
      component: savedComponent,
      spaceId: 245,
      templateId: 2329,
      scopeType: 'biz',
      scopeValue: 100605,
      selectedVersion: 'v9.9',
    }), {
      space_id: '245',
      template_id: '2329',
      plugin_type: 'uniform_api',
      plugin_code: 'builtin__job_fast_execute_script',
      plugin_version: 'v2.0',
      source_key: 'sops',
      scope_type: 'biz',
      scope_value: '100605',
    });
  });

  test('buildV4PluginDetailRequest accepts selectedVersion only for an unsaved node', () => {
    const location = {
      atomId: 'uniform_api',
      version: 'v4.0.0',
      data: {},
      api_meta: {
        wrapper_version: 'v4.0.0',
        source_key: 'sops',
        id: 'builtin__job_fast_execute_script',
      },
    };
    const component = {
      code: location.atomId,
      version: location.version,
      data: location.data,
      api_meta: location.api_meta,
    };

    assert.equal(buildV4PluginDetailRequest({
      component,
      spaceId: '245',
      templateId: '2329',
      selectedVersion: 'v3.0',
    }).plugin_version, 'v3.0');
    assert.throws(
      () => buildV4PluginDetailRequest({
        component,
        spaceId: '245',
        templateId: '2329',
      }),
      /plugin version is required/,
    );
  });

  test('buildV4PluginDetailRequest rejects selectedVersion for a saved node without version', () => {
    assert.throws(
      () => buildV4PluginDetailRequest({
        component: {
          code: 'uniform_api',
          version: 'v4.0.0',
          data: {
            uniform_api_plugin_source_key: { value: 'sops' },
          },
          api_meta: {
            wrapper_version: 'v4.0.0',
            source_key: 'sops',
            id: 'builtin__job_fast_execute_script',
          },
        },
        spaceId: '245',
        templateId: '2329',
        selectedVersion: 'v9.9',
      }),
      /plugin version is required/,
    );
  });

  test('buildUniformApiDetailState maps all save fields and normalizes methods and empty execution config', () => {
    assert.deepEqual(buildUniformApiDetailState({
      url: 'https://new.example/runs/',
      methods: ['', 'POST', null],
      response_data_path: 'data.result',
      plugin_version: 'v3.2',
      wrapper_version: 'v4.0.0',
      polling: {},
      callback: {},
      credential_key: 'new-credential',
    }, { method: 'GET' }), {
      realMetaUrl: 'https://new.example/runs/',
      method: 'POST',
      respDataPath: 'data.result',
      version: 'v3.2',
      uniform_api_plugin_version: 'v3.2',
      wrapperVersion: 'v4.0.0',
      methodList: ['POST'],
      polling: null,
      callback: null,
      credentialKey: 'new-credential',
    });
  });

  test('buildUniformApiComponent represents the current V4 identity and keeps other plugin routes non-V4', () => {
    const v4Component = buildUniformApiComponent({
      plugin: 'uniform_api',
      wrapperVersion: 'v4.0.0',
      pluginId: 'new-plugin',
      sourceKey: 'new-source',
      uniform_api_plugin_version: 'v3.2',
    });

    assert.equal(isV4OpenPlugin(v4Component), true);
    assert.deepEqual(v4Component.data, {
      uniform_api_plugin_version: { hook: false, value: 'v3.2' },
      uniform_api_plugin_id: { hook: false, value: 'new-plugin' },
      uniform_api_plugin_source_key: { hook: false, value: 'new-source' },
    });
    assert.deepEqual(buildV4PluginDetailRequest({
      component: v4Component,
      spaceId: 245,
      templateId: 2329,
      scopeType: 'biz',
      scopeValue: 100605,
    }), {
      space_id: '245',
      template_id: '2329',
      plugin_type: 'uniform_api',
      plugin_code: 'new-plugin',
      plugin_version: 'v3.2',
      source_key: 'new-source',
      scope_type: 'biz',
      scope_value: '100605',
    });
    assert.equal(isV4OpenPlugin(buildUniformApiComponent({
      plugin: 'uniform_api',
      wrapperVersion: 'v3.0.0',
      pluginId: 'legacy-plugin',
      sourceKey: 'legacy-source',
    })), false);
    assert.equal(isV4OpenPlugin(buildUniformApiComponent({
      plugin: 'uniform_api',
      wrapperVersion: 'v2.0.0',
      pluginId: 'v2-plugin',
      sourceKey: 'v2-source',
    })), false);
    assert.equal(isV4OpenPlugin(buildUniformApiComponent({ plugin: 'component', version: '1.0.0' })), false);
    assert.equal(isV4OpenPlugin(buildUniformApiComponent({ plugin: 'remote_plugin', version: '1.0.0' })), false);
  });

  test('canApplyPluginDetailResult rejects stale plugin and version responses', () => {
    assert.equal(canApplyPluginDetailResult(1, 2), false);
    assert.equal(canApplyPluginDetailResult(2, 2), true);
  });

  test('mergeV4ObjectSchema keeps all properties and maps all required fields', () => {
    const result = mergeV4ObjectSchema(
      { type: 'object', properties: {}, required: [] },
      {
        type: 'object',
        properties: {
          tagCode: { type: 'string' },
          extra: { type: 'number' },
        },
        required: ['tagCode', 'extra'],
      },
      { preferredKey: 'variable_key', sourceKey: 'tagCode' },
    );

    assert.deepEqual(Object.keys(result.properties), ['variable_key', 'extra']);
    assert.deepEqual(result.required, ['variable_key', 'extra']);
    assert.deepEqual(result.properties.extra, { type: 'number' });
  });

  test('mergeV4ObjectSchema resolves colliding properties deterministically without dropping fields', () => {
    const first = mergeV4ObjectSchema(
      { type: 'object', properties: {}, required: [] },
      { type: 'object', properties: { shared: { type: 'string' } }, required: ['shared'] },
      { namespace: 'first' },
    );
    const second = mergeV4ObjectSchema(
      first,
      {
        type: 'object',
        properties: {
          shared: { type: 'number' },
          second: { type: 'boolean' },
        },
        required: ['shared', 'second'],
      },
      { namespace: 'second' },
    );

    assert.deepEqual(Object.keys(second.properties), ['shared', 'shared__second', 'second']);
    assert.deepEqual(second.required, ['shared', 'shared__second', 'second']);
    assert.deepEqual(second.properties.shared__second, { type: 'number' });
  });

  test('validatePluginFormSections awaits all sections and blocks required failures', async () => {
    const events = [];
    const invalidSections = [
      { validate: () => Promise.resolve(true) },
      { validate: () => new Promise(resolve => setTimeout(() => {
        events.push('required-failed');
        resolve(false);
      }, 5)) },
    ];
    assert.equal(await validatePluginFormSections(invalidSections), false);
    assert.deepEqual(events, ['required-failed']);

    const validSections = [
      { validate: () => Promise.resolve(true) },
      { validate: () => Promise.resolve(true) },
    ];
    assert.equal(await validatePluginFormSections(validSections), true);
  });

  test('validatePluginFormSections normalizes Vue array and single refs', async () => {
    const calls = [];
    const arrayRef = [
      { validate: async () => { calls.push('array-1'); return true; } },
      { validate: async () => { calls.push('array-2'); return false; } },
    ];
    const singleRef = { validate: async () => { calls.push('object'); return true; } };

    assert.deepEqual(normalizePluginFormRefs([arrayRef, singleRef]), [
      arrayRef[0],
      arrayRef[1],
      singleRef,
    ]);
    assert.equal(await validatePluginFormSections([arrayRef, singleRef]), false);
    assert.deepEqual(calls, ['array-1', 'array-2', 'object']);
  });

  test('mergePluginFormSections keeps Array and Object fields in either order', () => {
    const arrayField = { tag_code: 'array_field', attrs: { name: 'array_field' } };
    const objectField = {
      type: 'object',
      properties: { object_field: { type: 'string' } },
      required: ['object_field'],
    };

    const arrayThenObject = mergePluginFormSections(
      mergePluginFormSections([], arrayField),
      objectField,
    );
    const objectThenArray = mergePluginFormSections(
      mergePluginFormSections([], objectField),
      arrayField,
    );

    for (const sections of [arrayThenObject, objectThenArray]) {
      assert.deepEqual(sections.find(section => section.type === 'array').scheme, [arrayField]);
      assert.deepEqual(sections.find(section => section.type === 'object').scheme, objectField);
    }
  });

  test('resolveVariableSourceComponent recovers V4 identity from pipeline activities', () => {
    const variable = {
      key: '${bk_biz_id}',
      source_info: { nodeabc: ['bk_biz_id'] },
      source_tag: 'uniform_api.bk_biz_id',
      version: 'v2.0.0',
      plugin_code: '',
    };
    const component = resolveVariableSourceComponent(variable, {
      activities: { nodeabc: { component: savedComponent } },
      atom: 'uniform_api',
      version: 'v2.0.0',
    });

    assert.equal(component, savedComponent);
    assert.equal(isV4OpenPlugin(component), true);
  });

  test('resolveVariableSourceComponent does not invent V4 identity from hooked constants', () => {
    const variable = {
      key: '${bk_biz_id}',
      source_info: { nodeabc: ['bk_biz_id'] },
      source_tag: 'uniform_api.bk_biz_id',
      version: 'v2.0.0',
      plugin_code: '',
    };
    const component = resolveVariableSourceComponent(variable, {
      atom: 'uniform_api',
      version: 'v2.0.0',
    });

    assert.equal(isV4OpenPlugin(component), false);
    assert.equal(component.code, 'uniform_api');
    assert.equal(component.version, 'v2.0.0');
  });

  test('resolveVariableSourceComponent prefers explicit component over source_info', () => {
    const explicit = { ...savedComponent, data: { ...savedComponent.data, mark: 'explicit' } };
    const fromTree = { ...savedComponent, data: { ...savedComponent.data, mark: 'tree' } };
    const component = resolveVariableSourceComponent({
      component: explicit,
      node_component: fromTree,
      source_info: { nodeabc: ['bk_biz_id'] },
    }, {
      activities: { nodeabc: { component: fromTree } },
    });

    assert.equal(component.data.mark, 'explicit');
  });

  test('resolveNewOpenPluginVersion prefers latest_version over default_version', () => {
    assert.equal(resolveNewOpenPluginVersion({
      defaultVersion: '1.0.0',
      latestVersion: '2.0.0',
      versions: ['1.0.0', '2.0.0'],
    }), '2.0.0');
    assert.equal(resolveNewOpenPluginVersion({
      latestVersion: '2.0.0',
      versions: [{ version: '1.0.0' }, { version: '2.0.0' }],
    }), '2.0.0');
    assert.equal(resolveNewOpenPluginVersion({
      versions: [{ version: '1.0.0' }, { version: '1.1.0' }],
    }), '1.1.0');
  });

  test('getOpenPluginSchemaSnapshot prefers execution node id then template node id', () => {
    const extraInfo = {
      plugin_schema_snapshot: {
        node1: { plugin_code: 'job_execute_task' },
        tpl_node: { plugin_code: 'from_template' },
      },
    };
    assert.equal(getOpenPluginSchemaSnapshot(extraInfo, 'node1', 'tpl_node').plugin_code, 'job_execute_task');
    assert.equal(getOpenPluginSchemaSnapshot(extraInfo, 'missing', 'tpl_node').plugin_code, 'from_template');
    assert.equal(getOpenPluginSchemaSnapshot({}, 'node1'), null);
  });

  test('buildV4DetailFromSchemaSnapshot rejects unknown protocol versions', () => {
    assert.throws(
      () => buildV4DetailFromSchemaSnapshot({ schema_protocol_version: 'unknown.v9' }),
      error => /schema_protocol_version/.test(error.message),
    );
    const detail = buildV4DetailFromSchemaSnapshot({
      schema_protocol_version: 'open_plugin_snapshot.v1',
      plugin_code: 'job_execute_task',
      inputs: [{ name: 'bk_biz_id' }],
    });
    assert.equal(detail.plugin_code, 'job_execute_task');
    assert.equal(detail.forms.input, null);
  });

  test('disablePluginFormFields updates array and object sections without throwing', () => {
    const sections = disablePluginFormFields([
      {
        type: 'array',
        scheme: [
          { tag_code: '${bk_biz_id}', attrs: { name: '业务' } },
          { tag_code: '${job_script}', attrs: { name: '脚本' } },
        ],
      },
      {
        type: 'object',
        scheme: {
          type: 'object',
          properties: {
            '${account}': { type: 'string', title: '账号' },
            '${other}': { type: 'string', title: '其他' },
          },
        },
      },
    ], ['${bk_biz_id}', '${account}', '${missing}'], {
      disabled: true,
      used_tip: '参数已被使用，不可修改',
    });

    const arrayField = sections[0].scheme.find(item => item.tag_code === '${bk_biz_id}');
    assert.equal(arrayField.attrs.disabled, true);
    assert.equal(arrayField.attrs.used_tip, '参数已被使用，不可修改');
    assert.equal(sections[0].scheme.find(item => item.tag_code === '${job_script}').attrs.disabled, undefined);
    assert.equal(sections[1].scheme.properties['${account}']['ui:component'].props.disabled, true);
    assert.equal(
      sections[1].scheme.properties['${account}']['x-bkflow-used-tip'],
      '参数已被使用，不可修改',
    );
    assert.equal(sections[1].scheme.properties['${other}']['ui:component'], undefined);
    assert.equal(sections[1].scheme.properties['${other}']['x-bkflow-used-tip'], undefined);
  });

  test('mergeV4VariableObjectField only keeps the hooked field from a full plugin schema', () => {
    const pluginSchema = {
      type: 'object',
      properties: {
        a: { type: 'string', title: 'A' },
        b: { type: 'string', title: 'B' },
      },
      required: ['a', 'b'],
    };
    const first = mergeV4VariableObjectField(
      { type: 'object', properties: {}, required: [] },
      pluginSchema,
      { key: '${var_a}' },
      'a',
    );
    const second = mergeV4VariableObjectField(first, pluginSchema, { key: '${var_b}' }, 'b');

    assert.deepEqual(Object.keys(second.properties), ['${var_a}', '${var_b}']);
    assert.deepEqual(second.required, ['${var_a}', '${var_b}']);
  });

  test('buildVariablePluginRuntimeInputs maps original tag codes from activities and constants', () => {
    const activities = {
      nodeabc: {
        component: {
          ...savedComponent,
          data: {
            ...savedComponent.data,
            a: { value: 'saved-a' },
            b: { value: 'saved-b' },
            c: { value: 'saved-c' },
          },
        },
      },
    };
    const constants = {
      '${var_a}': { key: '${var_a}', value: 'current-a', source_info: { nodeabc: ['a'] } },
      '${var_b}': { key: '${var_b}', value: 'current-b', source_info: { nodeabc: ['b'] } },
    };

    const inputs = buildVariablePluginRuntimeInputs({
      variable: constants['${var_a}'],
      activities,
      constants,
    });

    assert.deepEqual(inputs, {
      a: 'current-a',
      b: 'current-b',
      c: 'saved-c',
    });
    assert.equal(buildVariablePluginRuntimeInputs({
      variable: constants['${var_a}'],
    }).a, undefined);
  });

  test('buildOutputRenderData converts array and object outputs to form values', () => {
    assert.deepEqual(buildOutputRenderData([
      { key: 'job_inst_id', name: '作业实例 ID', value: 1001 },
      { key: 'log', name: '日志', value: 'ok' },
    ]), {
      job_inst_id: 1001,
      log: 'ok',
    });
    assert.deepEqual(buildOutputRenderData({
      job_inst_id: 1001,
      log: 'ok',
      ex_data: 'hidden',
    }), {
      job_inst_id: 1001,
      log: 'ok',
    });
    assert.deepEqual(buildOutputRenderData(), {});
    assert.deepEqual(buildOutputRenderData(null), {});
  });

  test('resolveNodeExecutionPayload reads outputs and state from API envelope data', () => {
    const envelope = {
      result: true,
      data: {
        inputs: { cmd: 'ls' },
        outputs: [{ key: 'job_inst_id', value: 1001 }],
        state: 'FAILED',
      },
    };

    assert.deepEqual(resolveNodeExecutionPayload(envelope), {
      inputs: { cmd: 'ls' },
      outputs: [{ key: 'job_inst_id', value: 1001 }],
      state: 'FAILED',
    });
    assert.deepEqual(resolveNodeExecutionPayload(envelope.data), {
      inputs: { cmd: 'ls' },
      outputs: [{ key: 'job_inst_id', value: 1001 }],
      state: 'FAILED',
    });
    assert.equal(resolveNodeExecutionPayload({ result: true, data: { inputs: {} } }).state, undefined);
    assert.deepEqual(resolveNodeExecutionPayload({}).outputs, []);
  });

  test('buildLegacyUniformApiMeta writes pre-V4 api_meta when original is missing', () => {
    const meta = buildLegacyUniformApiMeta({
      basicInfo: {
        pluginId: 'hy3',
        name: 'AI-hy3',
        apiPluginName: 'hy3',
        metaUrl: 'https://plugins.example.com/meta/hy3',
        apiKey: 'aidev',
        groupId: 'llm',
        groupName: 'LLM',
      },
    });

    assert.deepEqual(meta, {
      id: 'hy3',
      name: 'hy3',
      meta_url: 'https://plugins.example.com/meta/hy3',
      api_key: 'aidev',
      category: {
        id: 'llm',
        name: 'LLM',
      },
    });
    assert.equal(meta.wrapper_version, undefined);
    assert.equal(meta.source_key, undefined);
    assert.equal(meta.versions, undefined);
  });

  test('buildLegacyUniformApiMeta keeps original api_meta and skips empty pluginId', () => {
    const originalApiMeta = {
      id: 'legacy-v2',
      name: 'legacy',
      meta_url: 'https://plugins.example.com/meta/legacy',
      api_key: 'old',
      category: { id: 'old-group', name: 'Old' },
    };

    assert.deepEqual(buildLegacyUniformApiMeta({
      basicInfo: { pluginId: 'hy3', metaUrl: 'https://ignored.example' },
      originalApiMeta,
    }), originalApiMeta);
    assert.equal(buildLegacyUniformApiMeta({ basicInfo: {} }), null);
    assert.equal(buildLegacyUniformApiMeta({ basicInfo: { pluginId: '' } }), null);
  });

  test('buildApiVariableFormFromExtraInfo renders hooked V2 query from extra_info', () => {
    const form = buildApiVariableFormFromExtraInfo({
      name: '用户对话',
      key: '${query}',
      desc: '',
      source_tag: 'uniform_api.query',
      extra_info: {
        type: 'string',
        form_type: 'textarea',
        required: true,
      },
    });

    assert.equal(form.length, 1);
    assert.equal(form[0].type, 'textarea');
    assert.equal(form[0].tag_code, 'query');
    assert.equal(form[0].attrs.name, '用户对话');
    assert.deepEqual(form[0].attrs.validation, [{ type: 'required' }]);
    assert.equal(buildApiVariableFormFromExtraInfo({ key: '${query}' }), null);
    assert.equal(buildApiVariableFormFromExtraInfo({ extra_info: {} }), null);
  });
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
