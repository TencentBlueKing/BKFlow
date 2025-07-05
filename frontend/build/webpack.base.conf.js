const path = require('path');
const webpack = require('webpack');
const VueLoaderPlugin = require('vue-loader/lib/plugin')
const CaseSensitivePathsPlugin = require('case-sensitive-paths-webpack-plugin');
const MonacoWebpackPlugin = require('monaco-editor-webpack-plugin');

const os = require('os');

module.exports = {
  entry: {
    app: './src/main.js',
  },
  output: {
    path: path.resolve(__dirname, '../static/'),
    filename: 'js/[name].js',
    publicPath: '/',
    pathinfo: false,
  },
  resolve: {
    extensions: ['*', '.js', '.vue', '.json'],
    alias: {
      vue: 'vue/dist/vue.esm.js',
      '@': path.resolve(__dirname, '../src/'),
      jquery: 'jquery/dist/jquery.min.js',
      $: 'jquery/dist/jquery.min.js',
    },
    fallback: {
      path: false,
      buffer: false,
    },
  },
  cache: true,
  module: {
    rules: [
      {
        test: require.resolve('jquery'),
        loader: 'expose-loader',
        options: {
          exposes: ['$', 'jQuery'],
        },
      },
      {
        test: /\.vue$/,
        use: [{
          loader: 'vue-loader',
          options: {
            extractCSS: true,
          },
        }],
        exclude: /node_modules/,
      },
      {
        test: require.resolve('vue'),
        use: [{
          loader: 'expose-loader',
          options: 'Vue',
        }],
      },
      {
        test: /\.js$/,
        loader: 'babel-loader',
        exclude: [
          path.join(__dirname, '../node_modules'),
        ],
      },
      {
        test: /\.(png|jpe?g|gif|svg)(\?.*)?$/,
        type: 'asset/resource',
        generator: {
          filename: path.posix.join('images/[name].[contenthash:10].[ext]'),
        },
      },
      {
        test: /\.(mp4|webm|ogg|mp3|wav|flac|aac)(\?.*)?$/,
        type: 'asset/resource',
        generator: {
          filename: path.posix.join('videos/[name].[contenthash:10].[ext]'),
        },
      },
      {
        test: /\.(woff2?|eot|ttf|otf)(\?.*)?$/,
        type: 'asset/resource',
        generator: {
          filename: path.posix.join('fonts/[name].[contenthash:10].[ext]'),
        },
      },
    ],
  },
  optimization: {
    moduleIds: 'named',
    splitChunks: {
      cacheGroups: {
        defaultVendors: { // 框架相关
          test: /(vue|vue-router|vuex|axios|vee-validate|axios|vuedraggable)/,
          name: 'vendors',
          chunks: 'initial',
          priority: 100,
        },
        'moment-timezone': {
          test: /moment-timezone/,
          name: 'moment-timezone',
          chunks: 'all',
          priority: 100,
        },
        'monaco-editor': {
          test: /monaco-editor/,
          name: 'monaco-editor',
          chunks: 'all',
          priority: 100,
        },
        'bk-magic-vue': {
          test: /bk-magic-vue\/dist\/bk-magic-vue\.min\.js/,
          name: 'bk-magic-vue',
          chunks: 'initial',
          priority: 100,
        },
        jquery: {
          test: /jquery/,
          name: 'jquery',
          chunks: 'all',
          priority: 100,
        },
      },
    },
    runtimeChunk: {},
  },
  plugins: [
    new VueLoaderPlugin(),
    new webpack.DefinePlugin({
      'process.env': {
        DEV_VAR: JSON.stringify(process.env.DEV_VAR),
      },
    }),
    new webpack.ProvidePlugin({
      $: 'jquery',
      jQuery: 'jquery',
      'window.jQuery': 'jquery',
    }),
    new MonacoWebpackPlugin({
      languages: ['javascript', 'json'],
    }),
    // 严格组件名大小写，避免linux系统上打包报错
    // https://github.com/chemzqm/keng/issues/4
    new CaseSensitivePathsPlugin({ debug: false }),
    // moment 优化，只提取本地包
    new webpack.ContextReplacementPlugin(/moment\/locale$/, /zh-cn/),
    // brace 优化，只提取需要的语法
    new webpack.ContextReplacementPlugin(/brace\/mode$/, /^\.\/(json|python|sh|text)$/),
    // brace 优化，只提取需要的 theme
    new webpack.ContextReplacementPlugin(/brace\/theme$/, /^\.\/(monokai)$/),
  ],
};
