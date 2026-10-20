const assert = require('assert');
const fs = require('fs');
const path = require('path');
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
assert.strictEqual(denied.title, '插件可能已下架或当前无访问权限，请联系管理员确认。');
assert.strictEqual(denied.message, denied.title);
assert.strictEqual(denied.singleLine, true);

const v4Unavailable = formatTaskPluginMetaError(response(undefined, 404), context);
assert.strictEqual(v4Unavailable.title, v4Unavailable.message);
assert.strictEqual(v4Unavailable.singleLine, true);

const v4Denied = formatTaskPluginMetaError(response(undefined, 403), context);
assert.strictEqual(v4Denied.title, v4Denied.message);
assert.strictEqual(v4Denied.singleLine, true);

const emptyV4Denied = formatTaskPluginMetaError({ data: null, status: 403 }, context);
assert.strictEqual(emptyV4Denied.title, emptyV4Denied.message);

assert.strictEqual(formatTaskPluginMetaError(response('OTHER'), context), undefined);

let messageOptions;
global.window = {
  MESSAGE_HELPER_URL: '',
  msg_list: [{ msg: denied.message }],
};
const notifyLoad = createLoader({
  '@/utils/bus.js': { __esModule: true, default: { $emit() {} } },
});
const ErrorNotify = notifyLoad('utils/errorNotify.js').default;
new ErrorNotify(
  {
    msg: denied.message,
    title: denied.title,
    type: 'error',
    singleLine: true,
  },
  {
    errorMsgList: [],
    $bkMessage(options) {
      messageOptions = options;
      return {};
    },
  },
);
assert.strictEqual(messageOptions.message, denied.message);
assert.strictEqual(messageOptions.icon, 'icon-close-circle-shape');
assert.strictEqual(messageOptions.extCls, undefined);
assert.strictEqual(messageOptions.actions, undefined);

const appSource = fs.readFileSync(path.resolve(__dirname, '../src/App.vue'), 'utf8');
assert.ok(appSource.includes('info.singleLine'));
assert.ok(appSource.includes('.bk-message .icon-close-circle-shape::before'));
assert.ok(appSource.includes('content: "\\e134"'));

console.log('task plugin error tests passed');
