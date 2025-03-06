<template>
  <bk-dialog
    :value="isShow"
    theme="primary"
    render-directive="if"
    :mask-close="false"
    width="1000"
    :ok-text="$t('调试')"
    ext-cls="debug-decision-dialog"
    :loading="debugLoading"
    :auto-close="false"
    @cancel="$emit('close')">
    <div class="content-wrap">
      <div class="left-content">
        <p class="label">
          {{ $t('字段输入') }}
        </p>
        <bk-form
          ref="debugForm"
          :label-width="100"
          :model="formData"
          form-type="vertical">
          <bk-form-item
            v-for="item in inputs"
            :key="item.id"
            ref="formItem"
            :label="''"
            :required="true"
            :property="item.id"
            :rules="rules.required">
            <input-item
              :inputs="item"
              :form-data="formData"
              :is-view-mode="false"
              :render="false" />
          </bk-form-item>
        </bk-form>
        <bk-button
          theme="primary"
          @click="handleConfirm">
          {{ $t('调试') }}
        </bk-button>
      </div>
      <div class="right-content">
        <p class="label">
          {{ $t('输出结果') }}
        </p>
        <FullCodeEditor
          ref="fullCodeEditor"
          v-model="resultData"
          :options="{ language: 'json', readOnly: true }" />
      </div>
    </div>
    <bk-button
      slot="footer"
      type="submit"
      @click="$emit('close')">
      {{ $t('关闭') }}
    </bk-button>
  </bk-dialog>
</template>

<script>
  import InputItem from '@/components/SpecialPluginInputForm/DmnPlugin/InputItem.vue';
  import FullCodeEditor from '@/components/common/FullCodeEditor.vue';
  import { mapActions } from 'vuex';
  export default {
    name: 'DebugDialog',
    components: {
      InputItem,
      FullCodeEditor,
    },
    props: {
      isShow: {
        type: Boolean,
        default: false,
      },
      isAdminPth: {
        type: Boolean,
        default: false,
      },
      decisionId: {
        type: [String, Number],
        default: '',
      },
      spaceId: {
        type: [String, Number],
        default: '',
      },
      templateId: {
        type: [String, Number],
        default: '',
      },
      inputs: {
        type: Array,
        default: () => ([]),
      },
    },
    data() {
      return {
        formData: {},
        rules: {
          required: [
            {
              required: true,
              message: this.$t('必填项'),
              trigger: 'blur',
            },
          ],
        },
        debugLoading: false,
        resultData: '',
      };
    },
    watch: {
      inputs: {
        handler(val) {
          const formData = val && val.reduce((acc, cur) => {
            acc[cur.id] = '';
            return acc;
          }, {});
          this.formData = formData;
        },
        deep: true,
        immediate: true,
      },
      isShow(val) {
        val && setTimeout(() => {
          const editorInstance = this.$refs.fullCodeEditor;
          if (editorInstance) {
            editorInstance.layoutCodeEditorInstance();
          }
          if (!val) {
            this.formData = {};
          }
        });
      },
    },
    methods: {
      ...mapActions('decisionTable/', [
        'debugDecision',
      ]),
      handleConfirm() {
        this.debugLoading = true;
        this.$refs.debugForm.validate().then(async () => {
          try {
            const resp = await this.debugDecision({
              id: this.decisionId,
              facts: { ...this.formData },
              isAdmin: this.isAdminPth,
              space_id: this.spaceId,
              template_id: this.templateId,
            });
            if (!resp.result) return;
            const { error_hint: errorHint, outputs } = resp.data;
            const data = errorHint || outputs;
            this.resultData = JSON.stringify(data, null, 4);
          } catch (error) {
            console.warn(error);
          } finally {
            this.debugLoading = false;
          }
        }, () => {
          this.debugLoading = false;
        });
      },
    },
  };
</script>

<style lang="scss">
@import '../../../../../scss/mixins/scrollbar.scss';
.debug-decision-dialog {
  .bk-dialog-body {
    padding-bottom: 0;
  }
  .content-wrap {
    display: flex;
    min-height: 100px;
  }
  .left-content,
  .right-content {
    flex: 1;
    .label {
      position: relative;
      line-height: 32px;
    }
  }
  .left-content {
    margin-right: 15px;
    .label::after {
      content: '*';
      position: absolute;
      top: 50%;
      font-size: 12px;;
      color: #ea3636;
      transform: translate(3px, -50%);
    }
    .bk-form {
      max-height: 350px;
      padding-right: 10px;
      overflow: auto;
      @include scrollbar;
      .bk-form-item:last-child {
        .input-item {
          margin-bottom: 0;
        }
      }
    }
    > button {
      margin: 8px 0 16px;
    }
  }
  .full-code-editor {
    height: calc(100% - 32px);
    min-height: 280px;
  }
}
</style>
