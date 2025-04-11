<template>
  <bk-sideslider
    :is-show="isShow"
    :width="640"
    :title="$t('新建任务')"
    class="create-task-slider"
    :before-close="handleCancel">
    <template slot="content">
      <bk-form
        ref="createTaskForm"
        :label-width="100"
        :model="taskFormData">
        <bk-form-item
          :label="$t('任务名称')"
          :required="true"
          property="name"
          :rules="rules.name">
          <bk-input
            v-model="taskFormData.name"
            :maxlength="stringLength.TASK_NAME_MAX_LENGTH"
            :show-word-limit="true" />
        </bk-form-item>
        <bk-form-item
          ref="codeFormItem"
          :label="$t('请求参数')"
          :desc="$t('流程的入参')"
          property="constants">
          <div class="bk-button-group">
            <bk-button
              :class="taskFormData.mode === 'form' ? 'is-selected' : ''"
              @click="taskFormData.mode = 'form'">
              {{ $t('表单模式') }}
            </bk-button>
            <bk-button
              :class="taskFormData.mode === 'json' ? 'is-selected' : ''"
              @click="taskFormData.mode = 'json'">
              {{ $t('json模式') }}
            </bk-button>
          </div>
          <div
            v-if="taskFormData.mode === 'form'"
            class="form-wrapper">
            <TaskParamEdit
              ref="taskParamEdit"
              :editable="true"
              :constants="pipelineTree.constants" />
          </div>
          <div
            v-else
            class="code-wrapper">
            <FullCodeEditor
              ref="fullCodeEditor"
              v-model="taskFormData.constants"
              :options="{ language: 'json', placeholder: { '${key}': 'value' } }" />
            <p
              v-if="!isJsonConstantsValid"
              v-bk-tooltips.top="$t('请求参数格式不正确，应为JSON格式')"
              class="valid-error-tips bk-icon icon-exclamation-circle-shape" />
          </div>
        </bk-form-item>
      </bk-form>
    </template>
    <template slot="footer">
      <bk-button
        class="mr10"
        theme="primary"
        @click="createTaskConfirm">
        {{ $t('提交') }}
      </bk-button>
      <bk-button
        theme="default"
        @click="handleCancel">
        {{ $t('取消') }}
      </bk-button>
    </template>
  </bk-sideslider>
</template>
<script>
  import { STRING_LENGTH } from '@/constants/index.js';
  import { mapState, mapActions } from 'vuex';
  import moment from 'moment-timezone';
  import FullCodeEditor from '@/components/common/FullCodeEditor.vue';
  import TaskParamEdit from '../../../template/TemplateMock/MockExecute/components/TaskParamEdit.vue';
  import tools from '@/utils/tools.js';

  export default {
    name: 'CreateTaskSideslider',
    components: {
      FullCodeEditor,
      TaskParamEdit,
    },
    props: {
      isShow: {
        type: Boolean,
        default: false,
      },
      row: {
        type: Object,
        default: () => ({}),
      },
  },
    data() {
      return {
        taskFormData: {},
        pipelineTree: {},
        rules: {
          name: [
            {
              required: true,
              message: this.$t('必填项'),
              trigger: 'blur',
            },
          ],
        },
        stringLength: STRING_LENGTH,
        createLoading: false,
      };
    },
    computed: {
      ...mapState({
        spaceId: state => state.spaceId,
        username: state => state.username,
      }),
      isJsonConstantsValid() {
        const { constants, mode } = this.taskFormData;
        return mode === 'json' ? tools.checkIsJSON(constants) : true;
      },
    },
    watch: {
      isShow: {
        handler(val) {
          if (val) {
            this.loadInitialData();
          } else {
            this.taskFormData = {};
          }
        },
        immediate: true,
      },
    },
    methods: {
      ...mapActions('template/', [
        'loadTemplateData',
      ]),
      ...mapActions('task/', [
        'createTask',
      ]),
      async loadInitialData() {
        try {
          this.taskFormData = {
            mode: 'form',
            template_id: this.row.id,
            name: `${this.row.name}_${moment().format('YYYYMMDDHHmmss')}`,
            creator: this.username,
            constants: '',
          };
          const resp = await this.loadTemplateData({
            templateId: this.row.id,
          });
          this.pipelineTree = resp.pipeline_tree;
        } catch (error) {
          console.warn(error);
        }
      },
      async createTaskConfirm() {
        try {
          const isFormValid = await this.$refs.createTaskForm.validate();
          const isParamsValid = this.taskFormData.mode === 'json'
            ? this.isJsonConstantsValid
            : this.$refs.taskParamEdit.validate();

          if (!isFormValid || !isParamsValid) {
            this.createLoading = false;
            return;
          };

          this.createLoading = true;
          const resp = await this.createTask({
            spaceId: this.spaceId,
            params: {
              ...this.taskFormData,
              constants: this.getParameterConstants(),
            },
          });

          if (resp.result) {
            this.$bkMessage({
              message: this.$t('任务创建成功'),
              theme: 'success',
            });
            const { href } = this.$router.resolve({
              name: 'taskExecute',
              params: {
                spaceId: this.spaceId,
              },
              query: {
                instanceId: resp.data.id,
              },
            });
            window.open(href, '_blank');
            this.$emit('close');
          };
        } catch (error) {
          console.warn(error);
        } finally {
          this.createLoading = false;
        };
      },
      getParameterConstants() {
        const { constants, mode } = this.taskFormData;
        if (mode === 'json') {
          return JSON.parse(constants);
        };
        const variableData = this.$refs.taskParamEdit.getVariableData();
        return Object.values(variableData).reduce((acc, cur) => Object.assign(acc, { [cur.key]: cur.value }), {});
      },
      handleCancel() {
        this.$emit('close');
      },
    },
  };
</script>
<style lang="scss">
  @import '../../../../scss/mixins/scrollbar.scss';
  .create-task-slider {
    .bk-sideslider-wrapper {
      display: flex;
      flex-direction: column;
    }
    .bk-sideslider-content {
      height: max-content;
      padding: 28px 24px 8px;
      @include scrollbar;
    }
    .bk-sideslider-footer {
      height: max-content;
      padding: 24px 0 24px 124px;
      background: none !important;
    }
    .bk-button-group {
      margin-bottom: 8px;
    }
    .bk-form-item {
      .form-wrapper {
        padding: 12px;
        background: #F0F1F5;
        border-radius: 2px;
      }
      .code-wrapper {
        height: 300px;
      }
      .valid-error-tips {
        position: absolute;
        top: 12px;
        right: 0;
        color: #ea3636;
        cursor: pointer;
        font-size: 16px;
      }
      &:not(:first-child) {
        margin-top: 28px;
      }
    }
    .render-form {
      .rf-group-name .name {
        font-weight: normal;
      }
    }
  }
</style>
