<template>
  <bk-dialog
    :value="isShow"
    theme="primary"
    header-position="left"
    ext-cls="credential-dialog"
    :width="640"
    :mask-close="false"
    :esc-close="false"
    :title="$t('编辑凭证作用域')"
    render-directive="if"
    @cancel="handleCancel">
    <div class="content-wrapper">
      <bk-checkbox
        v-model="formData.unlimited"
        style="margin-bottom: 15px">
        {{ $t("对空间内所有流程开放") }}
      </bk-checkbox>
      <CredentialContentTable
        ref="credentialContentTableRef"
        empty-tip="第n项凭证作用域不能为空"
        error-tip="第n项凭证作用域格式错误, 仅支持字母、数字、下划线、连字符"
        :is-unique-key="false"
        :table-fields="tableFields"
        :select-list="formData.scopes"
        :disabled="formData.unlimited" />
    </div>
    <template #footer>
      <div class="dialog-btn">
        <bk-button
          theme="primary"
          :loading="confirmLoading"
          @click="handleConfirm">
          {{ $t("确定") }}
        </bk-button>
        <bk-button @click="handleCancel">
          {{ $t("取消") }}
        </bk-button>
      </div>
    </template>
  </bk-dialog>
</template>

<script>
import { mapActions } from 'vuex';
import CredentialContentTable from './CredentialContentTable.vue';

export default {
  components: { CredentialContentTable },
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    spaceId: {
      type: [String, Number],
      default: '',
    },
    detail: {
      type: Object,
      default: () => {},
    },
  },
  data() {
    return {
      confirmLoading: false,
      formData: {
        unlimited: false,
        scopes: [],
      },
      tableFields: [
        {
          prop: 'scope_type',
          label: this.$t('作用域类型'),
          inputType: 'text',
        },
        {
          prop: 'scope_value',
          label: this.$t('作用域值'),
          inputType: 'text',
        },
      ],
    };
  },
  watch: {
    detail: {
      handler(rowData) {
        if (Object.keys(rowData).length) {
          this.getCredentialScope(rowData);
        }
      },
      immediate: true,
    },
  },
  methods: {
    ...mapActions('credentialConfig', ['loadCredentialScope', 'updateCredentialScope']),
    async getCredentialScope(rowData) {
      const params = {
        id: rowData.id,
        space_id: this.spaceId,
      };
      const res = await this.loadCredentialScope(params);
      if (res.result) {
        const { unlimited, scopes } = res.data;
        this.formData = Object.assign(
          {},
          {
            unlimited,
            scopes,
          }
        );
      }
    },
    async handleConfirm() {
      try {
        const { credentialList, validate } = this.$refs.credentialContentTableRef;
        const isValidate = validate();
        if (isValidate) {
          const params = {
            ...this.formData,
            space_id: this.spaceId,
            id: this.detail.id,
            scopes: this.formData.unlimited ? [] : credentialList,
          };
          this.confirmLoading = true;
          const res = await this.updateCredentialScope(params);
          if (res.result) {
            this.$bkMessage({
              message: this.$t('修改成功！'),
              theme: 'success',
            });
            this.handleCancel();
            this.$emit('confirm', false);
          }
        }
      } finally {
        this.confirmLoading = false;
      }
    },
    handleCancel() {
      this.formData = Object.assign({}, { unlimited: false, scopes: [] });
      this.$refs.credentialContentTableRef.clearValidate();
      this.$refs.credentialContentTableRef.setCredentialField(this.tableFields);
      this.$emit('cancel');
    },
  },
};
</script>

<style lang="scss" scoped>
@import "@/scss/mixins/credentialScope.scss";
.credential-scope-table {
  margin-top: 15px;
}
</style>
