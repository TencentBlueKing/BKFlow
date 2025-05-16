const { merge } = require('webpack-merge');
const webpackBase = require('./webpack.base.conf');
const TerserJSPlugin = require('terser-webpack-plugin');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const OptimizeCSSAssetsPlugin = require('optimize-css-assets-webpack-plugin');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const { CleanWebpackPlugin } = require('clean-webpack-plugin');
const path = require('path');
const CopyPlugin = require('copy-webpack-plugin');
// const BundleAnalyzerPlugin = require('webpack-bundle-analyzer').BundleAnalyzerPlugin

module.exports = merge(webpackBase, {
  // 模式
  mode: 'production',
  // 开发工具
  devtool: 'source-map',
  // 输出
  output: {
    filename: 'js/[name].[contenthash:10].js',
    publicPath: '{{BK_STATIC_URL}}',
  },
  // 模块
  module: {
    rules: [
      {
        test: /\.s?[ac]ss$/,
        exclude: /node_modules/,
        use: [
          {
            loader: MiniCssExtractPlugin.loader,
            options: {
              publicPath: '../'
            }
          },
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
          {
            loader: MiniCssExtractPlugin.loader,
            options: {
              publicPath: '../'
            }
          },
          'css-loader'
        ]
      },
    ],
  },
  // 插件
  plugins: [
    new MiniCssExtractPlugin({
      filename: 'css/[name].[contenthash:10].css',
    }),
    new HtmlWebpackPlugin({
      filename: 'index-prod.html',
      template: 'index.html',
      inject: true,
    }),
    new CleanWebpackPlugin({
      cleanOnceBeforeBuildPatterns: ['./assets/**'],
      verbose: true,
    }),
    new CopyPlugin([
      {
        from: path.resolve(__dirname, '../login_success.html'),
        to: path.resolve(__dirname, '../static/'),
      },
    ]),
  ],
  // 优化
  optimization: {
    minimizer: [
      new TerserJSPlugin({
        parallel: true,
        extractComments: false,
      }),
      new OptimizeCSSAssetsPlugin({
        cssProcessorOptions: {
          // map: {  // css 文件 sourcemap
          //     inline: false,
          //     annotation: true
          // },
          safe: true,
        },
      }),
    ],
    runtimeChunk: 'single',
    splitChunks: {
      cacheGroups: {
        vueLib: {
          test: /[\\/]node_modules[\\/](vue|vue-router|vuex)[\\/]/,
          name: 'vue-lib',
          chunks: 'initial',
        },
        plotly: {
          test: /[\\/]node_modules[\\/]plotly.js[\\/]/,
          name: 'plotly',
          chunks: 'initial',
        },
        highlight: {
          test: /[\\/]node_modules[\\/]highlight.js[\\/]/,
          name: 'highlight',
          chunks: 'all',
        },
        brace: {
          test: /[\\/]node_modules[\\/]brace[\\/]/,
          name: 'brace',
          chunks: 'initial',
        },
      },
    },
  },
  stats: {
    children: false,
    entrypoints: false,
  },
});
