<template>
  <section
    class="info-section"
    data-test-id="taskExecute_form_excuteInfo">
    <h4 class="common-section-title">
      {{ $t('基础信息') }}
    </h4>
    <ul class="operation-table">
      <li v-if="isSubProcessNode || isTemSubflowNode">
        <span class="th">{{ $t('流程模板') }}</span>
        <span
          v-if="templateName"
          class="td">
          {{ templateName }}
          <i
            class="commonicon-icon common-icon-jump-link"
            @click="onSkipSubTemplate" />
        </span>
        <span
          v-else
          class="td">
          {{ '--' }}
        </span>
      </li>
      <template v-else>
        <li>
          <span class="th">{{ $t('标准插件') }}</span>
          <span class="td">{{ currentExecuteInfo.plugin_name || '--' }}</span>
        </li>
        <li>
          <span class="th">{{ $t('插件版本') }}</span>
          <span class="td">{{ currentExecuteInfo.plugin_version || '--' }}</span>
        </li>
      </template>
      <li>
        <span class="th">{{ $t('节点名称') }}</span>
        <span class="td">{{ templateConfig.name || '--' }}</span>
      </li>
      <li>
        <span class="th">{{ $t('步骤名称') }}</span>
        <span class="td">{{ templateConfig.stage_name || '--' }}</span>
      </li>
      <li>
        <span class="th">{{ $t('是否可选') }}</span>
        <span class="td">{{ templateConfig.optional ? $t('是') : $t('否') }}</span>
      </li>
      <li>
        <span class="th">{{ $t('失败处理') }}</span>
        <span
          v-if="isAutoOperate"
          class="error-handle-td td">
          <template v-if="templateConfig.error_ignorable">
            <span class="error-handle-icon"><span class="text">AS</span></span>
            {{ $t('自动跳过') }};
          </template>
          <template v-if="templateConfig.skippable">
            <span class="error-handle-icon"><span class="text">MS</span></span>
            {{ $t('手动跳过') }};
          </template>
          <template v-if="templateConfig.retryable">
            <span class="error-handle-icon"><span class="text">MR</span></span>
            {{ $t('手动重试') }};
          </template>
          <template v-if="templateConfig.auto_retry && templateConfig.auto_retry.enable">
            <span class="error-handle-icon"><span class="text">AR</span></span>
            {{ $t('在 ') + $tc('秒', templateConfig.auto_retry.interval, { n: templateConfig.auto_retry.interval }) + $t('后') + $t('，') }}
            {{ $t('自动重试') + ' ' + templateConfig.auto_retry.times + ' ' + $t('次') }}
          </template>
        </span>
        <span
          v-else
          class="td">{{ '--' }}</span>
      </li>

      <li v-if="isSubProcessNode || isTemSubflowNode">
        <span class="th">{{ $t('总是使用最新版本') }}</span>
        <span class="td">
          {{ !('always_use_latest' in componentValue) ? '--' : componentValue.always_use_latest ? $t('是') : $t('否') }}
        </span>
      </li>
    </ul>
    <!-- v-if="inputAndOutputWrapShow" -->
    <template>
      <h4 class="common-section-title">
        {{ $t('输入参数') }}
      </h4>
      <div
        v-bkloading="{ isLoading: inputLoading, zIndex: 100 }"
        class="input-wrap">
        <template v-if="!inputLoading">
          <SpecialPluginInputForm
            v-if="isSpecialPlugin"
            :value="inputsFormData"
            :code="pluginCode"
            :is-view-mode="true"
            :space-id="spaceId"
            :template-id="templateId"
            :variable-list="variableList"
            @updateOutputs="updateOutputs" />
          <template v-else-if="Array.isArray(inputs)">
            <render-form
              v-if="inputs.length > 0"
              ref="renderForm"
              :scheme="inputs"
              :hooked="hooked"
              :constants="isSubProcessNode || isTemSubflowNode ? subflowForms : constants"
              :form-option="option"
              :form-data="inputsFormData"
              :render-config="inputsRenderConfig" />
            <no-data
              v-else
              :message="$t('暂无参数')" />
          </template>
          <template v-else>
            <jsonschema-input-params
              v-if="inputs.properties && Object.keys(inputs.properties).length > 0"
              :schema="inputs"
              :is-view-mode="true"
              :is-api-plugin="isApiPlugin"
              :form-data="inputsFormData" />
            <no-data
              v-else
              :message="$t('暂无参数')" />
          </template>
        </template>
      </div>
      <h4 class="common-section-title">
        {{ $t('输出参数') }}
      </h4>
      <div
        v-bkloading="{ isLoading: outputLoading, zIndex: 100 }"
        class="outputs-wrapper">
        <bk-table
          v-if="outputs.length"
          :data="outputList"
          :col-border="false"
          :row-class-name="getRowClassName">
          <bk-table-column
            :label="$t('名称')"
            :width="180"
            prop="name">
            <p
              slot-scope="props"
              v-bk-tooltips="props.row.description"
              class="output-name">
              {{ props.row.name }}
            </p>
          </bk-table-column>
          <bk-table-column
            label="KEY"
            class-name="param-key">
            <div
              slot-scope="props"
              class="output-key">
              <div
                v-bk-overflow-tips
                class="key">
                {{ props.row.key }}
              </div>
              <div
                v-if="props.row.hooked"
                class="hooked-input">
                {{ props.row.varKey }}
              </div>
              <span class="hook-icon-wrap">
                <i
                  v-bk-tooltips="{
                    content: props.row.hooked ? $t('取消变量引用') : $t('设置为变量'),
                    placement: 'bottom',
                    zIndex: 3000
                  }"
                  :class="['common-icon-variable-hook hook-icon', {
                    actived: props.row.hooked,
                    disabled: true
                  }]" />
              </span>
            </div>
          </bk-table-column>
        </bk-table>
        <no-data
          v-else
          :message="$t('暂无参数')" />
      </div>
    </template>
  </section>
</template>

<script>
  import i18n from '@/config/i18n/index.js';
  import { mapState, mapActions } from 'vuex';
  import tools from '@/utils/tools.js';
  import atomFilter from '@/utils/atomFilter.js';
  import RenderForm from '@/components/common/RenderForm/RenderForm.vue';
  import JsonschemaInputParams from '@/views/template/TemplateEdit/NodeConfig/JsonschemaInputParams.vue';
  import NoData from '@/components/common/base/NoData.vue';
  import jsonFormSchema from '@/utils/jsonFormSchema.js';
  import SpecialPluginInputForm from '@/components/SpecialPluginInputForm/index.vue';

  export default {
    components: {
      RenderForm,
      JsonschemaInputParams,
      NoData,
      SpecialPluginInputForm,
    },
    props: {
      nodeActivity: {
        type: Object,
        default: () => ({}),
      },
      executeInfo: {
        type: Object,
        default: () => ({}),
      },
      constants: {
        type: Object,
        default: () => ({}),
      },
      nodeDetailConfig: {
        type: Object,
        default: () => ({}),
      },
      isThirdPartyNode: {
        type: Boolean,
        default: false,
      },
      thirdPartyNodeCode: {
        type: String,
        default: '',
      },
      // isSubProcessNode: {
      //   type: Boolean,
      //   default: false,
      // },
      spaceId: {
        type: Number,
        default: 0,
      },
      scopeInfo: { // api插件请求参数
        type: Object,
        default: () => ({}),
      },
      pluginCode: {
        type: String,
        default: '',
      },
      templateId: {
        type: [Number, String],
        default: '',
      },
      taskId: {
        type: String,
        default: '',
      },
    },
    data() {
      return {
        templateName: '',
        templateConfig: {},
        inputs: [],
        outputs: [],
        hooked: {},
        option: {
          showGroup: false,
          showHook: true,
          showLabel: true,
          showVarList: true,
          formEdit: false,
        },
        inputsFormData: {},
        inputsRenderConfig: {},
        subflowForms: {},
        taskNodeLoading: false,
        subflowLoading: false,
        constantsLoading: false,
        isTemSubflowNode: false,
        currentExecuteInfo: tools.deepClone(this.executeInfo),
        currentNodeDetailConfig: tools.deepClone(this.nodeDetailConfig),
      };
    },
    computed: {
      ...mapState('project', {
        project_id: state => state.project_id,
        projectName: state => state.projectName,
      }),
      ...mapState({
        pluginConfigs: state => state.atomForm.config,
        pluginOutput: state => state.atomForm.output,
        atomFormInfo: state => state.atomForm.form,
      }),
      componentValue() {
        if (this.nodeActivity?.component?.data?.subprocess) {
          return this.nodeActivity.component.data.subprocess.value;
        } if (this.isTemSubflowNode) {
          const { always_use_latest, template_id, template_source } = this.nodeActivity;
          return {
            always_use_latest,
            template_id,
            template_source,
          };
        }
        return {};
      },
      inputLoading() {
        return this.taskNodeLoading || this.subflowLoading || this.constantsLoading;
      },
      outputLoading() {
        return this.taskNodeLoading || this.subflowLoading;
      },
      outputList() {
        return this.getOutputsList();
      },
      // inputAndOutputWrapShow() {
      //   const { original_template_id: originTplId } = this.nodeActivity;
      //   // 普通任务节点展示/该功能上线后的独立子流程任务展示
      //   return originTplId && !this.templateConfig.isOldData;
      // },
      isSubProcessNode() {
        return this.nodeActivity?.component?.code === 'subprocess_plugin' || this.nodeActivity.type === 'SubProcess';
      },
      isAutoOperate() {
        const { ignorable, skippable, retryable, auto_retry: autoRetry } = this.templateConfig;
        return ignorable || skippable || retryable || (autoRetry && autoRetry.enable);
      },
      isApiPlugin() {
        return this.pluginCode === 'uniform_api';
      },
      // 特殊输入参数插件
      isSpecialPlugin() {
        return ['dmn_plugin', 'value_assign'].includes(this.pluginCode);
      },
      variableList() {
        const constants = this.isSubProcessNode ? this.subflowForms : this.constants;
        return [...Object.values(constants)];
      },
    },
    watch: {
      nodeDetailConfig: {
        handler(val, oldVal) {
          if (!tools.isDataEqual(val, oldVal)) {
            this.currentNodeDetailConfig = tools.deepClone(val);
            this.getThirdpluginNameAndVersion();
          }
        },
        deep: true,
        immediate: true,
      },
    },
    mounted() {
      $.context.exec_env = 'NODE_EXEC_DETAIL';
      this.initData();
      if (this.nodeActivity?.component?.data?.subprocess) {
        this.getTemplateData();
      } else if (this.nodeActivity.type === 'SubProcess') {
        this.isTemSubflowNode = true;
        this.getTemplateData();
      }
    },
    beforeDestroy() {
      $.context.exec_env = '';
    },
    methods: {
      ...mapActions('template/', [
        'getTemplatePublicData',
        'getCommonTemplatePublicData',
        'loadUniformApiMeta',
        'loadTemplateData',
      ]),
      ...mapActions('task', [
        'loadSubflowConfig',
        'getNodeSnapshotConfig',
      ]),
      ...mapActions('atomForm/', [
        'loadAtomConfig',
        'loadPluginServiceDetail',
        'loadPluginServiceAppDetail',
      ]),
      // 初始化节点数据
      async initData() {
        try {
          // 获取对应模板配置
          let tplConfig = {};
          if (this.nodeActivity.template_node_id) {
            tplConfig = await this.getNodeSnapshotConfig(this.currentNodeDetailConfig);
          }
          this.templateConfig = tplConfig.data || { ...this.nodeActivity, isOldData: true } || {};
          // if (this.nodeActivity.type === 'SubProcess') return;
          if (this.isSubProcessNode) { // 子流程任务节点
            // tplConfig.data为null为该功能之前的旧数据，没有original_template_id字段的，不调接口
            // if (!tplConfig.data || !this.nodeActivity.original_template_id) {
            //   return;
            // }
            const forms = {};
            const renderConfig = {};
            const constants = this.templateConfig.constants || {};
            Object.keys(constants).forEach((key) => {
              const form = constants[key];
              if (form.show_type === 'show') {
                forms[key] = form;
                renderConfig[key] = 'need_render' in form ? form.need_render : true;
              }
            });
            // 加载子流程详情
            await this.getSubflowDetail(this.templateConfig.version);
            this.inputs = await this.getSubflowInputsConfig();
            this.inputsFormData = this.getSubflowInputsValue(forms);
            this.inputsRenderConfig = renderConfig;
          } else { // 普通任务节点
            const { component } = this.nodeActivity;
            const paramsVal = {};
            const renderConfig = {};
            Object.keys(component.data || {}).forEach((key) => {
              const val = tools.deepClone(component.data[key].value);
              paramsVal[key] = val;
              renderConfig[key] = 'need_render' in component.data[key] ? component.data[key].need_render : true;
            });
            this.inputsFormData = paramsVal;
            this.inputsRenderConfig = renderConfig;
            await this.getPluginDetail();
          }
          // 获取输入参数的勾选状态
          this.hooked = !this.isApiPlugin && this.getFormsHookState();
        } catch (error) {
          console.warn(error);
        }
      },
      // 获取第三方插件版本和名称
      async getThirdpluginNameAndVersion() {
        const { component_code: componentCode, version, componentData } = this.currentNodeDetailConfig;
        if (this.isThirdPartyNode) {
          const resp = await this.loadPluginServiceAppDetail({ plugin_code: this.thirdPartyNodeCode });
          this.currentExecuteInfo.plugin_name = resp.data.name;
          this.currentExecuteInfo.plugin_version = componentData.plugin_version.value;
        } else if (atomFilter.isConfigExists(componentCode, version, this.atomFormInfo)) {
          const pluginInfo = this.atomFormInfo[componentCode][version];
          this.currentExecuteInfo.plugin_name = `${pluginInfo.group_name}-${pluginInfo.name}`;
          this.currentExecuteInfo.plugin_version = version;
        }
      },
      // 获取输入参数勾选状态
      getFormsHookState() {
        const hooked = {};
        const keys = Object.keys(this.constants);
        Array.isArray(this.inputs) && this.inputs.forEach((form) => {
          // 已勾选到全局变量中, 判断勾选的输入参数生成的变量及自定义全局变量source_info是否包含该节点对应表单tag_code
          // 可能存在表单勾选时已存在相同key的变量，选择复用自定义变量
          const isHooked = keys.some((item) => {
            let result = false;
            const varItem = this.constants[item];
            if (['component_inputs', 'custom'].includes(varItem.source_type)) {
              const sourceInfo = varItem.source_info[this.nodeActivity.id];
              if (sourceInfo && sourceInfo.includes(form.tag_code)) {
                result = true;
              }
            }
            return result;
          });
          hooked[form.tag_code] = isHooked;
        });
        return hooked;
      },
      /**
       * 加载子流程任务节点输入、输出、版本配置项
       */
      async getSubflowDetail(version = '') {
        this.subflowLoading = true;
        try {
          const params = {
            templateId: this.componentValue.template_id,
            is_all_nodes: true,
            version,
          };
          params.project_id = this.project_id;
          const resp = await this.loadSubflowConfig(params);
          // 子流程的输入参数包括流程引用的变量、自定义变量和未被引用的变量
          this.subflowForms = {
            ...resp.data.pipeline_tree.constants,
            ...resp.data.custom_constants,
            ...resp.data.constants_not_referred,
          };
          // 输出变量
          this.outputs = Object.keys(resp.data.outputs).map((item) => {
            const output = resp.data.outputs[item];
            const has = Object.prototype.hasOwnProperty;
            return {
              plugin_code: output.plugin_code,
              name: output.name,
              key: output.key,
              version: has.call(output, 'version') ? output.version : 'legacy',
            };
          });
        } catch (e) {
          console.log(e);
        } finally {
          this.subflowLoading = false;
        }
      },

      /**
       * 加载子流程输入参数表单配置项
       * 遍历每个非隐藏的全局变量，由 source_tag、coustom_type 字段确定需要加载的标准插件
       * 同时根据 source_tag 信息获取全局变量对应标准插件的某一个表单配置项
       *
       * @return {Array} 每个非隐藏全局变量对应表单配置项组成的数组
       */
      async getSubflowInputsConfig() {
        this.constantsLoading = true;
        const inputs = [];
        const variables = Object.keys(this.subflowForms)
          .map(key => this.subflowForms[key])
          .filter(item => item.show_type === 'show')
          .sort((a, b) => a.index - b.index);

        await Promise.all(variables.map(async (item) => {
          const variable = { ...item };
          const { key } = variable;
          const { name, atom, tagCode, classify } = atomFilter.getVariableArgs(variable);
          const version = variable.version || 'legacy';
          const isThird = Boolean(variable.plugin_code);
          const atomConfig = await this.getAtomConfig({ plugin: atom, version, classify, name, isThird });
          let formItemConfig = tools.deepClone(atomFilter.formFilter(tagCode, atomConfig));
          if (variable.is_meta || formItemConfig.meta_transform) {
            formItemConfig = formItemConfig.meta_transform(variable.meta || variable);
            if (!variable.meta) {
              variable.meta = tools.deepClone(variable);
              variable.value = formItemConfig.attrs.value;
            }
          }
          // 特殊处理逻辑，针对子流程节点，如果为自定义类型的下拉框变量，默认开始支持用户创建不存在的选项配置项
          if (variable.custom_type === 'select') {
            formItemConfig.attrs.allowCreate = true;
          }
          formItemConfig.tag_code = key;
          formItemConfig.attrs.name = variable.name;
          // 自定义输入框变量正则校验添加到插件配置项
          if (['input', 'textarea'].includes(variable.custom_type) && variable.validation !== '') {
            formItemConfig.attrs.validation.push({
              type: 'regex',
              args: variable.validation,
              error_message: i18n.t('默认值不符合正则规则：') + variable.validation,
            });
          }
          // 参数填写时为保证每个表单 tag_code 唯一，原表单 tag_code 会被替换为变量 key，导致事件监听不生效
          const has = Object.prototype.hasOwnProperty;
          if (has.call(formItemConfig, 'events')) {
            formItemConfig.events.forEach((e) => {
              if (e.source === tagCode) {
                e.source = `\${${e.source}}`;
              }
            });
          }
          inputs.push(formItemConfig);
        }));
        this.constantsLoading = false;
        return inputs;
      },
      setFormsSchema(inputs) {
        const keys = Object.keys(this.constants);
        const { properties } = inputs;
        Object.keys(properties).forEach((form) => {
          // 已勾选到全局变量中, 判断勾选的输入参数生成的变量及自定义全局变量source_info是否包含该节点对应表单tag_code
          // 可能存在表单勾选时已存在相同key的变量，选择复用自定义变量
          keys.some((item) => {
            let result = false;
            const varItem = this.constants[item];
            if (['component_inputs', 'custom'].includes(varItem.source_type)) {
              const sourceInfo = varItem.source_info[this.nodeActivity.id];
              if (sourceInfo && sourceInfo.includes(form)) {
                const schema = properties[form];
                this.inputsFormData[form] = `\${${form}}`;
                inputs.properties[form] = {
                  extend: {
                    can_hook: true,
                    hook: true,
                  },
                  title: schema.title,
                  type: 'string',
                  'ui:component': {
                    name: 'bfInput',
                    props: {
                      disabled: true,
                    },
                  },
                };
                result = true;
              }
            }
            return result;
          });
        });
      },
      /**
       * 加载标准插件表单配置项文件
       */
      async getAtomConfig(config) {
        const { plugin, version, classify, name, isThird } = config;
        try {
          // 先取标准节点缓存的数据
          const pluginGroup = this.pluginConfigs[plugin];
          if (pluginGroup && pluginGroup[version]) {
            return pluginGroup[version];
          }
          // api插件输入输出
          if (this.isApiPlugin) {
            const { api_meta: apiMeta } = this.nodeActivity.component || {};
            if (!apiMeta) return;
            // api插件配置
            const resp = await this.loadUniformApiMeta({
              taskId: this.taskId,
              templateId: this.templateId,
              spaceId: this.spaceId,
              meta_url: apiMeta.meta_url,
              ...this.scopeInfo,
            });
            if (!resp.result) return;
            // 输出参数
            const storeOutputs = this.pluginOutput.uniform_api[version];
            const outputs = resp.data.outputs || [];
            this.outputs = [...storeOutputs, ...outputs];
            const renderConfig = jsonFormSchema(resp.data, { disabled: true });
            this.setFormsSchema(renderConfig);
            return renderConfig;
          }
          // 第三方插件
          if (isThird) {
            await this.getThirdConfig(plugin, version);
          } else {
            await this.loadAtomConfig({ atom: plugin, version, classify, name, space_id: this.spaceId });
            this.outputs = this.pluginOutput[plugin][version];
          }
          const config = $.atoms[plugin];
          return config;
        } catch (e) {
          console.log(e);
        }
      },
      // 第三方插件输入输出配置
      async getThirdConfig(plugin, version) {
        try {
          const resp = await this.loadPluginServiceDetail({
            plugin_code: plugin,
            plugin_version: version,
            with_app_detail: true,
          });
          if (!resp.result) return;
          // 获取参数
          const { outputs: respOutputs, forms, inputs } = resp.data;
          // 获取host
          const { origin } = window.location;
          const hostUrl = `${origin + window.SITE_URL}plugin_service/data_api/${plugin}/`;
          $.context.bk_plugin_api_host[plugin] = hostUrl;
          if (forms.renderform) {
            // 输入参数
            $.atoms[plugin] = {};
            const renderFrom = forms.renderform;
            /* eslint-disable-next-line */
            eval(renderFrom)
          } else {
            $.atoms[plugin] = inputs;
          }

          // 输出参数
          const outputs = [];
          // 获取第三方插件公共输出参数
          if (!this.pluginOutput.remote_plugin) {
            await this.loadAtomConfig({ atom: 'remote_plugin', version: '1.0.0', space_id: this.spaceId });
          }
          const storeOutputs = this.pluginOutput.remote_plugin['1.0.0'];
          for (const [key, val] of Object.entries(respOutputs.properties)) {
            outputs.push({
              name: val.title || key,
              key,
              type: val.type,
              schema: { description: val.description },
            });
          }
          this.outputs = [...storeOutputs, ...outputs];
        } catch (error) {
            console.warn(error);
        }
      },
      /**
       * 获取子流程任务节点输入参数值
       */
      getSubflowInputsValue(forms, oldForms = {}) {
        return Object.keys(forms).reduce((acc, cur) => { // 遍历新表单项
          const variable = forms[cur];
          if (variable.show_type === 'show') {
            let canReuse = false;
            const oldVariable = oldForms[cur];
            const isHooked = this.isInputParamsInConstants(variable);
            if (oldVariable && !isHooked) { // 旧版本中存在相同key的表单项，且不是勾选状态
              if (variable.custom_type || oldVariable.custom_type) {
                canReuse = variable.custom_type === oldVariable.custom_type;
              } else {
                canReuse = variable.source_tag === oldVariable.source_tag;
              }
            }
            const val = canReuse ? this.inputsParamValue[cur] : variable.value;
            acc[variable.key] = tools.deepClone(val);
          }

          return acc;
        }, {});
      },
      // 输入参数是否已被勾选到全局变量
      isInputParamsInConstants(form) {
        return Object.keys(this.constants).some((key) => {
          const varItem = this.constants[key];
          const sourceInfo = varItem.source_info[this.nodeActivity.id];
          return sourceInfo && sourceInfo.includes(form.tag_code);
        });
      },
      /**
       * 加载标准插件节点输入参数表单配置项，获取输出参数列表
       */
      async getPluginDetail() {
        this.taskNodeLoading = true;
        try {
          // 获取输入输出参数
          let { component_code: plugin, version } = this.currentNodeDetailConfig;
          if (this.isThirdPartyNode) {
            const { componentData } = this.currentNodeDetailConfig;
            plugin = componentData.plugin_code.value;
            version = componentData.plugin_version.value;
          }
          this.inputs = await this.getAtomConfig({ plugin, version, isThird: this.isThirdPartyNode }) || [];
          if (!this.isThirdPartyNode) {
            this.outputs = this.pluginOutput[plugin][version];
          }
        } catch (e) {
          console.log(e);
        } finally {
          this.taskNodeLoading = false;
        }
      },
      // 获取输出变量列表
      getOutputsList() {
        const list = [];
        const varKeys = Object.keys(this.constants);
        this.outputs.forEach((param) => {
          let { key: varKey } = param;
          const isHooked = varKeys.some((item) => {
            let result = false;
            const varItem = this.constants[item];
            if (varItem.source_type === 'component_outputs') {
              const sourceInfo = varItem.source_info[this.nodeActivity.id];
              if (sourceInfo && sourceInfo.includes(param.key)) {
                varKey = item;
                result = true;
              }
            }
            return result;
          });
          list.push({
            key: param.key,
            varKey,
            name: param.name,
            description: param.schema ? param.schema.description : '--',
            version: param.version,
            status: param.status,
            hooked: isHooked,
          });
        });
        return list;
      },
      getRowClassName({ row }) {
        return row.status || '';
      },
      async getTemplateData() {
        const { template_id: templateId } = this.componentValue;
        const data = {
          templateId,
          common: false,
        };
        const templateData = await this.loadTemplateData(data);
        this.templateName = templateData.name;
      },
      onSkipSubTemplate() {
        const { href } = this.$router.resolve({
          name: 'templatePanel',
          params: {
            templateId: this.componentValue.template_id,
            type: 'view',
          },
        });
        window.open(href, '_blank');
      },
      updateOutputs(outputs) {
        this.outputs = this.outputs.filter(item => !item.fromDmn);
        this.outputs.push(...outputs);
      },
    },
  };
</script>

<style lang="scss" scoped>
    .operation-table {
        font-size: 12px;
        border: 1px solid #dcdee5 !important;
        border-bottom: none !important;
        margin-bottom: 32px;
        li {
            display: flex;
            height: 42px;
            line-height: 41px;
            color: #63656e;
            border-bottom: 1px solid #dcdee5;
            .th {
                width: 140px;
                font-weight: 400;
                color: #313238;
                padding-left: 12px;
                border-right: 1px solid #dcdee5;
                background: #fafbfd;
            }
            .td {
                flex: 1;
                position: relative;
                padding-left: 12px;
            }
        }
    }
    .error-handle-icon {
        display: inline-block;
        line-height: 12px;
        color: #ffffff;
        background: #979ba5;
        border-radius: 2px;
        .text {
            display: inline-block;
            font-size: 12px;
            transform: scale(0.8);
        }
    }
    .common-icon-jump-link {
        position: absolute;
        top: 15px;
        right: 10px;
        color: #3a84ff;
        cursor: pointer;
    }
    .input-wrap {
        margin-bottom: 32px;
    }
    .output-key {
      display: flex;
      align-items: center;
      padding-right: 50px;
      .key {
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
      }
      .hooked-input {
        flex: 1;
        height: 32px;
        min-width: 180px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 8px;
        margin-left: 15px;
        background: #fafbfd;
        border: 1px solid #dcdee5;
        border-radius: 2px;
      }
    }
    .output-name {
        display: inline-block;
        max-width: 100%;
        border-bottom: 1px dashed #979ba5;
        cursor: default;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
    }
    .hook-icon-wrap {
        position: absolute;
        right: 22px;
        top: 5px;
        display: inline-block;
        width: 32px;
        height: 32px;
        line-height: 32px;
        background: #f0f1f5;
        text-align: center;
        border-radius: 2px;
        .hook-icon {
            font-size: 16px;
            color: #979ba5;
            cursor: pointer;
            &.disabled {
                color: #c4c6cc;
                cursor: not-allowed;
            }
            &.actived {
                color: #3a84ff;
            }
        }
    }
    .no-data-wrapper {
        padding-top: 20px;
    }

</style>
