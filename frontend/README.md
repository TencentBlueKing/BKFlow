## bkflow 项目开发文档

本地开发之前，需要在项目根目录创建.env.local文件，并配置开发环境需要用到的环境变量，文件内容格式如下：
```
DEV_HOST=dev.xxx.com
API_URL=https://xxx.com
```

本地开发还需要将`index-dev.html`文件中的变量占位符，替换为开发环境对应的值。

### 安装依赖包
项目的开发环境要求 `Node.js` 版本至少为 18.20.4，安装依赖之前，需要检查 `Node.js`以及对应的 `npm` 版本是否符合。
``` shell
yarn install
```

### 配置本地的hosts
找到系统 hosts 文件的路径，以管理员权限编辑文件，将本地开发环境的域名配置到`127.0.0.1`。
```shell
# 找到 hosts 文件
 - windows 系统
 C:\Windows\System32\drivers\etc\hosts
 - macos 系统
 /etc/hosts

# 增加本地开发环境 host 配置，开发域名需要和 .env.local 文件中的 DEV_HOST 保持一致，例如：
127.0.0.1   dev.xxx.com
```

### webpack 代理配置
在本地开发环境调用后台接口时，通常会出现本地访问域名和后台接口的域名跨域的情况，浏览器的安全策略会对跨域接口的请求进行拦截。项目中利用了 webpack 的内置的 `devServer` 模块将后台接口请求进行代理，绕过浏览器的跨域拦截。如果开发过程中，发现调用的接口没有命中 webpack 代理，则需要修改项目中的`build/webpack.dev.config.js`文件，将接口路径添加到 `proxyPath` 变量中。
```
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
```

### 本地项目运行
```shell
npm run dev
```
构建完成后，在浏览器中通过开发域名+开发端口访问，例如`https://dev.xxx.com:9007`

### 项目目录结构说明

```
.
├── build
│   ├── webpack.base.conf.js # 项目共用的webpack配置
│   ├── webpack.dev.conf.js # 本地开发环境配置
│   └── webpack.prod.conf.js # 生产环境构建配置
├── favicon.ico
├── index-dev.html # 本地开发环境的html入口文件
├── index.html # 生产环境构建时html入口文件
├── login_success.html # 登录成功之后嵌入的html文件
├── package.json
├── postcss.config.js
├── README.md
├── src
│   ├── api # 项目中http请求的基础封装
│   ├── App.vue
│   ├── assets # 字体图标文件、图片、第三方js资源等
│   ├── components # 项目中通用的公共组件
│   ├── config
│   │   ├── i18n # 国际化相关配置
│   │   └── setting.js # 标准插件相关配置
│   ├── constants # 项目级别的全局变量
│   ├── css
│   ├── directives # 公共指令
│   ├── main.js # 应用的入口js文件
│   ├── mixins
│   ├── public-path.js # 用来设置 webpack public_path
│   ├── router # vue-router 的路由配置
│   ├── scss
│   ├── store # vuex状态管理，页面中绝大部分接口请求放到store的action中
│   ├── utils # 工具函数
│   └── views
│       ├── 404.vue
│       ├── admin # 管理员面板
│       ├── enginePanel # 引擎面板
│       ├── task # 任务模块
│       └── template # 流程模板模块
├── yarn.lock
├── .babelrc
├── .editorconfig
├── .env.local
├── .eslintignore
├── .eslintrc.js
├── .gitignore
└── .npmrc
```



