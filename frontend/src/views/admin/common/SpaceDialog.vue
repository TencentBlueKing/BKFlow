<template>
  <bk-dialog
    :value="isShow"
    theme="primary"
    :mask-close="false"
    header-position="left"
    :width="620"
    :esc-close="false"
    :show-footer="false"
    render-directive="if"
    :title="spaceFormData.id ? $t('编辑空间配置') : $t('新增空间配置')"
    @cancel="onCancel">
    <bk-form
      ref="spaceForm"
      :label-width="150"
      :model="spaceFormData">
      <template v-for="field in fields">
        <bk-form-item
          v-if="field.key !== 'id' || spaceFormData.id"
          :key="field.key"
          :label="field.label"
          :required="true"
          :rules="rules.required"
          :property="field.key">
          <bk-select
            v-if="field.choices"
            v-model="spaceFormData[field.key]">
            <bk-option
              v-for="option in field.choices"
              :id="option.value"
              :key="option.value"
              :name="option.text" />
          </bk-select>
          <bk-input
            v-else
            v-model="spaceFormData[field.key]"
            :disabled="field.key === 'id'"
            :maxlength="getMaxLength(field.key)"
            :show-word-limit="true"
            :placeholder="field.placeholder || ''" />
        </bk-form-item>
      </template>
      <bk-form-item>
        <bk-button
          theme="primary"
          :loading="editLoading"
          @click="onSubmit">
          {{ $t('提交') }}
        </bk-button>
        <bk-button
          ext-cls="mr5"
          theme="default"
          :disabled="editLoading"
          @click="onCancel">
          {{ $t('取消') }}
        </bk-button>
      </bk-form-item>
    </bk-form>
  </bk-dialog>
</template>
<script>
  import { mapActions } from 'vuex';
  import bus from '@/utils/bus.js';
  import i18n from '@/config/i18n/index.js';
  export default {
    name: 'SpaceDialog',
    props: {
      isShow: {
        type: Boolean,
        default: false,
      },
      fields: {
        type: Array,
        default: () => ([
          {
            key: 'name',
            label: i18n.t('空间名称'),
          },
          {
            key: 'app_code',
            label: 'APP Code',
            placeholder: i18n.t('仅支持您是开发者的 app_code'),
          },
          {
            key: 'desc',
            label: i18n.t('空间描述'),
          },
          {
            key: 'platform_url',
            label: i18n.t('平台提供服务的地址'),
            placeholder: i18n.t('请提供以 https:// 或 http:// 开头的服务地址'),
          },
        ]),
      },
      spaceInfo: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        spaceFormData: {},
        rules: {
          required: [
            {
              required: true,
              message: i18n.t('必填项'),
              trigger: 'blur',
            },
          ],
        },
        editLoading: false,
      };
    },
    watch: {
      isShow: {
        handler(val) {
          if (val) {
            this.spaceFormData = this.fields.reduce((acc, cur) => {
              acc[cur.key] = this.spaceInfo[cur.key] || '';
              return acc;
            }, {});
          }
        },
        immediate: true,
      },
    },
    methods: {
      ...mapActions('system/', [
        'updateSpaceConfig',
      ]),
      async onSubmit() {
        this.$refs.spaceForm.validate().then(async (validator) => {
          if (!validator) return;

          try {
            this.editLoading = true;
            const resp = await this.updateSpaceConfig(this.spaceFormData);
            if (resp.result === false) return;

            this.$emit('close', resp.data.id);
            bus.$emit('updateSpaceList');
            this.$bkMessage({
              message: this.spaceFormData.id ? this.$t('修改成功！') : this.$t('新增成功！'),
              theme: 'success',
            });
          } catch (error) {
            console.warn(error);
          } finally {
            this.editLoading = false;
          }
        });
      },
      getMaxLength(key) {
        let length = ['name', 'app_code'].includes(key) ? 32 : '';
        length = key === 'desc' ? 128 : length;
        length = key === 'platform_url' ? 265 : length;
        return length;
      },
      onCancel() {
        this.$emit('close');
      },
    },
  };
</script>
<style lang="scss">

</style>
