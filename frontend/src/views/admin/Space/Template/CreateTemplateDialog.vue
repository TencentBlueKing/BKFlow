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
      <bk-form-item
        :label="$t('标签')"
        :required="true"
        :property="'labels'">
        <label-cascade
          :value="selectedLabels"
          scope="template"
          @change="handleSelected">
          <template #trigger="{ list, isShow }">
            <div :class="['cascade-trigger', { focus: isShow }]">
              <div class="label-list">
                <div
                  v-for="label in list"
                  :key="label.id"
                  class="label-item"
                  :style="{ 'background-color': label.color }">
                  {{ label.full_path }}
                  <bk-icon
                    class="delete-icon"
                    type="close"
                    @click="handleDeleteLabel(label.id)" />
                </div>
              </div>
              <bk-icon
                :class="['angle-icon', { 'is-show': isShow }]"
                type="angle-down" />
            </div>
          </template>
        </label-cascade>
      </bk-form-item>
      <bk-form-item>
        <bk-button
          theme="primary"
          :loading="createLoading"
          @click="createTemplateConfirm">
          {{ $t("提交") }}
        </bk-button>
        <bk-button
          ext-cls="mr5"
          theme="default"
          :disabled="createLoading"
          @click="$emit('close')">
          {{ $t("取消") }}
        </bk-button>
      </bk-form-item>
    </bk-form>
  </bk-dialog>
</template>

<script>
import { NAME_REG, STRING_LENGTH } from '@/constants/index.js';
import { mapActions, mapState } from 'vuex';
import LabelCascade from '../common/LabelCascade.vue';
export default {
    name: 'CreateTemplateDialog',
    components: {
        LabelCascade,
    },
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
                label_ids: [],
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
            selectedLabels: [],
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
                        label_ids: [],
                    };
                }
                this.showCreateTplDialog = val;
            },
            immediate: true,
        },
    },
    methods: {
        ...mapActions('template/', ['createTemplate']),
        createTemplateConfirm() {
            this.$refs.createTemplateForm.validate().then(async (validator) => {
                if (!validator) {
                    this.createLoading = false;
                    return;
                }
                try {
                    this.createLoading = true;
                    const data = { spaceId: this.spaceId };
                    data.params = Object.keys(this.templateFormData).reduce(
                        (acc, cur) => {
                            const value = this.templateFormData[cur];
                            if (value) {
                                acc[cur] = value;
                            }
                            return acc;
                        },
                        {}
                    );
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
        handleSelected(val) {
            this.selectedLabels = val;
            this.templateFormData.label_ids = val.map(item => item.id);
        },
        handleDeleteLabel(val) {
            this.selectedLabels = this.selectedLabels.filter(item => item.id !== val);
            this.templateFormData.label_ids =                this.templateFormData.label_ids.filter(item => item !== val);
        },
    },
};
</script>

<style lang="scss" scoped>
.cascade-trigger {
    display: flex;
    align-items: center;
    width: 411px;
    padding: 0 0 0 8px;
    background: #ffffff;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
    &.focus {
        border-color: #3a84ff;
    }
    .label-list {
        flex: 1;
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 6px;
        height: 100%;
        min-height: 32px;
        padding: 7px 0 9px 0;
        .label-item {
            height: 16px;
            font-size: 10px;
            display: flex;
            align-items: center;
            padding: 0 4px;
            border-radius: 11px;
            color: #ffffff;
            .delete-icon {
                font-size: 16px !important;
                margin-left: 5px;
                cursor: pointer;
            }
        }
    }
    .angle-icon {
        width: 30px;
        height: 100%;
        font-size: 16px !important;
        color: #979ba5;
        &.is-show {
            transform: rotate(180deg);
        }
    }
}
</style>
