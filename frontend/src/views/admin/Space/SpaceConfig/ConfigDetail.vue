<template>
  <div
    v-if="config"
    class="config-detail">
    <div class="detail-header">
      <div class="detail-header-left">
        <div class="detail-title-wrap">
          <span class="detail-title">
            {{ config.desc }}
          </span>
          <div
            :class="[
              'detail-status',
              detailStatus === 'error' ? 'is-error' : detailStatus === 'default' ? 'is-default' : 'is-custom',
            ]">
            {{ detailStatus === 'error' ? $t('异常') : detailStatus === 'default' ? $t('默认') : $t('已配置') }}
          </div>
        </div>
        <!-- 帮助 -->
        <div
          v-if="config.help"
          class="detail-help">
          <p
            v-if="config.help.summary"
            class="help-summary">
            {{ config.help.summary }}
          </p>
          <p
            v-if="config.help.effect"
            class="help-effect">
            {{ config.help.effect }}
          </p>
        </div>
      </div>
      <div
        v-if="isCompositeControl"
        class="detail-header-right">
        <bk-radio-group
          v-model="currentMode"
          @change="toggleSourceMode">
          <bk-radio-button value="form_value">
            {{ $t('表单结构') }}
          </bk-radio-button>
          <bk-radio-button value="json_value">
            {{ $t('JSON源码') }}
          </bk-radio-button>
        </bk-radio-group>
      </div>
    </div>
    <!-- 画布模式示例图片 -->
    <div
      v-if="config.name === 'canvas_mode'"
      class="config-canvas-example">
      <div class="config-canvas-example-title">
        <span> {{ $t('效果演示') }}</span>
        <div
          v-if="config.help.doc_link"
          class="commonicon-icon common-icon-double-paper config-canvas-example-icon" />
        <bk-link
          v-if="config.help.doc_link"
          theme="primary"
          :href="config.help.doc_link"
          target="_blank">
          {{ $t('查看文档') }}
        </bk-link>
      </div>
      <div class="config-canvas-example-gif">
        <div
          v-for="(item, index) in config.help.media"
          :key="index"
          class="config-canvas-example-gif-wrap">
          <img
            :src="item.src || defaultCanvasImage">
          <div class="caption">
            {{ item.caption }}
          </div>
        </div>
      </div>
    </div>
    <div v-if="config.name === 'space_plugin_config'">
      <div
        v-if="currentGuide"
        class="detail-guide">
        <div
          v-if="currentGuide.purpose"
          class="guide-block">
          <div class="guide-title">
            {{ $t('用途') }}
          </div>
          <div class="guide-body">
            {{ currentGuide.purpose }}
          </div>
        </div>
        <div
          v-if="currentGuide.effects && currentGuide.effects.length"
          class="guide-block">
          <div class="guide-title">
            {{ $t('影响') }}
          </div>
          <ul class="guide-effects">
            <li
              v-for="(item, idx) in currentGuide.effects"
              :key="idx">
              {{ item }}
            </li>
          </ul>
        </div>
      </div>
      <div
        class="warning-info">
        <i class="bk-icon icon-exclamation-circle-shape warning-info-icon" />
        <span class="warning-info-text">
          <span class="warning-info-label">{{ $t('风险提示') }}：</span>
          {{ $t('此配置会影响已有流程编辑。保存前请确认名单覆盖本空间已在使用的插件（含 API 插件）。') }}
        </span>
      </div>
    </div>
    <!-- 配置内容 -->
    <div
      class="detail-form">
      <div
        v-if="!['uniform_api', 'api_gateway_credential_name'].includes(config.name) && config.ui"
        class="detail-label">
        <div class="label-text">
          {{ config.ui?.label || config.desc }}
        </div>
        <div
          v-if="config.ui?.help"
          class="label-tip">
          <bk-icon type="info" />
          <span>{{ config.ui.help }}</span>
        </div>
      </div>
      <component
        :is="activeComponent"
        ref="controlRef"
        :key="formModeRandomKey"
        v-model="formValue"
        :schema="config.ui"
        :example-placeholder="config.example"
        :name="config.name"
        :space-id="spaceId"
        :verifying="localVerifying"
        :verify-result="localVerifyResult"
        :doc-link="config.help && config.help.doc_link"
        @verify="onControlVerify" />
    </div>
    <div class="detail-footer">
      <bk-button
        theme="primary"
        :loading="saving"
        :disabled="!isDirty"
        @click="handleSave">
        {{ $t('保存') }}
      </bk-button>
      <bk-button
        v-show="config?.ui?.control !== 'member_selector'"
        :disabled="config.isDefault"
        @click="$emit('reset', config)">
        {{ $t('恢复默认') }}
      </bk-button>
      <!-- 暂时不添加 -->
      <!-- <template v-if="config.name === 'api_gateway_credential_name'">
        <bk-button
          :loading="localVerifying"
          :disabled="localVerifying"
          @click="handleVerify">
          {{ localVerifyResult ? $t('重新测试') : $t('测试有效性') }}
        </bk-button>
        <div
          v-if="localVerifyResult"
          class="verify-result-area">
          <template v-if="localVerifyResult.ok">
            <i class="bk-icon icon-check-circle-shape verify-icon is-ok" />
            <span class="verify-text">
              {{ $t('测试通过') }}
            </span>
          </template>
          <template v-else>
            <i class="bk-icon icon-close-circle-shape verify-icon is-fail" />
            <span class="verify-text is-fail">
              {{ $t('测试失败：') }}{{ verifyErrorMessage }}
            </span>
          </template>
        </div>
      </template> -->
    </div>
    <!-- 空间插件配置保存确认弹窗 -->
    <bk-dialog
      v-model="pluginSaveConfirmVisible"
      :title="null"
      :width="520"
      :mask-close="true"
      :show-footer="false"
      theme="primary">
      <div class="plugin-save-confirm-dialog">
        <div class="confirm-icon-wrap">
          <i class="bk-icon icon-exclamation confirm-icon" />
        </div>
        <div class="confirm-title">
          {{ $t('确认保存空间插件配置？') }}
        </div>
        <div class="confirm-suggest">
          <div class="confirm-desc">
            {{ $t('保存后立即生效，可能影响本空间已有流程：') }}
          </div>
          <ol class="confirm-list">
            <li>{{ $t('画布插件面板将按名单过滤，未覆盖的标准插件不再显示') }}</li>
            <li>{{ $t('已使用这些插件的流程，打开节点时可能提示「未找到」，无法继续编辑') }}</li>
            <li>{{ $t('使用「仅显示」且未把 API 插件列入时，第三方 / API 插件入口也会消失，存量 API 节点同样可能无法打开') }}</li>
          </ol>
          <div class="suggest-text">
            {{ $t('建议：已有流程时优先用「隐藏名单」；用「仅显示」时请把本空间已用到的插件（含 API 插件）全部列入。') }}
          </div>
          <div class="suggest-note">
            {{ $t('已在运行的任务不会因此停止。') }}
          </div>
        </div>
        <div class="confirm-actions">
          <bk-button
            theme="default"
            @click="pluginSaveConfirmVisible = false">
            {{ $t('取消') }}
          </bk-button>
          <bk-button
            theme="danger"
            @click="confirmPluginSave">
            {{ $t('仍要保存') }}
          </bk-button>
        </div>
      </div>
    </bk-dialog>
  </div>
</template>
<script>
  import { mapActions } from 'vuex';
  import { getControlComponent } from './controls/index.js';
  import tools from '@/utils/tools.js';
  import JsonEditorControl from './controls/JsonEditorControl.vue';
  import defaultCanvasImage from '@/assets/images/horizontal-vs-vertical-canvas.png';
  // 结构化复合控件（可切换 JSON 源码；is_mix_type 之外的对象型存储）
  const COMPOSITE_CONTROLS = ['credential_map', 'api_plugin_config', 'plugin_scope', 'engine_kv'];
  const KNOWN_CONTROLS = [
    'switch', 'radio', 'select', 'input', 'number', 'url', 'string_list', 'member_selector',
    ...COMPOSITE_CONTROLS,
  ];
  // 控件自带验证 UI（不再显示 ConfigDetail 顶部统一"测试"按钮）
  const SELF_VERIFY_CONTROLS = ['api_plugin_config'];
  const CONTROL_GUIDES = {
    plugin_scope: {
      purpose: '控制流程画布插件面板里标准插件的可见范围。按「仅显示」或「隐藏」过滤，保存后立即生效。',
      effects: [
        '被过滤的标准插件从画布面板消失，不能再拖入新节点。',
        '已有流程若用了这些插件，打开节点配置时可能提示「未找到」，无法继续编辑。',
        '「仅显示」按插件 code 白名单生效。名单里没有 API 插件 / 第三方插件时，它们的入口也会从面板消失，存量 API 节点同样可能无法打开。',
        '已在运行的任务不会因此停掉；但编辑受阻后无法改这些节点再保存。',
      ],
    },
  };

  export default {
    name: 'ConfigDetail',
    components: {
      JsonEditorControl,
    },
    props: {
      config: {
        type: Object,
        default: null,
      },
      spaceId: {
        type: [String, Number],
        default: '',
      },
      saving: {
        type: Boolean,
        default: false,
      },
      // 父组件保存失败（校验未通过/接口异常）后置为 true，用于头部异常状态
      saveError: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        formValue: this.readValue(this.config),
        // 初始值快照，用于判断是否发生变动
        initialValue: tools.deepClone(this.readValue(this.config)),
        isSourceMode: false,
        currentMode: 'form_value',
        formModeRandomKey: 0,
        localVerifying: false,
        localVerifyResult: null,
        localSaveError: false,
        defaultCanvasImage,
        // 空间插件配置保存二次确认弹窗
        pluginSaveConfirmVisible: false,
      };
    },
    computed: {
      controlComponent() {
        const ui = this.config && this.config.ui;
        const control = ui ? ui.control : null;
        return getControlComponent(control);
      },
      activeComponent() {
        return this.isSourceMode ? JsonEditorControl : this.controlComponent;
      },
      hasMedia() {
        const media = this.config && this.config.help && this.config.help.media;
        return Array.isArray(media) && media.length > 0;
      },
      currentControl() {
        return this.config && this.config.ui ? this.config.ui.control : null;
      },
      isCompositeControl() {
        return COMPOSITE_CONTROLS.includes(this.currentControl);
      },
      controlOwnsVerify() {
        return SELF_VERIFY_CONTROLS.includes(this.currentControl);
      },
      // 部分控件需要在前端补充“用途 / 影响”说明（文案走 i18n）
      currentGuide() {
        const guide = CONTROL_GUIDES[this.currentControl];
        if (!guide) return null;
        return {
          purpose: this.$t(guide.purpose),
          effects: (guide.effects || []).map(item => this.$t(item)),
        };
      },
      isJsonControl() {
        // 源码模式或未知/未声明控件都走 JSON 兜底
        if (this.isSourceMode) return true;
        return !KNOWN_CONTROLS.includes(this.currentControl);
      },
      detailStatus() {
        if (this.localSaveError || this.saveError) return 'error';
        return this.config.isDefault ? 'default' : 'configured';
      },
      // 当前值与初始值是否发生变动
      isDirty() {
        return !tools.isDataEqual(this.formValue, this.initialValue);
      },
      // 解析测试失败错误信息
      verifyErrorMessage() {
        if (!this.localVerifyResult) return '';
        if (this.localVerifyResult.error && this.localVerifyResult.error.message) {
          return this.localVerifyResult.error.message;
        }
        if (this.localVerifyResult.message) {
          return this.localVerifyResult.message;
        }
        return this.$t('未知错误');
      },
    },
    watch: {
      config(val) {
        this.formValue = this.readValue(val);
        // 同步重置初始值快照，切换配置项后重新计算是否变动
        this.initialValue = tools.deepClone(this.readValue(val));
        // 切换配置项时清空测试结果
        this.localVerifyResult = null;
        // 切换配置项时清空保存失败标记
        this.localSaveError = false;
      },
    },
    methods: {
      ...mapActions('spaceConfig/', [
        'verifySpaceConfig',
      ]),
      // 存储值 -> 控件值
      readValue(config) {
        if (!config) return '';
        if (config.isDefault) {
          const hasDefault = config.default_value !== null
            && config.default_value !== undefined;
          if (hasDefault) return config.default_value;
          // JSON 型配置默认返回空对象
          return config.value_type === 'JSON' ? {} : '';
        }
        // json_value非空时完整映射
        if (config.is_mix_type) {
          const jsonValue = config.json_value;
          if (jsonValue && typeof jsonValue === 'object' && Object.keys(jsonValue).length > 0) {
            return jsonValue;
          }
          return config.value || '';
        }
        return config.value_type === 'TEXT'
          ? config.value
          : config.json_value;
      },
      // 控件值 -> 存储 payload
      buildPayload() {
        const { id, name, value_type: valueType, is_mix_type: isMixType } = this.config;
        const payload = { id, name, space_id: this.spaceId, value_type: valueType };
        const formVal = this.formValue;
        if (this.isJsonControl) {
          let jsonValue;
          if (typeof formVal === 'string' && formVal.trim() !== '') {
            jsonValue = JSON.parse(formVal);
          } else if (formVal && typeof formVal === 'object') {
            jsonValue = formVal;
          } else {
            // JSON 源码为空时解析为空对象
            jsonValue = {};
          }
          if (valueType === 'TEXT' && !isMixType) {
            payload.text_value = typeof formVal === 'string' ? formVal : JSON.stringify(formVal);
          } else {
            payload.value_type = isMixType ? 'JSON' : valueType;
            payload.json_value = jsonValue;
          }
        } else if (isMixType) {
          if (formVal && typeof formVal === 'object') {
            payload.value_type = 'JSON';
            payload.json_value = formVal;
          } else {
            payload.value_type = 'TEXT';
            payload.text_value = formVal || '';
          }
        } else if (valueType === 'TEXT') {
          payload.text_value = formVal;
        } else {
          payload.json_value = formVal;
        }
        // plugin_scope 控件：allow_all场景下plugin_codes传空
        if (this.currentControl === 'plugin_scope'
          && payload.json_value
          && payload.json_value.default
          && payload.json_value.default.mode === 'allow_all') {
          payload.json_value = {
            ...payload.json_value,
            default: { ...payload.json_value.default, plugin_codes: [] },
          };
        }
        return payload;
      },
      async handleSave() {
        this.localSaveError = false;
        if (
          this.isJsonControl
          && typeof this.formValue === 'string'
          && this.formValue.trim() !== ''
          && !tools.checkIsJSON(this.formValue)
        ) {
          this.localSaveError = true;
          this.$bkMessage({
            message: this.$t('数据格式不正确，应为JSON格式'),
            theme: 'error',
          });
          return;
        }
        if (this.$refs.controlRef && typeof this.$refs.controlRef.validate === 'function') {
          const valid = await this.$refs.controlRef.validate();
          if (!valid) {
            this.localSaveError = true;
            return;
          }
        }
        if (this.config.name === 'superusers') {
          const userList = Array.isArray(this.formValue) ? this.formValue : [];
          if (userList.length === 0) {
            this.localSaveError = true;
            this.$bkMessage({
              message: this.$t('管理员至少保留一位'),
              theme: 'error',
            });
            return;
          }
        }
        // 空间插件配置：保存前二次确认
        if (this.config.name === 'space_plugin_config') {
          this.pluginSaveConfirmVisible = true;
          return;
        }
        this.$emit('save', this.buildPayload());
      },
      // 确认保存空间插件配置
      confirmPluginSave() {
        this.pluginSaveConfirmVisible = false;
        this.$emit('save', this.buildPayload());
      },
      // api插件配置测试
      async onControlVerify(payload) {
        try {
          this.localVerifying = true;
          this.localVerifyResult = null;
          const resp = await this.verifySpaceConfig({
            space_id: this.spaceId,
            name: this.config.name,
            value: this.formValue,
            ...(payload || {}),
          });
          this.localVerifyResult = resp.data || resp;
        } catch (error) {
          this.localVerifyResult = {
            ok: false,
            error: { message: String(error) },
          };
        } finally {
          this.localVerifying = false;
        }
      },
      toggleSourceMode(val) {
        if (val === 'form_value') {
          // JSON -> 结构化：把源码字符串解析回对象
          if (typeof this.formValue === 'string') {
            // JSON 源码为空时不做格式校验，直接清空（结构化控件空值为空对象）
            if (this.formValue.trim() === '') {
              this.formValue = {};
            } else if (!tools.checkIsJSON(this.formValue)) {
              this.$bkMessage({ message: this.$t('数据格式不正确，应为JSON格式'), theme: 'error' });
            } else {
              this.formValue = JSON.parse(this.formValue);
            }
          }
          this.formModeRandomKey = new Date().getTime();
        } else if (val === 'json_value') {
          // 结构化 -> JSON：把对象序列化为字符串
          if (typeof this.formValue === 'object' && this.formValue !== null) {
            if (this.currentControl === 'plugin_scope'
              && Object.keys(this.formValue).length === 0) {
              this.formValue = JSON.stringify({ default: { mode: 'allow_all', plugin_codes: [] } }, null, 2);
            } else {
              this.formValue = JSON.stringify(this.formValue, null, 2);
            }
          } else if (
            typeof this.formValue === 'string'
            && this.formValue.trim() !== ''
          ) {
            // 网关凭证配置存在默认凭证且未配置作用域是value_type为TEXT
            if (this.currentControl === 'credential_map') {
              this.formValue = JSON.stringify({ default: this.formValue }, null, 2);
            }
          } else if (this.currentControl === 'plugin_scope') {
            this.formValue = JSON.stringify({ default: { mode: 'allow_all', plugin_codes: [] } }, null, 2);
          }
        }
        this.isSourceMode = val === 'json_value';
        if (val === 'form_value') {
          this.$nextTick(() => {
            if (this.$refs.controlRef && typeof this.$refs.controlRef.validate === 'function') {
              this.$refs.controlRef.validate();
            }
          });
        }
      },
    },
  };
</script>
<style lang="scss" scoped>
  .config-detail {
    padding: 16px 24px;
  }
  .detail-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;
    .detail-title-wrap {
      display: flex;
      align-items: center;
      margin-bottom: 4px;
      .detail-title {
        font-size: 16px;
        font-weight: 700;
        margin-right: 12px;
      }
      .detail-status {
        font-size: 12px;
        padding: 0 8px;
        height: 22px;
        line-height: 22px;
        border-radius: 2px;
        &.is-custom {
          color: #14a568;
          background: #e4faf0;
        }
        &.is-default {
          color: #979ba5;
          background: #f0f1f5;
        }
        &.is-error {
          color: #ea3636;
          background: #fde9e9;
        }
      }
    }
    .detail-help {
      font-size: 12px;
      line-height: 20px;
      color: #4d4f56;
  }
  }
  .config-canvas-example {
    padding: 12px 16px;
    background: #f5f7fa;
    display: flex;
    flex-direction: column;
    margin-bottom: 24px;
    .config-canvas-example-title {
      display: flex;
      color: #313238;
      font-size: 12px;
      line-height: 20px;
      margin-bottom: 8px;
    }
    .config-canvas-example-icon {
      font-size: 12px;
      color: #3a84ff;
      line-height: 20px;
      margin-left: 12px;
      margin-right: 2px;
    }
    ::v-deep .bk-link {
      .bk-link-text {
        font-size: 12px;
      }
    }
    .config-canvas-example-gif {
      display: flex;
      align-items: center;
      justify-content: center;
      background: #eaebf0;
      flex-direction: column;
      .config-canvas-example-gif-wrap {
        margin: 12px 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        img {
          max-width: 640px;
          width: 100%;
          height: auto;
          margin-bottom: 12px;
        }
      }
      .caption {
        font-size: 14px;
        line-height: 22px;
        color: #979ba5;
      }
    }
  }
  .detail-form {
    margin-bottom: 32px;
    .detail-label {
      display: flex;
      font-size: 12px;
      margin-bottom: 8px;
      .label-text {
         font-weight: 700;
      }
      .label-tip {
        margin-left: 8px;
        color: #979ba5;
        margin-left: 16px;
        display: flex;
        align-items: center;
        .bk-icon {
          margin-right: 2px;
        }
      }
    }
  }
  .detail-verify {
    margin-bottom: 16px;
    .verify-result {
      margin-left: 12px;
      font-size: 13px;
      &.is-ok {
        color: #14a568;
      }
      &.is-fail {
        color: #ea3636;
      }
    }
  }
  .detail-footer {
    display: flex;
    align-items: center;
    gap: 8px;
    .verify-result-area {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-left: 8px;
      .verify-icon {
        font-size: 14px;
        &.is-ok {
          color: #2caf5e;
        }
        &.is-fail {
          color: #ea3636;
        }
      }
      .verify-text {
        font-size: 12px;
        color: #63656e;
        &.is-fail {
          color: #ea3636;
        }
      }
      .view-example-link {
        font-size: 12px;
        color: #3a84ff;
        cursor: pointer;
      }
    }
  }
  .detail-guide {
    margin-bottom: 16px;
    padding: 12px 16px;
    background: #f5f7fa;
    border-radius: 2px;
    .guide-block + .guide-block {
      margin-top: 12px;
    }
    .guide-title {
      font-size: 12px;
      font-weight: 700;
      color: #313238;
      line-height: 22px;
      margin-bottom: 6px;
    }
    .guide-body {
      font-size: 12px;
      line-height: 20px;
      color: #4d4f56;
      word-break: break-word;
    }
    .guide-effects {
      margin: 0;
      padding-left: 18px;
      li {
        // 直接命中 li 以覆盖全局 reset 的 list-style: none（写在 ul 上会被继承规则打败）
        list-style: disc;
        font-size: 12px;
        line-height: 20px;
        color: #4d4f56;
        word-break: break-word;
      }
    }
  }
  .warning-info {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #faf1e3;
    border: 1px solid #f7d8ac;
    border-radius: 5px;
    padding: 8px 12px;
    color: #f08c10;
    margin-bottom: 20px;
    .warning-info-icon {
      color: #ff9c01;
      font-size: 14px;
      line-height: 20px;
      flex-shrink: 0;
      margin-top: 1px;
    }
    .warning-info-text {
      font-size: 12px;
      line-height: 20px;
      word-break: break-word;
    }
    .warning-info-label {
      font-weight: 700;
    }
  }
  // 空间插件配置保存确认弹窗样式
  .plugin-save-confirm-dialog {
    text-align: center;
    padding: 0 8px;
    .confirm-icon-wrap {
      display: inline-flex;
      justify-content: center;
      align-items: center;
      width: 42px;
      height: 42px;
      border-radius: 50%;
      background: #fff3e0;
      margin-bottom: 16px;
    }
    .confirm-icon {
      font-size: 32px;
      color: #ff9800;
    }
    .confirm-title {
      font-size: 20px;
      color: #313238;
      line-height: 32px;
      margin-bottom: 16px;
    }
    .confirm-suggest {
      font-size: 12px;
      line-height: 22px;
      background: #f5f7fa;
      padding: 12px 16px;
      border-radius: 2px;
      margin-bottom: 24px;
      text-align: left;
      .confirm-desc {
        font-size: 14px;
        color: #4d4f56;
        margin-bottom: 8px;
        word-break: break-word;
      }
      .confirm-list {
        margin: 0 0 12px;
        padding-left: 22px;
        li {
          // 直接命中 li 以覆盖全局 reset 的 list-style: none
          list-style: decimal;
          font-size: 12px;
          line-height: 22px;
          color: #4d4f56;
          word-break: break-word;
          margin-bottom: 4px;
          &:last-child {
            margin-bottom: 0;
          }
        }
      }
      .suggest-text {
        color: #4d4f56;
        word-break: break-word;
        margin-bottom: 6px;
      }
      .suggest-note {
        color: #979ba5;
        word-break: break-word;
      }
    }
    .confirm-actions {
      display: flex;
      justify-content: end;
      gap: 8px;
      .bk-button {
        min-width: 96px;
      }
    }
  }
</style>
