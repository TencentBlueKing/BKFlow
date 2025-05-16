const fs = require('fs');
const path = require('path');
const webpack = require('webpack');
const { merge } = require('webpack-merge');
const webpackBase = require('./webpack.base.conf');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const dotenv = require('dotenv');

// 读取 .env 文件内容
const envPath = path.resolve(__dirname, '../.env.local');
const env = fs.existsSync(envPath)
  ? dotenv.parse(fs.readFileSync(envPath))
  : {};

const SITE_URL = '/';
// 代理接口列表
const proxyPath = [
  'api',
  'static',
  'jsi18n',
  'core/api',
  'config/api',
  'apigw',
  'common_template/api',
  'task',
  'taskflow/api',
  'pipeline',
  'analysis',
  'admin',
  'develop/api',
  'version_log',
  'iam',
  'plugin_service',
  'mako_operations',
  'collection',
  'get_msg_types',
  'is_admin_user',
  'task_system_superuser',
  'notice',
  'is_current_space_admin'
];
const context = proxyPath.map(item => SITE_URL + item);

module.exports = merge(webpackBase, {
  // 模式
  mode: 'development',
  // 模块
  module: {
    rules: [
      {
        test: /\.s?[ac]ss$/,
        exclude: /node_modules/,
        use: [
          'style-loader',
          'css-loader',
          'postcss-loader',
          {
            loader: 'sass-loader',
            options: {
              implementation: require('sass'), // 强制使用 Dart Sass
              sassOptions: {
                includePaths: [path.resolve(__dirname, '../src/')],
                indentedSyntax: false, // 如果使用 SCSS 语法需设为 false
                silenceDeprecations: ['import', 'legacy-js-api']
              }
            }
          }
        ]
      },
      {
        test: /\.css$/,
        include: /node_modules/,
        use: [
          'style-loader',
          {
            loader: 'css-loader',
            options: {
              importLoaders: 1 // 避免重复处理 @import
            }
          }
        ]
      },
    ],
  },
  // 插件
  plugins: [
    new webpack.HotModuleReplacementPlugin(),
    new HtmlWebpackPlugin({
      filename: 'index.html',
      template: 'index-dev.html',
      inject: true,
    }),
  ],
  // 开发工具
  devtool: 'inline-cheap-module-source-map',
  // 代理服务配置
  devServer: {
    host: env.DEV_HOST,
    port: 9007,
    server: 'https',
    historyApiFallback: {
      rewrites: [
        { from: /^.*$/, to: '/index.html' },
      ],
    },
    proxy: [
      {
        context,
        target: env.API_URL,
        secure: false,
        changeOrigin: true,
        headers: {
          referer: env.API_URL,
        },
      },
    ],
    client: {
      overlay: true,
      progress: true,
    },
  },
});
