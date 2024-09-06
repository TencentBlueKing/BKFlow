module.exports = {
  root: true,
  parserOptions: {
    parser: 'babel-eslint',
    ecmaVersion: 2018,
    sourceType: 'module',
    ecmaFeatures: {
      jsx: true,
      modules: true,
    },
  },
  env: {
    browser: true,
  },
  // https://github.com/standard/standard/blob/master/docs/RULES-en.md
  extends: ['@tencent/eslint-config-tencent', 'plugin:vue/recommended'],
  // required to lint *.vue files
  plugins: [
    'vue',
  ],
  globals: {
    // value 为 true 允许被重写，为 false 不允许被重写
    NODE_ENV: true,
    BUILD_TARGET: true,
    SITE_URL: true,
    BACKEND_URL: true,
    LOGIN_SERVICE_URL: true,
    LEGACY_APP_MIGRATION_ENABLED: true,
    AJAX_URL_PIRFIX: true,
    GRAFANA_IFRAME_URL: true,
    gettext: true,
    $: true
  },
  rules: {
    // 闭合括号禁止换行
    "vue/html-closing-bracket-newline": [
      "error",
      {
        "singleline": "never",
        "multiline": "never"
      }
    ],
    // 不要改变入参。不限制
    'no-param-reassign': 'off',
    // https://eslint.org/docs/rules/no-useless-escape
    // 禁止出现没必要的转义。不限制
    'no-useless-escape': 'off',
    // https://github.com/vuejs/eslint-plugin-vue/blob/master/docs/rules/camelcase.md
    // 后端数据字段经常不是驼峰，所以不限制 properties，也不限制解构
    'vue/camelcase': ['error', { properties: 'never', ignoreDestructuring: true }],
    // https://github.com/vuejs/eslint-plugin-vue/blob/master/docs/rules/no-side-effects-in-computed-properties.md
    // 禁止在计算属性对属性进行修改，不限制
    'vue/no-side-effects-in-computed-properties': 'off',
    // https://github.com/vuejs/eslint-plugin-vue/blob/master/docs/rules/no-v-html.md
    // 禁止使用 v-html，防止 xss
    'vue/no-v-html': 'off',
  },
  overrides: [
    {
      files: ['*.vue'],
      rules: {
        indent: 'off',
      },
    },
  ],
};
