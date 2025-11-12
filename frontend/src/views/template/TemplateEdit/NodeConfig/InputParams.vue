* Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
* Edition) available.
* Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
* Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
* http://opensource.org/licenses/MIT
* Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
* an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
* specific language governing permissions and limitations under the License.
*/
<template>
  <div class="input-params">
    <template v-if="!isJsonSchema && scheme.length > 0">
      <render-form
        ref="inputParamsForm"
        :scheme="formsScheme"
        :hooked="hooked"
        :constants="isSubflow ? subflowForms : constants"
        :form-option="option"
        :form-data="formData"
        :render-config="renderConfig"
        @change="onInputsValChange"
        @onRenderChange="$emit('renderConfigChange', arguments)"
        @onHookChange="onInputHookChange" />
      <bk-collapse
        v-if="formsNotReferredScheme.length > 0"
        :class="['not-referred-forms', { expand: notReferredExpand }]">
        <bk-collapse-item>
          {{ $t('查看未引用变量') }}
          <div
            slot="content"
            class="forms-wrapper"
            style="padding: 10px 64px 10px 0;">
            <render-form
              :scheme="formsNotReferredScheme"
              :form-option="{ showLabel: true, showHook: false, formEdit: false }"
              :form-data="formData" />
          </div>
        </bk-collapse-item>
      </bk-collapse>
    </template>
    <jsonschema-input-params
      v-else-if="scheme && scheme.properties && Object.keys(scheme.properties).length > 0"
      ref="inputParamsForm"
      :key="randomKey"
      :form-data="formData"
      :is-view-mode="isViewMode"
      :schema="formsScheme"
      :is-api-plugin="isApiPlugin"
      @onHookForm="onHookForm"
      @update="$emit('update', $event)" />
    <no-data
      v-else
      :message="$t('暂无参数')" />
    <reuse-var-dialog
      :is-show="isReuseDialogShow"
      :variables="reuseableVarList"
      :same-key-exist="isKeyExist"
      :new-var-key-name="newVarKeyName"
      @confirm="onConfirmReuseVar"
      @cancel="onCancelReuseVar" />
  </div>
</template>
<script>
  import tools from '@/utils/tools.js';
  import formSchema from '@/utils/formSchema.js';
  import RenderForm from '@/components/common/RenderForm/RenderForm.vue';
  import ReuseVarDialog from './ReuseVarDialog.vue';
  import JsonschemaInputParams from './JsonschemaInputParams.vue';
  import NoData from '@/components/common/base/NoData.vue';
  import { mapState, mapActions } from 'vuex';
  import { random4 } from '@/utils/uuid.js';

  const varKeyReg = /^\$\{(\w+)\}$/;

  export default {
    name: 'InputParams',
    components: {
      RenderForm,
      ReuseVarDialog,
      JsonschemaInputParams,
      NoData,
    },
    props: {
      scheme: {
        type: [Array, Object],
        default: () => ([]),
      },
      value: {
        type: Object,
        default: () => ({}),
      },
      renderConfig: { // 输入参数是否配置渲染豁免
        type: Object,
        default: () => ({}),
      },
      isSubflow: {
        type: Boolean,
        default: false,
      },
      subflowForms: {
        type: Object,
        default: () => ({}),
      }, // 子流程模板输入参数变量配置
      formsNotReferred: { // 子流程未引用的变量
        type: Object,
        default: () => ({}),
      },
      nodeId: {
        type: String,
        default: '',
      },
      constants: {
        type: Object,
        default: () => ({}),
      },
      isViewMode: Boolean,
      isApiPlugin: Boolean,
      basicInfo: {
        type: Object,
        default: () => ({}),
      },
      isThirdParty: {
        type: Boolean,
        default: false,
      },
      templateId: {
        type: [String, Number],
        default: '',
      },
    },
    data() {
      const defaultScheme = Array.isArray(this.scheme) ? [] : {};
      return {
        formData: tools.deepClone(this.value),
        hooked: {},
        hookingVarForm: '', // 正被勾选的表单项
        unhookingVarForm: '', // 正被取消勾选的表单项
        isKeyExist: false, // 勾选的表单生成的 key 是否在全局变量列表中存在
        newVarKeyName: { key: '', name: '' }, // 变量配置弹窗自动创建使用
        isReuseDialogShow: false,
        reuseableVarList: [],
        notReferredExpand: false, // 未引用变量是否展开
        option: {
          showGroup: false,
          showHook: true,
          showLabel: true,
          showVarList: true,
          formEdit: !this.isViewMode,
        },
        formsScheme: defaultScheme,
        formsNotReferredScheme: [],

        randomKey: null,
        hookFormSchema: {},
        hookFormData: {},
      };
    },
    computed: {
      ...mapState({
        spaceId: state => state.template.spaceId,
        scopeInfo: state => state.template.scopeInfo,
      }),
      isJsonSchema() { // 是否为jsonSchemaForm表单
        return !Array.isArray(this.scheme);
      },
    },
    watch: {
      value(val) {
        this.formData = tools.deepClone(val);
      },
      scheme: {
        handler() {
            this.formsScheme = this.getFormScheme();
            this.formsNotReferredScheme = this.getFormScheme('notReferred');
          },
        deep: true,
      },
    },
    mounted() {
      if (this.isJsonSchema) {
        this.setFormsSchema();
      } else {
        $.context.exec_env = 'NODE_CONFIG';
        this.hooked = this.getFormsHookState();
        this.formsScheme = this.getFormScheme();
        this.formsNotReferredScheme = this.getFormScheme('notReferred');
      }
    },
    beforeDestroy() {
      $.context.exec_env = '';
    },
    methods: {
      ...mapActions('template/', [
        'loadUniformApiMeta',
      ]),
      /*
        renderForm相关方法
      */
      getFormsHookState() {
        const hooked = {};
        const keys = Object.keys(this.constants);
        Array.isArray(this.scheme) && this.scheme.forEach((form) => {
          // 已勾选到全局变量中, 判断勾选的输入参数生成的变量及自定义全局变量source_info是否包含该节点对应表单tag_code
          // 可能存在表单勾选时已存在相同key的变量，选择复用自定义变量
          const isHooked = keys.some((item) => {
            let result = false;
            const varItem = this.constants[item];
            if (['component_inputs', 'custom'].includes(varItem.source_type)) {
              const sourceInfo = varItem.source_info[this.nodeId];
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
      getFormScheme(type = 'referred') {
        if (this.isSubflow && Object.keys(this.formsNotReferred).length > 0) {
          const has = Object.prototype.hasOwnProperty;
          return this.scheme.filter((item) => {
            const result = has.call(this.formsNotReferred, item.tag_code);
            return type === 'referred' ? !result : result;
          });
        }
        return type === 'referred' ? this.scheme : [];
      },

      /*
        jsonSchemaForm相关方法
      */
      setFormsSchema() {
        const keys = Object.keys(this.constants);
        const formSchema = tools.deepClone(this.scheme);
        const { properties = {} } = formSchema;
        Object.keys(properties).forEach((form) => {
          // 已勾选到全局变量中, 判断勾选的输入参数生成的变量及自定义全局变量source_info是否包含该节点对应表单tag_code
          // 可能存在表单勾选时已存在相同key的变量，选择复用自定义变量
          keys.some((item) => {
            let result = false;
            const varItem = this.constants[item];
            if (['component_inputs', 'custom'].includes(varItem.source_type)) {
              const sourceInfo = varItem.source_info[this.nodeId];
              if (sourceInfo && sourceInfo.includes(form)) {
                const schema = properties[form];
                this.hookFormData[form] = varItem.value;
                this.hookFormSchema[form] = { ...schema };
                this.formData[form] = `\${${form}}`;
                this.setHookFormItem(formSchema, { form, schema });
                result = true;
              }
            }
            return result;
          });
        });
        this.formsScheme = formSchema;
      },
      async onHookForm(path, schema) {
        if (this.isViewMode) return;
        if (schema.extend.hook) {
          // 取消勾选
          this.unhookForm(path);
          this.formData[path] = this.hookFormData[path];
          this.formsScheme.properties[path] = this.hookFormSchema[path];
        } else {
          // 勾选
          this.hookFormData[path] = tools.deepClone(this.formData[path]);
          this.hookFormSchema[path] = { ...schema };
          const result = await this.hookForm(path);
          if (!result) return;
          this.formData[path] = `\${${path}}`;
          this.setHookFormItem(this.formsScheme, { form: path, schema });
          this.$emit('update', tools.deepClone(this.formData));
        }
        this.randomKey = new Date().getTime();
      },
      setHookFormItem(formSchema, { form, schema }) {
        formSchema.properties[form] = {
          extend: {
            can_hook: true,
            hook: true,
          },
          title: schema.title,
          description: schema.description,
          type: 'string',
          'ui:component': {
            name: 'bfInput',
            props: {
              disabled: true,
            },
          },
        };
      },

      /*
        公共方法
      */
      onInputsValChange(val) {
        this.$emit('update', tools.deepClone(val));
      },
      onInputHookChange(form, val) {
        if (val) {
          this.hookForm(form);
        } else {
          this.unhookForm(form);
        }
      },
      /**
       * 输入参数勾选
       *
       * 勾选逻辑：
       * 1.判断是否存在类型相同的变量(表单项的tag_code是否相同)，存在则显示变量复用弹窗，
       * 提供“复用已有变量”、“手动创建变量”固定两种方式给用户选择，如果全局变量中不存在与被勾选变量相同key的变量，
       * 再提供第三种“自动创建变量”的选项，不存在则进行下一步判断
       * 2.判断是否存在相同key的变量，存在则提示用户手动新建变量，不存在则自动创建变量
       */
      async hookForm(form) {
        const reuseList = [];
        let variableKey; let formCode; let name;

        if (this.isSubflow) {
          const variable = this.subflowForms[form];
          variableKey = form;
          // eslint-disable-next-line
          formCode = variable.source_tag.split('.')[1]
        } else {
          variableKey = `\${${form}}`;
          formCode = form;
        }

        let isKeyInVariables = false;
        this.hookingVarForm = form;
        this.hooked[form] = true;

        if (this.isJsonSchema) {
          name = this.hookFormSchema[form].title;
        } else {
          const formConfig = this.scheme.find(item => item.tag_code === form);
          name = formConfig.attrs.name;
        }
        const config = this.getNewVarConfig(name, variableKey);

        Object.keys(this.constants).forEach((keyItem) => {
          const constant = this.constants[keyItem];
          const sourceTag = constant.source_tag;
          if (sourceTag) { // 判断 sourceTag 是否存在是为了兼容旧数据自定义全局变量 source_tag 为空
            const tagCode = sourceTag.split('.')[1];
            // 判断全局变量中是否有与被勾选表单项存在相同类型的，输入参数和输出参数不做比较
            if (tagCode === formCode && constant.source_type !== 'component_outputs') {
              reuseList.push({
                name: `${constant.name}(${constant.key})`,
                id: constant.key,
              });
            }
          }

          if (keyItem === variableKey) {
            isKeyInVariables = true;
          }
        });

        if (reuseList.length > 0) { // 存在类型相同的全局变量
          let isSame = true;
          if (this.isJsonSchema) {
            // 存在类型相同的全局变量(复用变量)
            const { metaUrl } = this.$parent.$parent.basicInfo;
            // api插件配置
            const resp = await this.loadUniformApiMeta({
              templateId: this.templateId,
              spaceId: this.spaceId,
              meta_url: metaUrl,
              ...this.scopeInfo,
            });
            if (!resp.result) return;
            const sourceSchema = resp.data.inputs.find(item => item.key === form);
            const crtSchema = this.$parent.$parent.apiInputs.find(item => item.key === form);
            isSame = tools.isDataEqual(sourceSchema, crtSchema);
          }
          if (isSame) {
            this.reuseableVarList = reuseList;
            this.isKeyExist = isKeyInVariables;
            this.isReuseDialogShow = true;
            this.newVarKeyName = {
              key: config.key,
              name: config.name,
            };
            return false;
          }
          config.key = `\${${form}_${random4()}}`;
        } else if (isKeyInVariables) { // 存在相同key的变量，手动创建新变量
          this.isKeyExist = true;
          this.isReuseDialogShow = true;
          this.reuseableVarList = [];
          this.newVarKeyName = {
            key: config.key,
            name: config.name,
          };
          return false;
        }
        // 自动创建新变量
        this.reuseableVarList = [];
        this.newVarKeyName = { key: '', name: '' };
        this.createVariable(config);
        return true;
      },
      /**
       * 取消勾选表单
       *
       * 去掉包含该表单的全局变量 source_info 对应的信息，若对应全局变量只包含这一个表单项，则删除全局变量
       * 取消勾选后全局变量的值需要同步当前表单项
       */
      unhookForm(form) {
        this.unhookingVarForm = form;
        const variableKey = this.formData[form];
        const constant = this.constants[variableKey];
        if (constant) { // 标准插件里(如：job_execute_task)可能会修改表单的勾选状态，需要做一个兼容处理
          const config = ({
            type: 'delete',
            id: this.nodeId,
            key: variableKey,
            tagCode: form,
            source: 'input',
          });
          this.$emit('hookChange', 'delete', config);
        }
      },
      // 变量勾选/取消勾选后，需重新对form进行赋值
      setFormData(data = {}) {
        const form = this.unhookingVarForm;
        this.formData[form] = tools.deepClone(data.value) || '';
        this.hooked[form] = false;
        this.$emit('update', tools.deepClone(this.formData));
      },
      getNewVarConfig(name, key) {
        const variableKey = varKeyReg.test(key) ? key : `\${${key}}`;
        const { plugin, version } = this.basicInfo;
        const pluginCode = this.isThirdParty ? plugin : '';
        const config = {
          name,
          key: variableKey,
          source_info: { [this.nodeId]: [this.hookingVarForm] },
          value: tools.deepClone(this.formData[this.hookingVarForm]) || '',
          form_schema: this.isJsonSchema ? {} : formSchema.getSchema(this.hookingVarForm, this.scheme),
          plugin_code: pluginCode,
        };
        if (this.isSubflow) {
          const constant = this.subflowForms[this.hookingVarForm];
          const { desc, custom_type, source_tag, validation, is_meta: isMeta, meta, version, plugin_code } = constant;
          Object.assign(config, {
            desc,
            custom_type,
            source_tag,
            validation,
            version,
            plugin_code,
          });
          if (isMeta) {
            config.is_meta = true;
            config.meta = tools.deepClone(meta);
          }
        } else {
          Object.assign(config, {
            custom_type: '',
            source_tag: `${plugin}.${this.hookingVarForm}`,
            version,
          });
          // jsonSchema表单
          if (this.isJsonSchema) {
            config.form_schema = {};
            config.plugin_code = '';
            config.version = 'v2.0.0';
          }
        }
        return config;
      },
      // 创建新变量
      createVariable(config = {}) {
        const len = Object.keys(this.constants).length;
        const defaultOpts = {
          name: '',
          key: '',
          desc: '',
          custom_type: '',
          source_info: {},
          source_tag: '',
          value: '',
          show_type: 'show',
          source_type: 'component_inputs',
          validation: '',
          index: len,
          version: 'legacy',
          form_schema: {},
          plugin_code: '',
        };
        // api插件json格式勾选需透传meta_desc、type、form_type、required
        if (this.isApiPlugin) {
          const form = config.source_tag.split('.')[1];
          const schema = this.formsScheme.properties[form];
          const extraInfo = {
            type: schema.type,
          };
          if (schema.metaDesc) {
            extraInfo.meta_desc = schema.metaDesc;
          }
          if (schema.formType) {
            extraInfo.form_type = schema.formType;
          }
          if (schema['ui:rules']) {
            extraInfo.required = true;
          }
          defaultOpts.extra_info = extraInfo;
        }
        const variable = Object.assign({}, defaultOpts, config);
        this.formData[this.hookingVarForm] = variable.key;
        this.$emit('hookChange', 'create', variable);
        this.$emit('update', tools.deepClone(this.formData));
        this.hookingVarForm = '';
      },
      /**
       * 复用变量弹窗点击确认回调
       *
       * @param {String} type 自动创建新变量(autoCreate)、复用已有全局变量(reuse)或者创建新变量(manualCreate)
       * @param {String, Obejct} data 复用时为 formcode，新建时为 {name, key}
       */
      onConfirmReuseVar(type, data) {
        this.isReuseDialogShow = false;
        const form = this.hookingVarForm;
        if (['autoCreate', 'manualCreate'].includes(type)) { // 创建新变量
          const { name, key } = data;
          const config = this.getNewVarConfig(name, key);
          this.createVariable(config);
        } else { // 复用已有全局变量
          const variableKey = data;
          const config = {
            type: 'add',
            id: this.nodeId,
            key: variableKey,
            tagCode: form,
          };
          this.formData[form] = variableKey;
          this.$emit('hookChange', 'reuse', config);
          this.$emit('update', tools.deepClone(this.formData));
          this.hookingVarForm = '';
        }
        // jsonSchema表单重置hook态
        if (this.isJsonSchema) {
          const schema = this.hookFormSchema[form];
          this.setHookFormItem(this.formsScheme, { form, schema });
          this.randomKey = new Date().getTime();
        }
      },
      /**
       * 取消复用变量回调
       */
      onCancelReuseVar() {
        this.hooked[this.hookingVarForm] = false;
        this.isReuseDialogShow = false;
        this.isKeyExist = false;
        this.hookingVarForm = '';
        this.reuseableVarList = [];
      },
      validate() {
        if (this.$refs.inputParamsForm) {
          return this.$refs.inputParamsForm.validate();
        }
        return true;
      },
    },
  };
</script>
<style lang="scss" scoped>
.not-referred-forms {
    margin-top: 20px;
    background: #f0f1f5;
    & ::v-deep .bk-collapse-item {
        .bk-collapse-item-header {
            color: #333333;
            &:hover {
                background: #e4e6ed;
            }
        }
    }
}
</style>
