const assert = require('assert');
const createLoader = require('./helpers/loadSourceModule');

const load = createLoader();
const { formatTaskPluginMetaError } = load('utils/taskPluginError.js');

const t = (message, context = {}) => message
  .replace('{name}', context.name)
  .replace('{version}', context.version);

function response(errorCode, status) {
  return {
    data: {
      result: false,
      message: 'formatted provider failure',
      error_code: errorCode,
    },
    status,
  };
}

const context = {
  pluginCode: 'hy3-preview',
  pluginName: 'hy3-preview',
  pluginVersion: '1.0.0',
  t,
};

const unavailableResponse = response('PLUGIN_UNAVAILABLE');
assert.strictEqual(formatTaskPluginMetaError(unavailableResponse, context), undefined);

const denied = formatTaskPluginMetaError(response('PLUGIN_DETAIL_UNAVAILABLE'), context);
assert.strictEqual(denied.title, '插件详情加载失败');
assert.ok(denied.message.includes('可能已下架或当前无访问权限'));

const v4Unavailable = formatTaskPluginMetaError(response(undefined, 404), context);
assert.strictEqual(v4Unavailable.title, '插件已下架，节点参数无法加载');

const v4Denied = formatTaskPluginMetaError(response(undefined, 403), context);
assert.strictEqual(v4Denied.title, '插件详情加载失败');

const emptyV4Denied = formatTaskPluginMetaError({ data: null, status: 403 }, context);
assert.strictEqual(emptyV4Denied.title, '插件详情加载失败');

assert.strictEqual(formatTaskPluginMetaError(response('OTHER'), context), undefined);

console.log('task plugin error tests passed');
