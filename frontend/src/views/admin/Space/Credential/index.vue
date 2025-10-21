<template>
  <div class="credential-list">
    <bk-button
      class="mb20"
      theme="primary"
      :disabled="listLoading || !spaceId"
      @click="isDialogShow = true">
      {{ $t("新建") }}
    </bk-button>
    <bk-table
      ref="credentialRef"
      v-bkloading="{ isLoading: listLoading }"
      :data="credentialList"
      :size="setting.size"
      :max-height="tableMaxHeight"
      :pagination="pagination"
      @page-change="handlePageChange"
      @page-limit-change="handlePageLimitChange"
      @filter-change="handleFilterChange"
      @sort-change="handleSortChange">
      <bk-table-column
        v-for="item in setting.selectedFields"
        :key="item.id"
        :label="item.label"
        :prop="item.id"
        :column-key="item.id"
        :width="item.width"
        :min-width="item.min_width"
        :fixed="item.fixed"
        :sortable="item.sortable ?? false"
        :filters="item.filters"
        :filter-method="item.filterMethod"
        :filter-multiple="item.filterMultiple ?? false"
        show-overflow-tooltip>
        <template slot-scope="{ row }">
          <div
            v-if="['operate'].includes(item.id)"
            class="operate-column">
            <bk-button
              theme="primary"
              text
              @click="handleOperate('edit', row)">
              {{ $t("编辑") }}
            </bk-button>
            <bk-button
              theme="primary"
              text
              @click="handleOperate('content', row)">
              {{ $t("查看内容") }}
            </bk-button>
            <bk-button
              theme="primary"
              text
              @click="handleOperate('scope', row)">
              {{ $t("作用域") }}
            </bk-button>
            <bk-button
              theme="primary"
              text
              @click="handleDelete(row)">
              {{ $t("删除") }}
            </bk-button>
          </div>
          <span
            v-else
            class="table-cell">
            {{ getTableCell(row, item) }}
          </span>
        </template>
      </bk-table-column>
      <bk-table-column
        type="setting"
        :tippy-options="{ zIndex: 3000 }">
        <bk-table-setting-content
          :fields="setting.fieldList"
          :size="setting.size"
          :selected="setting.selectedFields"
          @setting-change="handleSettingChange" />
      </bk-table-column>
      <div
        slot="empty"
        class="empty-data">
        <NoData
          class="exception-part"
          :type="renderEmptyType"
          :message="renderEmptyMessage"
          @searchClear="handleClearFilter" />
      </div>
    </bk-table>
    <CredentialDialog
      :is-show="isDialogShow"
      :detail="selectedRow"
      :space-id="spaceId"
      @confirm="handleCredentialDialogConfirm"
      @cancel="handleCredentialDialogCancel" />
    <!-- 查看内容 -->
    <CredentialContentDialog
      :is-show="isContentDialogShow"
      :detail="selectedRow"
      @cancel="handleCredentialDialogCancel" />
    <!-- 编辑凭证作用域 -->
    <CredentialScopeDialog
      :is-show="isScopeDialogShow"
      :detail="selectedRow"
      :space-id="spaceId"
      @confirm="handleCredentialDialogConfirm"
      @cancel="handleCredentialDialogCancel" />
  </div>
</template>

<script>
import { mapActions } from 'vuex';
import { CREDENTIAL_TYPE_LIST } from '@/constants';
import i18n from '@/config/i18n';
import tableHeader from '@/mixins/tableHeader';
import tableCommon from '../mixins/tableCommon';
import NoData from '@/components/common/base/NoData.vue';
import CredentialDialog from './components/CredentialDialog.vue';
import CredentialContentDialog from './components/CredentialContentDialog.vue';
import CredentialScopeDialog from './components/CredentialScopeDialog.vue';

export default {
  components: {
    NoData,
    CredentialDialog,
    CredentialContentDialog,
    CredentialScopeDialog,
  },
  mixins: [tableHeader, tableCommon],
  data() {
    return {
      CREDENTIAL_TYPE_LIST,
      credentialList: [],
      typeFilters: [],
      isDialogShow: false,
      isScopeDialogShow: false,
      isContentDialogShow: false,
      selectedRow: {},
      pageType: 'credentialList',
      tableFields: [],
      setting: {
        fieldList: this.getTableColumns,
        selectedFields: this.getTableColumns,
        size: 'small',
      },
      filterData: {
        type: '',
      },
    };
  },
  computed: {
    getTableColumns() {
      const tableFields = [
        {
          id: 'name',
          label: i18n.t('名称'),
          min_width: 250,
        },
        {
          id: 'desc',
          label: i18n.t('描述'),
          min_width: 200,
        },
        {
          id: 'type',
          label: i18n.t('类型'),
          width: 200,
          filters: CREDENTIAL_TYPE_LIST,
          filterMethod: this.getTypeFilterMethod,
          filterMultiple: false,
        },
        {
          id: 'creator',
          label: i18n.t('创建人'),
        },
        {
          id: 'create_at',
          label: i18n.t('创建时间'),
          width: 160,
          sortable: 'custom',
        },
        {
          id: 'updated_by',
          label: i18n.t('更新人'),
        },
        {
          id: 'update_at',
          label: i18n.t('更新时间'),
          width: 160,
          sortable: 'custom',
        },
        {
          id: 'operate',
          label: i18n.t('操作'),
          width: 220,
          fixed: 'right',
        },
      ];
      return tableFields;
    },
    renderEmptyType() {
      if (this.filterData.type) {
        return 'search-empty';
      }
      return 'empty';
    },
    renderEmptyMessage() {
      return this.filterData.type ? this.$t('搜索结果为空') : '';
    },
  },
  created() {
    this.setting = {
      fieldList: this.getTableColumns,
      selectedFields: this.getTableColumns,
      size: 'small',
    };
    this.getCredentialList();
  },
  methods: {
    ...mapActions('credentialConfig', [
      'loadCredentialList',
      'deleteCredential',
    ]),
    async getCredentialList() {
      try {
        if (!this.spaceId) return;
        this.listLoading = true;

        const { limit, current } = this.pagination;
        const { type, order_by: orderBy } = this.filterData;
        const resp = await this.loadCredentialList({
          space_id: this.spaceId,
          limit,
          offset: (current - 1) * limit,
          type: type || undefined,
          order_by: orderBy || undefined,
        });
        if (resp.data) {
          this.credentialList = resp.data.results;
          this.pagination.count = resp.data.count;
          const totalPage = Math.ceil(this.pagination.count / limit);
          if (!totalPage) {
            this.totalPage = 1;
          } else {
            this.totalPage = totalPage;
          }
        }
      } catch {
        this.credentialList = [];
        this.pagination.count = 0;
      } finally {
        this.listLoading = false;
      }
    },
    getTableCell(row, cell) {
      if (['type'].includes(cell.id)) {
        return CREDENTIAL_TYPE_LIST.find(item => item.value === row[cell.id])?.text ?? '--';
      }
      return row[cell.id] || '--';
    },
    getTypeFilterMethod(value, row, column) {
      const { property } = column;
      return row[property] === value;
    },
    handleFilterChange(filters) {
      this.filterData.type = filters.type.join();
      this.handleResetPagination(true);
    },
    handleSortChange(sort) {
      const { order, prop } = sort;
      this.filterData.order_by = '';
      if (order) {
        this.filterData.order_by = order.includes('ascending') ? prop : `-${prop}`;
      }
      this.handleResetPagination(true);
    },
    handleOperate(type = 'edit', row) {
      this.selectedRow = row;
      const typeMap = {
        edit: () => {
          this.isDialogShow = true;
        },
        content: () => {
          this.isContentDialogShow = true;
        },
        scope: () => {
          this.isScopeDialogShow = true;
        },
      };
      return typeMap[type]?.();
    },
    handleDelete(row) {
      this.$bkInfo({
        title: this.$t('凭证删除后不可恢复，确认删除？'),
        maskClose: false,
        width: 450,
        confirmLoading: true,
        cancelText: this.$t('取消'),
        confirmFn: async () => {
          await this.deleteCredential({
            id: row.id,
            space_id: this.spaceId,
          });

          // 最后一页最后一条删除后，往前翻一页
          if (
            this.pagination.current > 1
            && this.totalPage === this.pagination.current
            && this.pagination.count
              - (this.totalPage - 1) * this.pagination.limit
              === 1
          ) {
            this.pagination.current -= 1;
          }
          this.getCredentialList();
          this.$bkMessage({
            message: this.$t('删除成功！'),
            theme: 'success',
          });
        },
      });
    },
    handleClearFilter() {
      Object.assign(this.filterData, { type: '', order_by: '' });
      this.$refs.credentialRef.clearFilter();
      this.handleResetPagination(true);
    },
    handleResetPagination(isResetPage = false) {
      if (isResetPage) {
       this.pagination.current = 1;
      }
      this.handleCredentialDialogCancel();
      this.getCredentialList();
    },
    handleCredentialDialogConfirm(isResetPage) {
      this.handleResetPagination(isResetPage);
    },
    handleCredentialDialogCancel() {
      this.selectedRow = {};
      this.isDialogShow = false;
      this.isContentDialogShow = false;
      this.isScopeDialogShow = false;
    },
  },
};
</script>

<style lang="scss" scoped>
.operate-column {
  .bk-button-text {
    &:not(&:last-child) {
      margin-right: 16px;
    }
  }
}
::v-deep .content-form-item {
  .bk-form-content {
    height: 300px;
    .content-wrapper {
      position: relative;
      height: 100%;
    }
  }
}
::v-deep .bk-table-empty-text {
  width: 100%;
}
</style>
