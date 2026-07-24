
import axios from 'axios';

export default {
  namespaced: true,
  state: {},
  mutations: {},
  actions: {
    // 检查空间配置
    checkSpaceConfig({}, data) {
      return axios.get(`/api/space/config/${data.id}/check_space_config/`, { params: data }).then(response => response.data);
    },
    // 无鉴权获取空间基本配置信息
    getNotAuthSpaceConfig({}) {
      return axios.get('/api/space/config/get_control_config/').then(response => response.data);
    },
    getSpaceConfigData({}, data) {
      return axios.get('api/space/admin/space_config/get_all_space_configs/', {
        params: {
          space_id: data.space_id,
        },
      }).then(response => response.data);
    },
    updateSpaceConfig({}, data) {
      let url = 'api/space/admin/space_config/';
      let method = 'post';
      if (data.id) {
        url = `${url}${data.id}/`;
        method = 'patch';
      }

      return axios[method](url, data).then(response => response.data);
    },
    deleteSpaceConfig({}, data) {
      return axios.delete(`api/space/admin/space_config/${data.id}/`).then(response => response.data);
    },
    getSpaceConfigMeta({}, data) {
      return axios.get('api/space/admin/space_config/config_meta/', {
        params: {
          space_id: data.space_id,
        },
      }).then((response) => {
        const mockData = {
          result: true,
          data: {
            token_expiration: {
              name: 'token_expiration',
              desc: 'Token过期时间',
              is_public: true,
              value_type: 'TEXT',
              default_value: '1h',
              choices: null,
              example: '[n]h or [n]d, h->hour d->day, at least 1h',
              is_mix_type: false,
              group: 'access_security',
              help: {
                summary: '访问 Token 的有效期',
                effect: 'Token 到该时间节点之后自动过期',
                media: [],
                doc_link: '',
              },
              ui: {
                control: 'input',
                label: '设置过期时间',
                help: '最短 1 小时，单位可选择小时/天',
                placeholder: '1h',
                validation: {
                  type: 'duration',
                  min: '1h',
                },
              },
              verifiable: false,
              input_model: null,
            },
            token_auto_renewal: {
              name: 'token_auto_renewal',
              desc: 'Token自动续期',
              is_public: true,
              value_type: 'TEXT',
              default_value: 'true',
              choices: [
                'true',
                'false',
              ],
              example: null,
              is_mix_type: false,
              group: 'access_security',
              help: {
                summary: 'Token 临近过期时是否自动续期',
                effect: 'Token 临近过期时自动延长有效期，减少调用中断',
                media: [],
                doc_link: '',
              },
              ui: {
                control: 'switch',
                label: '启用自动续期',
                true_value: 'true',
                false_value: 'false',
                help: '关闭后到期即失效，需重新获取',
              },
              verifiable: false,
              input_model: null,
            },
            allow_multiple_triggers: {
              name: 'allow_multiple_triggers',
              desc: '是否允许配置多个触发器',
              is_public: true,
              value_type: 'TEXT',
              default_value: 'false',
              choices: [
                'true',
                'false',
              ],
              example: null,
              is_mix_type: false,
              group: 'flow_canvas',
              help: {
                summary: '单个流程是否允许配置多个触发器',
                effect: '开启：一个流程可挂多个触发器（定时/事件）同时生效；关闭：仅允许一个',
                media: [],
                doc_link: '',
              },
              ui: {
                control: 'switch',
                label: '允许多触发器',
                true_value: 'true',
                false_value: 'false',
              },
              verifiable: false,
              input_model: null,
            },
            engine_space_config: {
              name: 'engine_space_config',
              desc: '引擎模块配置',
              is_public: true,
              value_type: 'REF',
              default_value: null,
              choices: null,
              example: {
                space: [
                  '{key1}',
                  '{value1}',
                ],
                scope: {
                  '{scope_type}_{scope_value}': {
                    '{key1}': '{value1}',
                  },
                },
              },
              is_mix_type: false,
              group: 'api_integration',
              help: {
                summary: '下发给引擎的运行参数（高级）',
                effect: 'space 为空间级键值，scope 为按作用域覆盖的键值；影响引擎运行行为，请谨慎修改',
                media: [],
                doc_link: '',
              },
              ui: {
                control: 'engine_kv',
                label: '引擎模块配置',
                help: '键值仅支持字符串/数字/布尔',
              },
              verifiable: false,
              input_model: null,
            },
            callback_hooks: {
              name: 'callback_hooks',
              desc: '回调配置',
              is_public: false,
              value_type: 'JSON',
              default_value: null,
              choices: null,
              example: {
                url: '{callback_url}',
                callback_types: [
                  'template',
                ],
              },
              is_mix_type: false,
              group: null,
              help: null,
              ui: null,
              verifiable: false,
              input_model: null,
            },
            uniform_api: {
              name: 'uniform_api',
              desc: 'API插件',
              is_public: true,
              value_type: 'JSON',
              default_value: null,
              choices: null,
              example: {
                api: {
                  '{api_key}': {
                    meta_apis: '{meta_apis url}',
                    api_categories: '{api_categories url}',
                    display_name: '{display_name}',
                    headers: {
                      'X-Custom-Header': '${_system.operator}',
                    },
                  },
                },
              },
              is_mix_type: false,
              group: 'api_integration',
              help: {
                summary: '接入统一 API 平台，把外部 API 暴露为可编排的 API 插件',
                effect: '管理API相关api_key的结构化接入与可视化解析；每个api_key一条接入信息',
                media: [],
                doc_link: '',
              },
              ui: {
                control: 'api_plugin_config',
                label: 'API 插件',
                help: '每个 api_key 配置 display_name / meta_apis(apigw URL) / api_categories(可选) / headers',
                validation: {
                  type: 'apigw_url',
                },
              },
              verifiable: true,
              input_model: {
                form_structure: '表单结构',
                json_source_code: 'JSON 源码',
              },
            },
            superusers: {
              name: 'superusers',
              desc: '空间管理员',
              is_public: true,
              value_type: 'JSON',
              default_value: null,
              choices: null,
              example: [
                'super_user1',
                'super_user2',
                'super_user3',
              ],
              is_mix_type: false,
              group: 'access_security',
              help: {
                summary: '空间的超级管理员',
                effect: '拥有本空间全部管理权限，加入后可管理配置、凭证与全部流程/任务',
                media: [],
                doc_link: '',
              },
              ui: {
                control: 'member_selector',
                label: '配置管理员',
                placeholder: '请选择成员',
              },
              verifiable: false,
              input_model: null,
            },
            canvas_mode: {
              name: 'canvas_mode',
              desc: '画布模式',
              is_public: true,
              value_type: 'TEXT',
              default_value: 'horizontal',
              choices: [
                'horizontal',
                'vertical',
              ],
              example: null,
              is_mix_type: false,
              group: 'flow_canvas',
              help: {
                summary: '流程画布的默认排布方向',
                effect: '控制流程画布中节点的默认排布方向',
                media: [
                  {
                    type: 'gif',
                    src: '',
                    caption: '横向 vs 纵向 排布示意',
                  },
                ],
                doc_link: '',
              },
              ui: {
                control: 'radio',
                label: '画布模式',
                help: '切换后新建流程画布按所选方向排布',
                options: [
                  {
                    value: 'horizontal',
                    label: '横向',
                    desc: '节点从左到右排布，适合较线性的流程',
                  },
                  {
                    value: 'vertical',
                    label: '纵向',
                    desc: '节点从上到下排布，适合分支多、层级清晰的流程',
                  },
                ],
              },
              verifiable: false,
              input_model: null,
            },
            gateway_expression: {
              name: 'gateway_expression',
              desc: '网关表达式',
              is_public: true,
              value_type: 'TEXT',
              default_value: 'boolrule',
              choices: [
                'boolrule',
                'FEEL',
                'MAKO',
              ],
              example: null,
              is_mix_type: false,
              group: 'flow_canvas',
              help: {
                summary: '分支网关条件使用的表达式语言',
                effect: '影响分支网关条件的书写与求值方式；修改仅影响此后新建/编辑的条件',
                media: [],
                doc_link: '',
              },
              ui: {
                control: 'radio',
                label: '表达式类型',
                options: [
                  {
                    value: 'boolrule',
                    label: 'Boolrule（默认）',
                    desc: '简单布尔规则，可视化友好，适合常规条件',
                  },
                  {
                    value: 'FEEL',
                    label: 'FEEL',
                    desc: 'DMN 标准表达式，功能强，适合复杂决策',
                  },
                  {
                    value: 'MAKO',
                    label: 'MAKO',
                    desc: 'Python 模板表达式，最灵活但需谨慎',
                  },
                ],
              },
              verifiable: false,
              input_model: null,
            },
            api_gateway_credential_name: {
              name: 'api_gateway_credential_name',
              desc: '网关凭证',
              is_public: true,
              value_type: 'TEXT',
              default_value: null,
              choices: null,
              example: {
                default: '{default_credential_name}',
                '{scope_type}_{scope_id}': '{credential_name}',
              },
              is_mix_type: true,
              group: 'access_security',
              help: {
                summary: '网关调用使用哪个凭证（引用凭证管理里的 BK_APP 凭证）',
                effect: '适用于 [凭证管理] 中的BK_APP 凭证访问统一API网关。本质是一张 [作用域] 到 [凭证] 的路由表。',
                media: [],
                doc_link: '',
              },
              ui: {
                control: 'credential_map',
                label: '网关凭证',
                help: '默认凭证必选；可按作用域（scope_type_scope_value）追加覆盖',
                data_source: {
                  type: 'credential',
                  credential_type: 'BK_APP',
                },
              },
              verifiable: false,
              input_model: null,
            },
            space_plugin_config: {
              name: 'space_plugin_config',
              desc: '空间插件配置',
              is_public: true,
              value_type: 'JSON',
              default_value: null,
              choices: null,
              example: {
                default: {
                  mode: '{allow_list/deny_list}',
                  plugin_codes: [
                    'plugin_1',
                    'plugin_2',
                  ],
                },
              },
              is_mix_type: false,
              group: 'api_integration',
              help: {
                summary: '控制本空间可用的插件范围',
                effect: 'allow_list 仅允许所列插件，deny_list 屏蔽所列插件；影响流程编辑时可选插件',
                media: [],
                doc_link: '',
              },
              ui: {
                control: 'plugin_scope',
                label: '空间插件',
                help: '选择模式并配置插件 code 列表',
              },
              verifiable: false,
              input_model: null,
            },
            flow_versioning: {
              name: 'flow_versioning',
              desc: '流程版本控制',
              is_public: true,
              value_type: 'TEXT',
              default_value: 'false',
              choices: [
                'true',
                'false',
              ],
              example: null,
              is_mix_type: false,
              group: 'flow_canvas',
              help: {
                summary: '是否开启流程版本管理',
                effect: '开启：流程保存产生版本、可回溯与回滚；关闭：仅保留最新版本',
                media: [],
                doc_link: '',
              },
              ui: {
                control: 'switch',
                label: '版本控制',
                true_value: 'true',
                false_value: 'false',
              },
              verifiable: false,
              input_model: null,
            },
          },
          code: '0',
          message: '',
        };
        console.log(response.data);
        return mockData;
      });
    },
    // 目前仅支持 uniform_api 配置项的校验配置项验证
    verifySpaceConfig({}, data) {
      return axios.post('api/space/admin/space_config/verify/', data).then(response => response.data);
    },
  },
};

