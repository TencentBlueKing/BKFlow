const fs = require('fs');
const path = require('path');
const babel = require('@babel/core');

// Compile real frontend modules; only browser/framework boundaries are replaced.
module.exports = function createLoader(mocks = {}) {
  const sourceRoot = path.resolve(__dirname, '../../src');
  const cache = new Map();
  function load(relativePath) {
    const file = path.resolve(sourceRoot, relativePath);
    if (cache.has(file)) return cache.get(file).exports;
    let source = fs.readFileSync(file, 'utf8');
    if (file.endsWith('.vue')) source = source.match(/<script>([\s\S]*?)<\/script>/)[1];
    const { code } = babel.transformSync(source, {
      babelrc: false,
      configFile: false,
      plugins: ['@babel/plugin-transform-modules-commonjs'],
    });
    const module = { exports: {} };
    cache.set(file, module);
    function localRequire(id) {
      if (id in mocks) return mocks[id];
      if (id === '@/utils/i18n.js' || id === '@/config/i18n/index.js') {
        return { __esModule: true, default: { t: value => value } };
      }
      if (id.startsWith('.') || id.startsWith('@/')) {
        let resolved = id.startsWith('@/') ? path.join(sourceRoot, id.slice(2)) : path.resolve(path.dirname(file), id);
        if (!path.extname(resolved)) resolved += '.js';
        return load(resolved);
      }
      return require(id);
    }
    // eslint-disable-next-line no-new-func
    new Function('require', 'module', 'exports', code)(localRequire, module, module.exports);
    return module.exports;
  }
  return load;
};
