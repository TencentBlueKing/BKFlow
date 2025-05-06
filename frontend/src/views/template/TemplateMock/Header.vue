<template>
  <div class="template-mock-header">
    <div class="header-left">
      <i
        class="bk-icon icon-arrows-left back-icon"
        @click="onCancelMock" />
      <span class="title">{{ mockStep === 'setting' ? $t('流程调试') : $t('调试执行') }}</span>
      <span
        v-if="mockStep === 'setting'"
        class="template-name">{{ tplName }}</span>
      <template v-else>
        <bk-input
          v-model="taskName"
          v-validate="taskNameRule"
          class="name-input"
          name="taskName"
          :maxlength="stringLength.TASK_NAME_MAX_LENGTH"
          :show-word-limit="true" />
        <span
          v-show="veeErrors.has('taskName')"
          class="common-error-tip">{{ veeErrors.first('taskName') }}</span>
      </template>
    </div>
    <div
      v-if="mockStep === 'setting'"
      class="header-right">
      <bk-button
        class="task-btn"
        data-test-id="templateMock_form_returnMock"
        @click.stop="onCancelMock">
        {{ $t('退出调试') }}
      </bk-button>
      <bk-button
        class="task-btn"
        data-test-id="templateMock_form_saveMock"
        :disabled="executeLoading || !tplActions.includes('MOCK')"
        :loading="saveLoading && !executeLoading"
        @click="onSaveMock">
        {{ $t('保存') }}
      </bk-button>
      <bk-button
        class="task-btn"
        theme="primary"
        :loading="executeLoading"
        :disabled="!tplActions.includes('MOCK')"
        data-test-id="templateMock_form_executeMock"
        @click.stop="onExecuteMock">
        {{ $t('执行调试') }}
      </bk-button>
    </div>
  </div>
</template>

<script>
  import moment from 'moment-timezone';
  import { STRING_LENGTH, NAME_REG } from '@/constants/index.js';
  export default {
    name: 'TemplateMockHeader',
    props: {
      tplName: {
        type: String,
        default: '',
      },
      mockStep: {
        type: String,
        default: 'setting',
      },
      saveLoading: {
        type: Boolean,
        default: false,
      },
      executeLoading: {
        type: Boolean,
        default: false,
      },
      tplActions: {
        type: Array,
        default: () => ([]),
      },
    },
    data() {
      return {
        taskName: '',
        stringLength: STRING_LENGTH,
        taskNameRule: {
          required: true,
          max: STRING_LENGTH.TASK_NAME_MAX_LENGTH,
          regex: NAME_REG,
        },
      };
    },
    watch: {
      tplName: {
        handler(val) {
          if (this.mockStep === 'setting') {
            this.taskName = val;
            return;
          }
          const nowTime = moment(new Date()).format('YYYYMMDDHHmmss');
          this.taskName = `${val}_${this.$t('调试任务')}_${nowTime}`;
        },
        immediate: true,
      },
      taskName(val) {
        this.$emit('onChange', val);
      },
    },
    methods: {
      // 退出调试
      onCancelMock() {
        this.$emit('onReturn');
      },
      // 保存
      onSaveMock() {
        this.$emit('onSave');
      },
      // 执行调试
      onExecuteMock() {
        this.$emit('onExecute');
      },
    },
  };
</script>

<style lang="scss" scoped>
.template-mock-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  padding: 0 24px 0 15px;
  background: #fff;
  box-shadow: 0 2px 4px 0 #0000001a;
  z-index: 1;
  .header-left {
    display: flex;
    align-items: center;
    font-size: 14px;
    color: #63656e;
    .back-icon {
      font-size: 28px;
      margin-top: 3px;
      color: #3a84ff;
      cursor: pointer;
    }
  }
  .header-right {
    display: flex;
    align-items: center;
    .bk-button {
      min-width: 88px;
      margin-left: 8px;
    }
  }
  .template-name,
  .bk-button:nth-child(2) {
    position: relative;
    margin-left: 33px;
    &::before {
      content: '';
      position: absolute;
      top: 0;
      left: -16px;
      height: 100%;
      width: 1px;
      background: #dcdee5;
    }
  }
  .name-input {
    width: 320px;
    margin-left: 16px;
  }
}
</style>
