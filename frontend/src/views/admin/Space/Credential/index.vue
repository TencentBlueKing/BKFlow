<template>
  <div class="credential-list">
    <bk-button
      class="mb20"
      theme="primary"
      :disabled="listLoading || !spaceId"
      @click="isDialogShow = true">
      {{ $t('新建') }}
    </bk-button>
    <bk-table
      v-bkloading="{ isLoading: listLoading }"
      :data="credentialList"
      :max-height="tableMaxHeight"
      :pagination="pagination"
      @page-change="handlePageChange"
      @page-limit-change="handlePageLimitChange">
      <bk-table-column
        v-for="item in tableFields"
        :key="item.id"
        :label="item.label"
        :prop="item.id"
        :render-header="renderTableHeader"
        :width="item.width"
        show-overflow-tooltip
        :min-width="item.min_width">
        <template slot-scope="{ row }">
          <span class="table-cell">{{ row[item.id] || '--' }}</span>
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
            text
            @click="handleDelete(row)">
            {{ $t('删除') }}
          </bk-button>
        </template>
      </bk-table-column>
      <div
        slot="empty"
        class="empty-data">
        <NoData type="empty" />
      </div>
    </bk-table>
    <CredentialDialog
      :is-show="isDialogShow"
      :row="selectedRow"
      :space-id="spaceId"
      @confirm="handleCredentialDialogConfirm"
      @cancel="handleCredentialDialogCancel" />
  </div>
</template>
<script>
  import { mapActions } from 'vuex';
  import tableHeader from '@/mixins/tableHeader.js';
  import tableCommon from '../mixins/tableCommon.js';
  import NoData from '@/components/common/base/NoData.vue';
  import CredentialDialog from './CredentialDialog.vue';
  import i18n from '@/config/i18n/index.js';

  const TABLE_FIELDS = [
    {
      id: 'name',
      label: i18n.t('名称'),
      min_width: 250,
    },
    {
      id: 'desc',
      label: i18n.t('描述'),
      disabled: true,
      width: 250,
    },
    {
      id: 'type',
      label: i18n.t('类型'),
      width: 100,
    },
    {
      id: 'content',
      label: i18n.t('内容'),
      min_width: 250,
    },
    {
      id: 'creator',
      label: i18n.t('创建人'),
      width: 160,
    },
    {
      id: 'create_at',
      label: i18n.t('创建时间'),
      width: 280,
    },
    {
      id: 'updated_by',
      label: i18n.t('更新人'),
      width: 160,
    },
    {
      id: 'update_at',
      label: i18n.t('更新时间'),
      width: 280,
    },
  ];

  export default {
    components: {
      NoData,
      CredentialDialog,
    },
    mixins: [tableHeader, tableCommon],
    data() {
      return {
        credentialList: [],
        tableFields: TABLE_FIELDS,
        isDialogShow: false,
        selectedRow: {},
        pageType: 'credentialList',
      };
    },
    created() {
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
          const resp = await this.loadCredentialList({
            space_id: this.spaceId,
            limit,
            offset: (current - 1) * limit,
          });

          this.credentialList = resp.data.results;
          this.pagination.count = resp.data.count;
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
      handleEdit(row) {
        this.selectedRow = row;
        this.isDialogShow = true;
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
              && this.pagination.count - (this.totalPage - 1) * this.pagination.limit === 1
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
      handleCredentialDialogConfirm() {
        this.handleCredentialDialogCancel();
        this.getCredentialList();
      },
      handleCredentialDialogCancel() {
        this.selectedRow = {};
        this.isDialogShow = false;
      },
    },
  };
</script>
<style lang="scss" scoped>
  /deep/.content-form-item {
    .bk-form-content {
      height: 300px;
      .content-wrapper {
        position: relative;
        height: 100%;
      }
    }
  }
  /deep/.bk-table-empty-text {
    width: 100%;
  }
</style>
