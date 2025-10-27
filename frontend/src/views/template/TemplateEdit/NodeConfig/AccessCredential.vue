<template>
  <div class="access-credential">
    <bk-form
      ref="credentialForm"
      :label-width="130"
      :model="formData"
      :rules="credentialFormRules">
      <bk-form-item
        :label="$t('选择凭证')"
        :required="true"
        property="curSelectedCredential">
        <bk-select
          v-model="formData.curSelectedCredential"
          v-bkloading="{ isLoading: listLoading, zIndex: 100 }"
          ext-cls="select-credential"
          :disabled="isViewMode"
          multiple
          display-tag
          :auto-height="false"
          :placeholder="$t('请选择凭证')"
          @selected="handleSelectedCredential">
          <bk-option
            v-for="option in list"
            :id="option.id"
            :key="option.key"
            v-bk-tooltips="{ content: option.desc, placement: 'left-start' }"
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
        curSelectedCredential: [],
      },
      credentialFormRules: {
        curSelectedCredential: [
          { required: true, message: this.$t('请选择凭证'), trigger: 'change' },
        ],
      },
      list: [],
      listLoading: false,
    };
  },
  watch: {
    basicInfo: {
      handler(val) {
        if (val?.credentials) {
          this.formData.curSelectedCredential = [];
          const credKeys = Object.keys(this.basicInfo.credentials);
          if (credKeys.length > 0) {
            for (const item of credKeys) {
                const curItemValue = val.credentials[item].value;
               this.formData.curSelectedCredential.push(curItemValue);
            }
          }
        }
      },
      deep: true,
      immediate: true,
    },
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
      const res = await this.getCredentialList({ space_id: this.spaceId, ...this.scopeInfo });
      this.list = res.data.results || [];
      this.listLoading = false;
    },
    handleSelectedCredential(value) {
      const curCredentials = {};
      value?.forEach((id) => {
        const selectedItem = this.list.find(item => item.id === id);
        if (selectedItem) {
          curCredentials[selectedItem.name] = {
            hook: false,
            need_render: true,
            value: selectedItem.id,
          };
        }
      });
      this.$emit('changeCredential', curCredentials) ;
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

</style>
