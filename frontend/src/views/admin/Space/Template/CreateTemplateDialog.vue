<template>
  <bk-dialog
    v-model="showCreateTplDialog"
    theme="primary"
    :mask-close="false"
    header-position="left"
    :width="600"
    :esc-close="false"
    :show-footer="false"
    render-directive="if"
    :title="$t('新建流程')"
    @cancel="$emit('close')">
    <bk-form
      ref="createTemplateForm"
      :label-width="125"
      :model="templateFormData">
      <bk-form-item
        :label="$t('流程名称')"
        :required="true"
        :property="'name'"
        :rules="rules.name">
        <bk-input
          v-model="templateFormData.name"
          :maxlength="stringLength.TEMPLATE_NAME_MAX_LENGTH"
          :show-word-limit="true" />
      </bk-form-item>
      <bk-form-item
        :label="$t('所属作用域类型')"
        :desc="$t('scopeType')"
        :property="'scope_type'">
        <bk-input
          v-model="templateFormData.scope_type"
          :maxlength="64"
          :show-word-limit="true" />
      </bk-form-item>
      <bk-form-item
        :label="$t('所属作用域值')"
        :desc="$t('scopeValue')"
        :property="'scope_value'">
        <bk-input
          v-model="templateFormData.scope_value"
          :maxlength="64"
          :show-word-limit="true" />
      </bk-form-item>
      <bk-form-item>
        <bk-button
          theme="primary"
          :loading="createLoading"
          @click="createTemplateConfirm">
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
  import { NAME_REG, STRING_LENGTH } from '@/constants/index.js';
  import { mapActions, mapState } from 'vuex';
  export default {
    name: 'CreateTemplateDialog',
    props: {
      isShow: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        showCreateTplDialog: false,
        templateFormData: {
          name: '',
          scope_type: '',
          scope_value: '',
        },
        stringLength: STRING_LENGTH,
        rules: {
          name: [
            {
              required: true,
              message: this.$t('必填项'),
              trigger: 'blur',
            },
            {
              regex: NAME_REG,
              message: `${this.$t('流程名称不能包含')}'‘"”$&<>${this.$t('非法字符')}`,
              trigger: 'blur',
            },
          ],
        },
        createLoading: false,
      };
    },
    computed: {
      ...mapState({
        spaceId: state => state.spaceId,
      }),
    },
    watch: {
      isShow: {
        handler(val) {
          if (!val) {
            this.templateFormData = {
              name: '',
              scope_type: '',
              scope_value: '',
            };
          }
          this.showCreateTplDialog = val;
        },
        immediate: true,
      },
    },
    methods: {
      ...mapActions('template/', [
        'createTemplate',
      ]),
      createTemplateConfirm() {
        this.$refs.createTemplateForm.validate().then(async (validator) => {
          if (!validator) {
            this.createLoading = false;
            return;
          }
          try {
            this.createLoading = true;
            const data = { spaceId: this.spaceId };
            data.params = Object.keys(this.templateFormData).reduce((acc, cur) => {
              const value = this.templateFormData[cur];
              if (value) {
                acc[cur] = value;
              }
              return acc;
            }, {});
            const resp = await this.createTemplate(data);
            if (!resp.result) return;
            this.$bkMessage({
              message: this.$t('流程创建成功'),
              theme: 'success',
            });
            this.createLoading = false;
            this.$emit('close');
            this.$emit('updateList');
          } catch (error) {
            this.createLoading = false;
            console.warn(error);
          }
        });
      },
    },

  };
</script>

<style lang="scss" scoped>

</style>
