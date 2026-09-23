<template>
  <bk-dialog
    :value="isShow"
    theme="primary"
    :mask-close="false"
    header-position="left"
    :width="640"
    :esc-close="false"
    :show-footer="false"
    :title="$t('查看内容')"
    render-directive="if"
    @cancel="handleCancel">
    <div class="content-wrapper">
      <FullCodeEditor
        ref="fullCodeEditor"
        v-model="formData.content"
        style="height: 514px"
        :options="{ language: 'json', placeholder: contentPlaceholder }" />
    </div>
  </bk-dialog>
</template>

<script>
import FullCodeEditor from '@/components/common/FullCodeEditor.vue';
export default {
  components: {
    FullCodeEditor,
  },
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    detail: {
      type: Object,
      default: () => {},
    },
  },
  data() {
    return {
      formData: {
        content: '',
      },
      contentPlaceholder: {
        bk_app_code: 'xxxxxx',
        bk_app_secret: 'xxxxxx',
      },
    };
  },
  watch: {
    detail: {
      handler(rowData) {
        if (Object.keys(rowData).length) {
          this.formData.content = JSON.stringify(rowData.content, null, 4);
        }
      },
      deep: true,
    },
  },
  methods: {
    handleCancel() {
      this.$emit('cancel');
    },
  },
};
</script>
