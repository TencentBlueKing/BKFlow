const assert = require('assert');
const createLoader = require('./helpers/loadSourceModule');

async function run() {
  const calls = [];
  const axios = {
    put: async (...args) => { calls.push(args); return {data: {data: {language: 'en'}}}; },
    jsonp: async (...args) => { calls.push(args); return {result: true}; },
  };
  const {updatePlatformLanguage} = createLoader()('utils/platformLanguage.js');
  for (const tenant of ['default', 'tenant-a']) {
    await updatePlatformLanguage(axios, {USE_APIGW: true, TENANT_ID: tenant, BK_USER_WEB_APIGW_URL: 'https://user.example/prod/'}, 'en');
    const [url, body, options] = calls.pop();
    assert.strictEqual(url, 'https://user.example/prod/api/v3/open-web/tenant/current-user/language/');
    assert.deepStrictEqual(body, {language: 'en'});
    assert.strictEqual(options.headers['X-Bk-Tenant-Id'], tenant);
    assert.strictEqual(options.withCredentials, true);
  }
  await updatePlatformLanguage(axios, {USE_APIGW: false, BK_PAAS_ESB_HOST: 'https://legacy.example'}, 'zh-cn');
  assert(calls.pop()[0].includes('/api/c/compapi/v2/usermanage/fe_update_user_language/'));
  await assert.rejects(updatePlatformLanguage({put: async () => ({data: {result: false, message: 'denied'}})}, {USE_APIGW: true, BK_USER_WEB_APIGW_URL: 'https://user.example'}, 'en'));

  let cookies = 0;
  let reloads = 0;
  const loader = createLoader({
    axios,
    'js-cookie': {set: () => { cookies += 1; }},
    vuex: {mapActions: () => ({}), mapMutations: () => ({}), mapState: x => x},
    './VersionLog.vue': {},
    '@blueking/login-userinfo/vue2': {},
    '@blueking/login-userinfo/vue2/vue2.css': {},
    '@blueking/user-selector': {},
    '@blueking/bk-user-selector/vue2': {},
    '@blueking/bk-user-selector/vue2/vue2.css': {},
  });
  const navigation = loader('components/layout/NavigationHeadRight.vue').default;
  global.window = {USE_APIGW: true, BK_USER_WEB_APIGW_URL: 'https://user.example', location: {hostname: 'flow.example.com', reload: () => { reloads += 1; }}};
  const component = {curLanguage: 'chinese', $t: x => x, $bkMessage: () => {}};
  axios.put = async () => { throw new Error('offline'); };
  const warn = console.warn;
  console.warn = () => {};
  try {
    await navigation.methods.toggleLanguage.call(component, 'english');
  } finally {
    console.warn = warn;
  }
  assert.strictEqual(component.curLanguage, 'chinese');
  assert.strictEqual(cookies + reloads, 0);
  axios.put = async () => ({data: {data: {language: 'en'}}});
  await navigation.methods.toggleLanguage.call(component, 'english');
  assert.strictEqual(cookies, 1);
  assert.strictEqual(reloads, 1);

  const selector = loader('components/common/Individualization/MemberSelect.vue').default;
  for (const useApigw of [false, true]) {
    window.USE_APIGW = useApigw;
    window.ENABLE_MULTI_TENANT_MODE = false;
    assert.strictEqual(selector.computed.useApigw(), useApigw);
    assert.strictEqual(selector.data().tenantId, 'default');
  }
  const cron = createLoader({
    '@/assets/images/task-zh.png': '', '@/assets/images/task-en.png': '',
    '@/utils/tools.js': {debounce: x => x},
  })('views/template/TemplateEdit/TemplateSetting/CronRuleSelect.vue').default;
  for (const timezone of ['Europe/Paris', 'Asia/Tokyo']) {
    const context = {timezone, nextTime: []};
    cron.methods.checkAndTranslate.call(context, '0 9 * * *');
    assert.strictEqual(context.nextTime.length, 5);
    assert(context.nextTime.every(time => time.endsWith('09:00:00')));
  }
  console.log('release compatibility: APIGW/legacy language, failure handling, member selector and timezone preview passed');
}
run().catch(error => { console.error(error); process.exitCode = 1; });
