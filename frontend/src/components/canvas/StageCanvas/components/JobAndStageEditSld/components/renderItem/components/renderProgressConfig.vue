<template>
  <div class="render-progess-config">
    <bk-form
      ref="configForm"
      :model="renderDataSync"
      :rules="rules">
      <bk-form-item
        label="数值范围"
        property="range">
        <div class="data-range-container">
          <bk-input
            v-model="startValue"
            style="width: 120px;" />
          <span class="from-to">至</span>
          <bk-input
            v-model="endValue"
            style="width: 120px;margin-right: 8px;" />
          <bk-color-picker
            v-model="renderDataSync.color"
            class="color-picker"
            :show-value="false" />
        </div>
      </bk-form-item>
    </bk-form>
  </div>
</template>

<script>
export default {
    name: 'RenderProgessConfig',
    props: {
        renderData: {
            type: Object,
            required: true,
        },
    },
    data() {
        return {
            rules: {
                range: [
                  {
                    trigger: 'blur',
                    message: '请输入有效的数值范围',
                    validator: () => this.renderData.range.findIndex(item => item === '' || isNaN(item)) === -1,
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
        startValue: {
            get() {
                return this.renderDataSync.range[0];
            },
            set(value) {
                this.$set(this.renderDataSync.range, '0', value);
            },
        },
        endValue: {
            get() {
                return this.renderDataSync.range[1];
            },
            set(value) {
                this.$set(this.renderDataSync.range, '1', value);
            },
        },
    },
    created() {
        if (!this.renderDataSync.color) {
            this.$set(this.renderDataSync, 'color', '#3A83FF');
        }
        if (!this.renderDataSync.range) {
            this.$set(this.renderDataSync, 'range', ['', '']);
        }
    },
    methods: {
        async validate() {
            return await this.$refs.configForm.validate();
        },
    },
};
</script>

<style lang="scss" scoped>
.render-progess-config {
    .data-range-container{
        font-size: 12px;
        display: flex;
        align-items: center;
        .from-to{
            margin: 0 8px;
        }
    }
}
</style>
