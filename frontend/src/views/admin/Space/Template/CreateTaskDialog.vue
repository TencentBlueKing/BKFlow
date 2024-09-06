<template>
  <bk-dialog
    v-model="showCreateTaskDialog"
    theme="primary"
    :mask-close="false"
    header-position="left"
    :width="600"
    :esc-close="false"
    :show-footer="false"
    render-directive="if"
    :title="$t('新建任务')"
    @cancel="$emit('close')">
    <bk-form
      ref="createTaskForm"
      :label-width="100"
      :model="taskFormData">
      <bk-form-item
        :label="$t('模板Id')"
        :required="true"
        :property="'template_id'">
        <bk-input
          v-model="taskFormData.template_id"
          :disabled="true" />
      </bk-form-item>
      <bk-form-item
        :label="$t('任务名称')"
        :required="true"
        :property="'name'"
        :rules="rules.name">
        <bk-input
          v-model="taskFormData.name"
          :maxlength="stringLength.TASK_NAME_MAX_LENGTH"
          :show-word-limit="true" />
      </bk-form-item>
      <bk-form-item
        :label="$t('创建人')"
        :required="true"
        :property="'creator'">
        <bk-input
          v-model="taskFormData.creator"
          disabled />
      </bk-form-item>
      <bk-form-item
        ref="codeFormItem"
        :label="$t('请求参数')"
        :property="'constants'"
        class="code-form-item">
        <div class="code-wrapper">
          <FullCodeEditor
            ref="fullCodeEditor"
            v-model="taskFormData.constants"
            :options="{ language: 'json' }" />
        </div>
      </bk-form-item>
      <bk-form-item>
        <bk-button
          theme="primary"
          :loading="createLoading"
          @click="createTaskConfirm">
          {{ $t('提交') }}
        </bk-button>
        <bk-button
          ext-cls="mr5"
          theme="default"
          :disabled="createLoading"
          @click="$emit('close')">
          {{ $t('取消') }}
        </bk-button>
      </bk-form-item>
    </bk-form>
  </bk-dialog>
</template>

<script>
  import { STRING_LENGTH } from '@/constants/index.js';
  import { mapState, mapActions } from 'vuex';
  import moment from 'moment-timezone';
  import FullCodeEditor from '@/components/common/FullCodeEditor.vue';
  import tools from '@/utils/tools.js';
  export default {
    name: 'CreateTaskDialog',
    components: {
      FullCodeEditor,
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
        showCreateTaskDialog: false,
        taskFormData: {},
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
    },
    watch: {
      isShow: {
        handler(val) {
          this.showCreateTaskDialog = val;
          if (val) {
            this.taskFormData = {
              template_id: this.row.id,
              name: `${this.row.name}_${moment().format('YYYYMMDDHHmmss')}`,
              creator: this.username,
              constants: '',
            };
            setTimeout(() => {
              const editorInstance = this.$refs.fullCodeEditor;
              if (editorInstance) {
                editorInstance.layoutCodeEditorInstance();
              }
            });
          } else {
            this.taskFormData = {};
          }
        },
        immediate: true,
      },
    },
    methods: {
      ...mapActions('task/', [
        'createTask',
      ]),
      createTaskConfirm() {
        this.$refs.createTaskForm.validate().then(async (validator) => {
          if (!validator) {
            this.createLoading = false;
            return;
          }
          // constants转json格式
          let constantsJson = {};
          const { constants } = this.taskFormData;
          if (constants) {
            if (tools.checkIsJSON(constants)) {
              constantsJson = JSON.parse(constants);
            } else {
              this.$bkMessage({
                message: this.$t('请求参数格式不正确，应为JSON格式'),
                theme: 'error',
              });
              return;
            }
          }
          try {
            this.createLoading = true;
            const resp = await this.createTask({
              spaceId: this.spaceId,
              params: {
                ...this.taskFormData,
                constants: constantsJson,
              },
            });
            if (resp.result) {
              this.$bkMessage({
                message: this.$t('任务创建成功'),
                theme: 'success',
              });
              this.createLoading = false;
              this.$emit('close');
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
            }
          } catch (error) {
            console.warn(error);
            this.createLoading = false;
          }
        });
      },
    },
  };
</script>

<style>

</style>
