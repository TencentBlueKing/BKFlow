const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const createLoader = require('./helpers/loadSourceModule');

async function run() {
  const { buildUserNavigationActions } = createLoader()('utils/userNavigation.js');
  const logout = () => {};
  for (const value of [undefined, null, '', 'None', 'undefined', 'javascript:alert(1)', '/relative']) {
    const actions = buildUserNavigationActions({iamUrl: value, userUrl: value, translate: x => x, logout});
    assert.strictEqual(actions.length, 1);
    assert.strictEqual(actions[0].handle, logout);
  }
  const configured = buildUserNavigationActions({
    iamUrl: 'https://iam.example/', userUrl: 'https://user.example/', translate: x => x, logout,
  });
  assert.deepStrictEqual(configured.map(action => action.href), [
    'https://iam.example', 'https://user.example/personal-center', undefined,
  ]);
  const calls = [];
  const axios = {
    post: async (url, data) => { calls.push({url, data}); return {data: {result: true}}; },
    patch: async (url, data) => { calls.push({url, data}); return {data: {result: true}}; },
  };
  const store = createLoader({axios})('store/modules/system.js').default;
  for (const enabled of [false, true]) {
    global.window = {ENABLE_MULTI_TENANT_MODE: enabled, TENANT_ID: enabled ? 'tenant-a' : ''};
    await store.actions.updateSpaceConfig({}, {name: 'create'});
    await store.actions.updateSpaceConfig({}, {id: 1, name: 'edit'});
    for (const call of calls.splice(0)) {
      assert.strictEqual(Object.hasOwn(call.data, 'tenant_id'), enabled);
      if (enabled) assert.strictEqual(call.data.tenant_id, 'tenant-a');
    }
  }
  const source = fs.readFileSync(path.resolve(__dirname, '../../bkflow/pipeline_plugins/static/components/notify/v1_0.js'), 'utf8');
  for (const data of [
    [{type: 'mail', label: '邮件', is_active: true}, {type: 'sms', label: '短信', is_active: false}],
    [{type: 'mail', name: '邮件', enabled: true}, {type: 'sms', name: '短信', enabled: false}],
  ]) {
    const context = {gettext: x => x, show_msg: () => {}, $: {atoms: {}, context: {get: () => '/'}, ajax: ({success}) => success({result: true, data})}};
    vm.runInNewContext(source, context);
    const form = {items: []};
    context.$.atoms.bk_notify[0].methods._tag_init.call(form);
    assert.deepStrictEqual(JSON.parse(JSON.stringify(form.items)), [{name: '邮件', value: 'mail'}]);
  }
  console.log('tenant compatibility: legacy/modern channels and space create/edit passed');
}
run().catch(error => { console.error(error); process.exitCode = 1; });
