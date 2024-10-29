<template>
  <div class="space-config-list">
    <bk-table
      v-bkloading="{ isLoading: listLoading }"
      :data="spaceConfigList"
      :max-height="tableMaxHeight">
      <bk-table-column
        v-for="item in tableFields"
        :key="item.id"
        :label="item.label"
        :prop="item.id"
        show-overflow-tooltip>
        <template slot-scope="{ row }">
          <span :class="['table-cell', { 'is-disabled': row.isDefault }]">{{ row[item.id] || '--' }}</span>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('操作')"
        fixed="right"
        width="200">
        <template slot-scope="{ row }">
          <bk-button
            theme="primary"
            class="mr10"
            text
            @click="handleEdit(row)">
            {{ $t('编辑') }}
          </bk-button>
          <bk-button
            theme="primary"
            :disabled="row.isDefault"
            text
            @click="handleDelete(row)">
            {{ $t('恢复默认值') }}
          </bk-button>
        </template>
      </bk-table-column>
      <NoData
        slot="empty"
        type="empty" />
    </bk-table>
    <bk-dialog
      v-model="editDialogShow"
      theme="primary"
      :mask-close="false"
      header-position="left"
      :width="600"
      :esc-close="false"
      :show-footer="false"
      render-directive="if"
      :title="$t('编辑配置')">
      <bk-form
        ref="editConfigForm"
        :label-width="100"
        :rules="rules"
        :model="configFormData">
        <bk-form-item label="Name">
          {{ selectedRow.name }}
        </bk-form-item>
        <bk-form-item :label="$t('说明')">
          {{ selectedRow.desc }}
        </bk-form-item>
        <bk-form-item
          :label="$t('值')"
          :property="'formValue'"
          :required="true"
          :class="{ 'code-form-item': configFormData.formType === 'json' }">
          <div
            v-if="configFormData.formType === 'json'"
            class="code-wrapper">
            <FullCodeEditor
              ref="fullCodeEditor"
              v-model="configFormData.formValue"
              style="height: 300px;"
              :options="{ language: 'json', placeholder: selectedRow.example }" />
          </div>
          <bk-select
            v-else-if="configFormData.formType === 'select'"
            v-model="configFormData.formValue"
            :placeholder="selectedRow.example">
            <bk-option
              v-for="option in selectedRow.choices"
              :id="option"
              :key="option"
              :name="option" />
          </bk-select>
          <bk-input
            v-else
            v-model="configFormData.formValue"
            :placeholder="selectedRow.example" />
        </bk-form-item>
        <bk-form-item class="mt20">
          <bk-button
            theme="primary"
            :loading="editLoading"
            @click="handleEditConfirm">
            {{ $t('提交') }}
          </bk-button>
          <bk-button
            ext-cls="mr5"
            theme="default"
            :disabled="editLoading"
            @click="editDialogShow = false">
            {{ $t('取消') }}
          </bk-button>
        </bk-form-item>
      </bk-form>
    </bk-dialog>
  </div>
</template>
<script>
  import NoData from '@/components/common/base/NoData.vue';
  import FullCodeEditor from '@/components/common/FullCodeEditor.vue';
  import { mapActions } from 'vuex';
  import i18n from '@/config/i18n/index.js';
  import tools from '@/utils/tools.js';

  const TABLE_FIELDS = [
    {
      id: 'name',
      label: i18n.t('名字'),
    },
    {
      id: 'desc',
      label: i18n.t('说明'),
    },
    {
      id: 'valueText',
      label: i18n.t('值'),
    },
  ];

  export default {
    name: 'SpaceConfigList',
    components: {
      NoData,
      FullCodeEditor,
    },
    props: {
      spaceId: {
        type: [String, Number],
        default: '',
      },
      hasAlertNotice: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        listLoading: false,
        spaceConfigList: [],
        tableFields: TABLE_FIELDS,
        selectedRow: {},
        deleting: false,
        editDialogShow: false,
        configFormData: {
          formType: '',
          formValue: '',
        },
        editLoading: false,
        rules: {
          formValue: [{
            required: true,
            message: this.$t('必填项'),
            trigger: 'change',
          }],
        },
      };
    },
    computed: {
      tableMaxHeight() {
        let maxHeight = window.innerHeight - 154;
        if (this.hasAlertNotice) {
          maxHeight -= 40;
        }
        return maxHeight;
      },
    },
    watch: {
      spaceId: {
        handler() {
          this.getSpaceConfigList();
        },
        immediate: true,
      },
      editDialogShow(val) {
        if (!val) {
          this.configFormData = {
            formType: '',
            formValue: '',
          };
        }
      },
    },
    methods: {
      ...mapActions('spaceConfig/', [
        'getSpaceConfigData',
        'updateSpaceConfig',
        'deleteSpaceConfig',
        'getSpaceConfigMeta',
      ]),
      // 空间配置列表
      async getSpaceConfigList() {
        if (!this.spaceId) return;
        try {
          this.listLoading = true;
          const [resp1, resp2] = await Promise.all([
            this.getSpaceConfigData({ space_id: this.spaceId }),
            this.getSpaceConfigMeta({ space_id: this.spaceId }),
          ]);
          const list = Object.values(resp2.data).reduce((acc, cur) => {
            const configData = resp1.data.find(item => item.name === cur.name);
            if (configData) {
              const { value_type: type, value, json_value: jsonValue } = configData;
              const valueText = type === 'TEXT' ? value : JSON.stringify(jsonValue);
              acc.push({
                ...cur,
                ...configData,
                valueText,
              });
            } else {
              acc.push({
                ...cur,
                valueText: cur.default_value,
                isDefault: true,
              });
            }
            return acc;
          }, []);
          list.sort((a, b) => {
            let result = a.isDefault ? 1 : -1;
            result = a.isDefault === b.isDefault ? 0 : result;
            return result;
          });
          this.spaceConfigList = list;
        } catch (error) {
          console.warn(error);
        } finally {
          this.listLoading = false;
        }
      },
      // 编辑
      handleEdit(row) {
        this.selectedRow = row;
        const {
          value_type: valueType,
          choices,
          value,
          json_value: jsonValue = {},
          isDefault,
        } = row;
        // 表单类型
        let formType = valueType === 'JSON' ? 'json' : 'input';
        formType = choices ? 'select' : formType;
        // 表单值
        let formValue;
        if (isDefault) {
          const { default_value: defaultValue } = row;
          formValue = formType === 'json' && defaultValue ? JSON.stringify(defaultValue, null, 4) : defaultValue;
        } else {
          formValue = formType === 'json' && jsonValue ? JSON.stringify(jsonValue, null, 4) : value;
        }
        formValue = formValue || '';
        this.configFormData = {
          formType,
          formValue,
        };
        this.editDialogShow = true;
        setTimeout(() => {
          const editorInstance = this.$refs.fullCodeEditor;
          if (editorInstance) {
            editorInstance.layoutCodeEditorInstance();
          }
        });
      },
      // 确认修改
      async handleEditConfirm() {
        this.$refs.editConfigForm.validate().then(async (validator) => {
          if (!validator) return;
          // 检查值数据类型
          const { formType, formValue } = this.configFormData;
          if (formType === 'json' && !tools.checkIsJSON(formValue)) {
            this.$bkMessage({
              message: this.$t('数据格式不正确，应为JSON格式'),
              theme: 'error',
            });
            return;
          }

          try {
            this.editLoading = true;
            const { id, name, value_type: valueType  } = this.selectedRow;
            const data = {
              id,
              name,
              space_id: this.spaceId,
              value_type: valueType,
            };
            if (formType === 'json') {
              data.json_value = JSON.parse(formValue);
            } else {
              data.text_value = formValue;
            }
            const resp = await this.updateSpaceConfig(data);
            if (resp.result === false) return;

            this.editDialogShow = false;
            this.getSpaceConfigList();
            this.$bkMessage({
              message: this.$t('修改成功！'),
              theme: 'success',
            });
          } catch (error) {
            console.warn(error);
          } finally {
            this.editLoading = false;
          }
        });
      },
      // 删除
      handleDelete(row) {
        const h = this.$createElement;
        this.$bkInfo({
          subHeader: h('div', { class: 'custom-header' }, [
            h('div', {
              class: 'custom-header-title',
              directives: [{
                name: 'bk-overflow-tips',
              }],
            }, [this.$t('确认" {0} "恢复默认值?', [row.name])]),
          ]),
          extCls: 'dialog-custom-header-title',
          maskClose: false,
          width: 400,
          confirmLoading: true,
          cancelText: this.$t('取消'),
          confirmFn: async () => {
            await this.onDeleteConfirm(row.id);
          },
        });
      },
      // 确认删除
      async onDeleteConfirm(configId) {
        this.deleting = true;
        try {
          const resp = await this.deleteSpaceConfig({ id: configId });
          if (resp.result === false) return;

          this.getSpaceConfigList();
          this.$bkMessage({
            message: this.$t('删除成功！'),
            theme: 'success',
          });
        } catch (e) {
          console.log(e);
        } finally {
          this.deleting = false;
        }
      },
      handlePageChange(val) {
        this.pagination.current = val;
        this.getSpaceConfigList();
      },
      handlePageLimitChange(val) {
        this.pagination.limit = val;
        this.pagination.current = 1;
        this.getSpaceConfigList();
      },
    },
  };
</script>
<style lang="scss" scoped>
/deep/.code-form-item {
    .bk-form-content {
      height: 300px;
      .code-wrapper {
        position: relative;
        height: 100%;
      }
    }
  }
  .space-config-list {
    /deep/.bk-table-empty-text {
      width: 100%;
    }
    /deep/.table-cell {
      display: inline-block;
      overflow : hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      &.is-disabled {
        color: #dcdee5;
      }
    }
  }
</style>
