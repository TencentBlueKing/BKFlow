/**
 * 冻结 MonacoEnvironment，阻止当前 SDK 的 setupMonacoEnvironment() 用 ESM Worker 覆盖接入项目的经典 Worker。
 *
 * 背景：
 *  - 宿主通过 MonacoWebpackPlugin 注入经典 Worker 配置（self.MonacoEnvironment.getWorkerUrl），
 *    对应 worker 文件由 webpack 编译输出为 [name].worker.js（editor.worker.js / ts.worker.js / ...），
 *    其 loadForeignModule 走 AMD require，TS 语言特性（inlayHints / codeAction / outline / stickyScroll 等）可正常工作。
 *  - SDK 的 setupMonacoEnvironment() 在模块加载时若发现 self.MonacoEnvironment 为空，
 *    会把 self.MonacoEnvironment 覆盖成 `new Worker(path, { type: 'module' })` 的 ESM Worker。
 *    ESM 版 editorSimpleWorker 的 loadForeignModule 被硬编码为 reject('Unexpected usage')，
 *    且裸模块路径在 webpack dev server 下会被 historyApiFallback 喂成 index.html（Unexpected token '<'）。
 *  - 因此这里把 self.MonacoEnvironment 锁成访问器，忽略 SDK 的覆盖赋值；
 *    并始终使用我们自己可控的经典 getWorkerUrl（指向 MonacoWebpackPlugin 实际产出的 [name].worker.js），
 *    不再信任插件注入的 getWorkerUrl（它在部分环境下对 editorWorkerService 等 label 会返回 undefined，
 *    导致 worker 去抓 /undefined 拿到 HTML）。
 */
/* eslint-disable no-undef */
// 与 MonacoWebpackPlugin 默认 filename '[name].worker.js' 对应的产物名
// 注意：宿主 MonacoWebpackPlugin 仅配置了 languages: ['javascript', 'json']，
// 实际只产出 editor.worker.js / ts.worker.js / json.worker.js，本映射覆盖全部可能 label（其余指向 editor.worker.js 兜底）
const workerFileMap = {
  editorWorkerService: 'editor.worker.js',
  typescript: 'ts.worker.js',
  javascript: 'ts.worker.js',
  json: 'json.worker.js',
  css: 'css.worker.js',
  scss: 'css.worker.js',
  less: 'css.worker.js',
  html: 'html.worker.js',
  handlebars: 'html.worker.js',
  razor: 'html.worker.js',
};

// 读取 webpack public path，并防御 public-path.js 把 __webpack_public_path__ 误设为字符串 'undefined' / 'null'
const getPublicPath = () => {
  const raw = typeof __webpack_public_path__ === 'string' ? __webpack_public_path__ : '';
  if (raw === 'undefined' || raw === 'null' || raw === '') {
    return '';
  }
  return raw.replace(/\/$/, ''); // 去掉尾部斜杠，统一在拼 URL 时处理
};

// 计算 worker 文件的基址（绝对 URL）
const getWorkerBaseUrl = () => {
  const prefix = getPublicPath();
  if (!prefix) {
    // 未配置静态资源前缀（如本地 dev server）：worker 由 webpack 输出在站点根
    return `${window.location.origin}/`;
  }
  if (/^https?:\/\//i.test(prefix)) {
    // 完整 CDN 地址（如 https://cdn.example.com/static）
    return `${prefix.replace(/\/$/, '')}/`;
  }
  // 形如 /static 或 static 的路径前缀
  const pathPart = prefix.replace(/^\/+/, '');
  return `${window.location.origin}/${pathPart}/`;
};

// 经典 Worker：返回 MonacoWebpackPlugin 编译输出的 worker 文件绝对 URL，由 Monaco 以 classic Worker 方式加载
const classicGetWorkerUrl = (moduleId, label) => {
  const file = workerFileMap[label] || 'editor.worker.js';
  return new URL(file, getWorkerBaseUrl()).href;
};

Object.defineProperty(self, 'MonacoEnvironment', {
  configurable: false,
  enumerable: true,
  get() {
    // 返回新对象可让 SDK 的污染失效，确保始终用经典 getWorkerUrl 加载 [name].worker.js（AMD require，TS 特性正常）
    return { getWorkerUrl: classicGetWorkerUrl };
  },
  set() {
    // 忽略 SDK 的覆盖赋值，保持经典 Worker 配置
  },
});
