<template>
  <div class="access-credential">
    <bk-form
      ref="credentialForm"
      :label-width="140"
      ext-cls="access-credential-form"
      :model="formData"
      :rules="credentialRules">
      <bk-form-item
        v-for=" (item, index) in formData.curCredential"
        :key="item.key"
        :label="item.key"
        :required="true"
        :desc="item.description"
        :rules="credentialRules.curCredential"
        :property="'curCredential.' + index + '.value'">
        <bk-select
          v-model="item.value"
          v-bkloading="{ isLoading: listLoading, zIndex: 100 }"
          ext-cls="select-credential"
          :disabled="isViewMode"
          :clearable="false"
          :placeholder="$t('请选择凭证')"
          @selected="handleSelectedCredential">
          <bk-option
            v-for="option in list"
            :id="option.id"
            :key="option.key"
            :name="option.name" />
        </bk-select>
      </bk-form-item>
    </bk-form>
  </div>
</template>
<script>
import { mapActions } from 'vuex';

export default {
  name: 'AccessCredential',
  props: {
    isViewMode: {
      type: Boolean,
      default: false,
    },
    basicInfo: {
      type: Object,
      default: () => ({}),
    },
    spaceId: {
      type: [String, Number],
      default: '',
    },
    scopeInfo: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      formData: {
        curCredential: this.basicInfo.processCredentials,
      },
      list: [],
      listLoading: false,
      credentialRules: {
        curCredential: [{ required: true, message: this.$t('请选择凭证'), trigger: 'blur' }],
      },
    };
  },
  mounted() {
    this.loadCredentialList();
  },
  methods: {
    ...mapActions('template/', [
      'getCredentialList',
    ]),
    async loadCredentialList() {
      this.listLoading = true;
      const res = await this.getCredentialList({
        space_id: this.spaceId,
        ...this.scopeInfo,
        template_id: this.$route.params.templateId });
      this.list = res.data.results || [];
      this.listLoading = false;
    },
    handleSelectedCredential() {
      const transformedCredential = this.formData.curCredential.reduce((acc, item) => {
          acc[item.key] = {
            hook: item.hook,
            need_render: item.need_render,
            value: item.value,
          };
          return acc;
        }, {});
      this.$emit('changeCredential', transformedCredential) ;
    },
    validate() {
      if (this.$refs.credentialForm) {
        return this.$refs.credentialForm.validate();
      }
      return true;
    },
  },
};
</script>

<style lang="scss" scoped>
::v-deep .access-credential-form{
  .bk-label.has-desc>span {
    border-bottom: none !important;
  }
}
</style>
