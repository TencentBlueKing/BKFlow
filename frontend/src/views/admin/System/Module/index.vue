<template>
  <div
    v-bkloading="{ isLoading: listLoading }"
    class="system-module-list">
    <bk-button
      theme="primary"
      class="mb20"
      :disabled="listLoading"
      @click="handleEdit()">
      {{ $t('新增') }}
    </bk-button>
    <bk-table
      v-if="tableFields.length"
      :data="systemModuleList"
      :pagination="pagination"
      :max-height="tableMaxHeight"
      @page-change="handlePageChange"
      @page-limit-change="handlePageLimitChange">
      <bk-table-column
        v-for="field in tableFields"
        :key="field.key"
        :label="field.label"
        :prop="field.key"
        show-overflow-tooltip>
        <template slot-scope="{ row }">
          <span v-if="field.key === 'space_id'">{{ row[field.key] }}</span>
          <span v-else>{{ row[field.key] || '--' }}</span>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('操作')"
        fixed="right"
        width="200">
        <template slot-scope="{ row }">
          <bk-button
            theme="primary"
            text
            @click="handleEdit(row)">
            {{ $t('编辑') }}
          </bk-button>
          <bk-button
            theme="primary"
            class="ml10"
            text
            @click="handleDelete(row)">
            {{ $t('删除') }}
          </bk-button>
        </template>
      </bk-table-column>
      <NoData
        slot="empty"
        type="empty" />
    </bk-table>
    <NoData
      v-else
      slot="empty"
      type="empty" />
    <bk-dialog
      v-model="editDialogShow"
      theme="primary"
      :mask-close="false"
      header-position="left"
      :width="600"
      :esc-close="false"
      :show-footer="false"
      render-directive="if"
      :title="moduleFormData.id ? $t('编辑模块配置') : $t('新增模块配置')">
      <bk-form
        ref="editModuleForm"
        :label-width="130"
        :model="moduleFormData">
        <template v-for="field in tableFields">
          <bk-form-item
            v-if="field.key !== 'id'"
            :key="field.key"
            :label="field.label"
            :required="true"
            :rules="rules.required"
            :property="field.key">
            <bk-select
              v-if="field.choices"
              v-model="moduleFormData[field.key]">
              <bk-option
                v-for="option in field.choices"
                :id="option.value"
                :key="option.value"
                :name="option.text" />
            </bk-select>
            <bk-input
              v-else
              v-model="moduleFormData[field.key]"
              :type="field.key === 'space_id' ? 'number' : 'text'"
              :maxlength="getMaxLength(field.key)"
              :show-word-limit="true" />
          </bk-form-item>
        </template>
        <bk-form-item>
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
  import { mapActions } from 'vuex';
  import tableCommon from '../../Space/mixins/tableCommon.js';

  export default {
    name: 'SystemModuleList',
    components: {
      NoData,
    },
    mixins: [tableCommon],
    data() {
      return {
        systemModuleList: [],
        tableFields: [],
        deleting: false,
        editDialogShow: false,
        moduleFormData: {},
        editLoading: false,
        rules: {
          required: [
            {
              required: true,
              message: this.$t('必填项'),
              trigger: 'blur',
            },
          ],
        },
        defaultSelected: [],
        pageType: 'systemModuleList', // 页面类型，在mixins中分页表格头显示使用
      };
    },
    watch: {
      editDialogShow(val) {
        if (!val) {
          this.moduleFormData = {};
        }
      },
    },
    created() {
      this.getSystemModuleList();
    },
    methods: {
      ...mapActions('system/', [
        'getSystemModuleData',
        'updateSystemModule',
        'deleteSystemModule',
        'getSystemModuleMeta',
      ]),
      async getSystemModuleList() {
        try {
          if (this.listLoading) return;
          this.listLoading = true;
          const { limit, current } = this.pagination;
          const [resp1, resp2] = await Promise.all([
            this.getSystemModuleData({
              limit,
              offset: (current - 1) * limit,
            }),
            this.getSystemModuleMeta(),
          ]);
          this.tableFields = Object.keys(resp2.data).reduce((acc, key) => {
            const { verbose_name: value, choices } = resp2.data[key];
            acc.push({
              key,
              label: value,
              choices,
            });
            return acc;
          }, []);
          this.systemModuleList = resp1.data.results;
          this.pagination.count = resp1.data.count;
          const totalPage = Math.ceil(this.pagination.count / this.pagination.limit);
          if (!totalPage) {
            this.totalPage = 1;
          } else {
            this.totalPage = totalPage;
          }
        } catch (error) {
          console.warn(error);
        } finally {
          this.listLoading = false;
        }
      },
      // 编辑
      handleEdit(config) {
        if (config) {
          this.moduleFormData = { ...config };
        } else {
          this.moduleFormData = this.tableFields.reduce((acc, cur) => {
            acc[cur.key] = '';
            return acc;
          }, {});
        }
        this.editDialogShow = true;
      },
      // 确认编辑
      async handleEditConfirm() {
        this.$refs.editModuleForm.validate().then(async (validator) => {
          if (!validator) return;

          try {
            this.editLoading = true;
            const resp = await this.updateSystemModule({
              ...this.moduleFormData,
            });
            if (resp.result === false) return;

            this.getSystemModuleList();
            this.$bkMessage({
              message: this.moduleFormData.id ? this.$t('修改成功！') : this.$t('新增成功！'),
              theme: 'success',
            });
            this.editDialogShow = false;
          } catch (error) {
            console.warn(error);
          } finally {
            this.editLoading = false;
          }
        });
      },
      // 删除
      handleDelete(config) {
        const h = this.$createElement;
        this.$bkInfo({
          subHeader: h('div', { class: 'custom-header' }, [
            h('div', {
              class: 'custom-header-title',
              directives: [{
                name: 'bk-overflow-tips',
              }],
            }, [this.$t('确认删除模块" {0} " ?', [config.code])]),
          ]),
          extCls: 'dialog-custom-header-title',
          maskClose: false,
          width: 400,
          confirmLoading: true,
          cancelText: this.$t('取消'),
          confirmFn: async () => {
            await this.onDeleteConfirm(config.id);
          },
        });
      },
      // 确认删除
      async onDeleteConfirm(configId) {
        this.deleting = true;
        try {
          const resp = await this.deleteSystemModule({ id: configId });
          if (resp.result === false) return;

          // 最后一页最后一条删除后，往前翻一页
          if (
            this.pagination.current > 1
            && this.totalPage === this.pagination.current
            && this.pagination.count - (this.totalPage - 1) * this.pagination.limit === 1
          ) {
            this.pagination.current -= 1;
          }
          this.getSystemModuleList();
          this.$emit('updateUrl', { current: 1 });
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
      getMaxLength(key) {
        let length = key === 'url' ? 512 : '';
        length = ['code', 'token'].includes(key) ? 32 : length;
        return length;
      },
    },
  };
</script>
<style lang="scss" scoped>
  .system-module-list {
    /deep/.bk-table-empty-text {
      width: 100%;
    }
  }
</style>
