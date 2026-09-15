const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const createLoader = require('./helpers/loadSourceModule');

const sourceRoot = path.resolve(__dirname, '../src');
const cases = [
  ['components/layout/Navigation.vue', ['logo']],
  ['components/common/base/NoData.vue', ['notDataUrl', 'searchEmptyUrl']],
  ['components/common/modal/ErrorCodeModal.vue', ['expPic500']],
  ['components/common/modal/home.vue', Array.from({ length: 16 }, (_, index) => `image${index + 1}`)],
];

function assetModule(name) {
  // Match the Module namespace object captured in the STAG img.src failure.
  return Object.assign(Object.create(null), {
    __esModule: true,
    default: `/static/${name}`,
    [Symbol.toStringTag]: 'Module',
  });
}

for (const [file, fields] of cases) {
  test(`${file}: image bindings remain URL strings when the bundler returns an ES module`, () => {
    const source = fs.readFileSync(path.join(sourceRoot, file), 'utf8');
    const component = { __esModule: true, default: {} };
    const mocks = {
      vuex: { mapState: () => ({}), mapActions: () => ({}), mapMutations: () => ({}) },
      './NavigationHeadLeft.vue': component,
      './NavigationHeadRight.vue': component,
      './NavigationMenu.vue': component,
      './ErrorCode403.vue': component,
      './ErrorCode500.vue': component,
    };
    for (const [, asset] of source.matchAll(/['"]([^'"]+\.(?:png|jpe?g|gif|svg))['"]/g)) {
      mocks[asset] = assetModule(path.basename(asset));
    }
    const values = createLoader(mocks)(file).default.data();
    for (const field of fields) {
      assert.equal(typeof values[field], 'string', `${field} must be a URL, not a module namespace`);
      assert.match(String(values[field]), /^\/static\/.+\.(png|jpe?g|gif|svg)$/);
    }
  });
}

for (const file of [
  'components/common/Individualization/cronRuleSelect.vue',
  'components/common/Individualization/loopRuleSelect.vue',
  'views/template/TemplateEdit/TemplateSetting/CronRuleSelect.vue',
]) {
  for (const language of ['zh', 'en']) {
    test(`${file}: cron illustration remains a URL for ${language}`, (context) => {
      const previousWindow = global.window;
      global.window = { PERIODIC_TASK_SHORTEST_TIME: 5 };
      context.after(() => {
        if (previousWindow === undefined) delete global.window;
        else global.window = previousWindow;
      });
      const mocks = {
        '@/config/i18n/index.js': {
          __esModule: true,
          default: {
            t: value => value === 'task-zh' ? `task-${language}` : value,
            tc: value => value,
          },
        },
        '@/assets/images/task-zh.png': assetModule('task-zh.png'),
        '@/assets/images/task-en.png': assetModule('task-en.png'),
        '@/constants/index.js': {},
        '@/utils/tools.js': { debounce: handler => handler },
        '@/utils/cron.js': {},
        'cron-parser-custom': {},
      };
      const values = createLoader(mocks)(file).default.data.call({ value: '*/5 * * * *' });
      assert.equal(values.periodicCronImg, `/static/task-${language}.png`);
    });
  }
}
