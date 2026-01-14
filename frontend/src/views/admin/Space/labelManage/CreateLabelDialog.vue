<template>
  <bk-dialog
    v-model="showCreateDialog"
    theme="primary"
    :mask-close="false"
    header-position="left"
    :width="640"
    render-directive="if"
    :title="isEdit ? $t('编辑标签') : $t('新增标签')"
    @cancel="$emit('close')">
    <bk-form
      ref="createLabelForm"
      :model="labelFormData"
      :label-width="100"
      :rules="rules">
      <bk-form-item
        :label="$t('标签名称')"
        :required="true"
        :property="'name'">
        <bk-input
          v-model="labelFormData.name"
          :maxlength="stringLength.TEMPLATE_NAME_MAX_LENGTH" />
      </bk-form-item>
      <bk-form-item
        :label="$t('标签颜色')"
        :required="true"
        :property="'color'">
        <bk-color-picker
          v-model="labelFormData.color"
          :recommend="labelColorList" />
      </bk-form-item>
      <bk-form-item
        :label="$t('标签描述')"
        :required="true"
        :property="'description'">
        <bk-input
          v-model="labelFormData.description"
          :show-word-limit="true"
          :type="'textarea'"
          :rows="3"
          :maxlength="500" />
      </bk-form-item>
      <bk-form-item
        v-if="!scope"
        :label="$t('标签范围')"
        :required="true"
        :property="'label_scope'">
        <bk-checkbox-group
          v-model="labelFormData.label_scope"
          class="scope-checkbox">
          <bk-checkbox :value="'task'">
            {{ $t("任务") }}
          </bk-checkbox>
          <bk-checkbox :value="'template'">
            {{ $t("流程") }}
          </bk-checkbox>
        </bk-checkbox-group>
      </bk-form-item>
    </bk-form>
    <template #footer>
      <bk-button
        theme="primary"
        :loading="confirmLoading"
        @click="handleConfirm">
        {{ $t("确认") }}
      </bk-button>
      <bk-button
        ext-cls="mr5"
        theme="default"
        :disabled="confirmLoading"
        @click="$emit('close')">
        {{ $t("取消") }}
      </bk-button>
    </template>
  </bk-dialog>
</template>

<script>
import { STRING_LENGTH, LABEL_COLOR_LIST } from '@/constants/index.js';
import { mapActions, mapState } from 'vuex';
export default {
    name: 'CreateTemplateDialog',
    props: {
        isShow: {
            type: Boolean,
            default: false,
        },
        isEdit: {
            type: Boolean,
            default: false,
        },
        labelData: {
            type: Object,
            default: () => ({}),
        },
        scope: {
            type: String,
            default: '',
        },
    },
    data() {
        return {
            showCreateDialog: false,
            labelFormData: {
                name: '',
                color: '#1C9574',
                description: '',
                label_scope: ['task', 'template'],
            },
            stringLength: STRING_LENGTH,
            confirmLoading: false,
            labelColorList: LABEL_COLOR_LIST,
            editLabelId: 0,
            rules: {
                name: [
                    {
                        required: true,
                        message: this.$t('必填项'),
                        trigger: 'blur',
                    },
                ],
                description: [
                    {
                        required: true,
                        message: this.$t('必填项'),
                        trigger: 'blur',
                    },
                ],
            },
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
                    this.labelFormData = {
                        name: '',
                        color: '#1C9574',
                        description: '',
                        label_scope: this.scope ? [this.scope] : ['task', 'template'],
                    };
                } else {
                    if (this.isEdit) {
                        this.labelFormData = {
                            name: this.labelData.name,
                            color: this.labelData.color,
                            description: this.labelData.description,
                            label_scope: this.labelData.label_scope,
                            parent_id: this.labelData.parent_id,
                        };
                        this.editLabelId = this.labelData.id;
                    }
                }
                this.showCreateDialog = val;
            },
            immediate: true,
        },
    },
    methods: {
        ...mapActions('label/', ['createLabel', 'updateLabel']),
        async validate() {
            return await this.$refs.createLabelForm.validate();
        },
        async handleConfirm() {
            const isValid = await this.validate();
            if (!isValid) return;
            this.confirmLoading = true;
            try {
                const payload = {
                    ...this.labelFormData,
                    space_id: this.spaceId,
                };

                if (this.isEdit) {
                    await this.updateLabel({
                        id: this.editLabelId,
                        data: payload,
                    });
                } else {
                    await this.createLabel(payload);
                }

                this.$emit('updateList');
                this.$emit('close');
            } catch (error) {
                console.warn(error);
            } finally {
                this.confirmLoading = false;
            }
        },
    },
};
</script>

<style lang="scss" scoped>
.scope-checkbox {
    .bk-form-checkbox {
        margin-right: 24px;
    }
}
</style>
