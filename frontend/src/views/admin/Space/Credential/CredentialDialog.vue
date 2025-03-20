<template>
  <bk-dialog
    :value="isShow"
    theme="primary"
    :mask-close="false"
    header-position="left"
    :width="600"
    :esc-close="false"
    :show-footer="false"
    render-directive="if"
    :title="row.id ? $t('编辑凭证') : $t('新建凭证')"
    @cancel="onCancel">
    <bk-form
      ref="credentialFormRef"
      :label-width="100"
      :model="formData">
      <bk-form-item
        :label="$t('名称')"
        :required="true"
        property="name"
        :rules="rules.required">
        <bk-input v-model="formData.name" />
      </bk-form-item>
      <bk-form-item
        :label="$t('描述')"
        :required="true"
        property="desc"
        :rules="rules.required">
        <bk-input v-model="formData.desc" />
      </bk-form-item>
      <bk-form-item :label="$t('类型')">
        <bk-input
          readonly
          :value="'BK_APP'" />
      </bk-form-item>
      <bk-form-item
        :label="$t('内容')"
        property="content"
        :required="true"
        :rules="rules.required"
        class="content-form-item">
        <div
          class="content-wrapper">
          <FullCodeEditor
            ref="fullCodeEditor"
            v-model="formData.content"
            style="height: 300px;"
            :options="{ language: 'json', placeholder: contentPlaceholder }" />
        </div>
      </bk-form-item>
      <bk-form-item class="mt20">
        <bk-button
          theme="primary"
          :loading="confirmLoading"
          @click="handleConfirm">
          {{ row.id ? $t('保存') : $t('提交') }}
        </bk-button>
        <bk-button
          ext-cls="mr5"
          theme="default"
          :disabled="confirmLoading"
          @click="onCancel">
          {{ $t('取消') }}
        </bk-button>
      </bk-form-item>
    </bk-form>
  </bk-dialog>
</template>
<script>
import FullCodeEditor from '@/components/common/FullCodeEditor.vue';
import { mapActions } from 'vuex';
export default {
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
    spaceId: {
      type: [String, Number],
      default: '',
    },
  },
  data() {
    return {
      formData: {
        name: '',
        desc: '',
        content: '',
      },
      rules: {
        required: [{
          required: true,
          message: this.$t('必填项'),
          trigger: 'change',
        }],
      },
      confirmLoading: false,
      contentPlaceholder: {
        bk_app_code: 'xxxxxx',
        bk_app_secret: 'xxxxxx',
      },
    };
  },
  watch: {
    row: {
      handler(val) {
        this.formData = Object.keys(this.formData).reduce((acc, key) => Object.assign(acc, {
          [key]: key === 'content' ? val[key] && JSON.stringify(val[key], null, 4) : val[key],
        }), {});
      },
      deep: true,
    },
  },
  methods: {
    ...mapActions('credentialConfig', [
      'createCredential',
      'updateCredential',
    ]),
    async handleConfirm() {
      try {
        await this.$refs.credentialFormRef.validate();

        this.confirmLoading = true;
        const { id } = this.row;
        const params = Object.assign(this.formData, {
          id,
          type: 'BK_APP',
          content: JSON.parse(this.formData.content),
          space_id: this.spaceId,
        });

        let resp = {};
        if (id) {
          resp = await this.updateCredential(params);
        } else {
          resp = await this.createCredential(params);
        }
        if (!resp.result) return;

        this.$bkMessage({
          message: id ? this.$t('修改成功！') : this.$t('新增成功！'),
          theme: 'success',
        });
        this.$emit('confirm');
      } catch (error) {
        console.warn(error);
      } finally {
        this.confirmLoading = false;
      };
    },
    onCancel() {
      this.$emit('cancel');
    },
  },
};
</script>
