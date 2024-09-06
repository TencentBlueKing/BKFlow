const webpack = require('webpack');
const { merge } = require('webpack-merge');
const webpackBase = require('./webpack.base.conf');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const SITE_URL = '/';
// 代理接口列表
const proxyPath = [
  'api',
  'api/v1',
  'static',
  'jsi18n',
  'api',
  'core/api',
  'config/api',
  'apigw',
  'common_template/api',
  'task/get_task_detail',
  'task/get_task_states',
  'task/operate_task',
  'task/get_task_node_detail',
  'task/operate_node',
  'task/render_current_constants',
  'task/get_task_node_log',
  'task/get_task_operation_record',
  'task_admin',
  'task/get_node_snapshot_config',
  'task_admin/get_tasks_states',
  'taskflow/api',
  'pipeline',
  'analysis',
  'admin/search',
  'admin/api',
  'admin/taskflow',
  'admin/template',
  'develop/api',
  'version_log',
  'iam',
  'plugin_service',
  'mako_operations',
  'collection',
  'get_msg_types',
  'is_admin_user',
  'task_system_superuser',
  'task/get_task_mock_data',
  'notice',
  'api/space',
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
        use: ['style-loader', 'css-loader', 'postcss-loader', 'sass-loader'],
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
    host: 'dev.{BK_PAAS_HOST}',
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
        target: 'https://{BK_PAAS_HOST}:8000',
        secure: false,
        changeOrigin: true,
        headers: {
          referer: 'https://{BK_PAAS_HOST}:8000',
        },
      },
    ],
    client: {
      overlay: true,
      progress: true,
    },
  },
});
