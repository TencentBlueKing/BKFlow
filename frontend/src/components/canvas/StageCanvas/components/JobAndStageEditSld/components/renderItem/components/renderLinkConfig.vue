<template>
  <div class="render-link-config">
    <bk-form
      ref="configForm"
      :model="renderDataSync"
      :rules="rules">
      <bk-form-item
        property="url"
        label="超链接"
        style="margin-top: 8px;"
        required>
        <bk-input
          v-model="renderDataSync.url"
          :disabled="!editable" />
      </bk-form-item>
    </bk-form>
  </div>
</template>

<script>
export default {
    name: 'RenderLinkConfig',
    props: {
        renderData: {
            type: Object,
            required: true,
        },
        editable: {
          type: Boolean,
          default: false,
      },
    },
    data() {
        return {

            rules: {
              url: [
                  {
                    trigger: 'blur',
                    message: '请输入有效的链接',
                    validator: () => !!this.renderDataSync.url,
                  },
                ],
            },
        };
    },
    computed: {
        renderDataSync: {
            get() {
                return this.renderData;
            },
            set(value) {
                this.$emit('update:renderData', value);
            },
        },

    },

    methods: {
        async validate() {
            return await this.$refs.configForm.validate();
        },
    },
};
</script>

<style lang="scss" scoped>
</style>
