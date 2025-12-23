<template>
  <div class="decision-table-list">
    <table-operate
      ref="tableOperate"
      :space-id="spaceId"
      :placeholder="$t('ID/名称/创建人/更新人/所属模板 ID/所属作用域类型/所属作用域值')"
      :search-list="searchList"
      @updateSearchValue="searchValue = $event"
      @changeRequest="handleSearchSelectChange">
      <bk-button
        theme="primary"
        :disabled="listLoading || !spaceId"
        @click="handleEdit()">
        {{ $t('新建') }}
      </bk-button>
    </table-operate>
    <bk-table
      v-bkloading="{ isLoading: listLoading }"
      :data="decisionList"
      :max-height="tableMaxHeight"
      :size="setting.size"
      :pagination="pagination"
      @page-change="handlePageChange"
      @page-limit-change="handlePageLimitChange">
      <bk-table-column
        v-for="item in setting.selectedFields"
        :key="item.id"
        :label="item.label"
        :prop="item.id"
        :render-header="renderTableHeader"
        :width="item.width"
        show-overflow-tooltip
        :min-width="item.min_width">
        <template slot-scope="{ row }">
          <a
            v-if="item.id === 'name'"
            class="decision-name"
            @click="handleNameClick(row)">
            {{ row.name }}
          </a>
          <span
            v-else
            class="table-cell">{{ row[item.id] || '--' }}</span>
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
          <decision-delete
            :data="row"
            :text="true"
            :is-admin-path="true"
            @onDeleted="onDecisionDeleted" />
        </template>
      </bk-table-column>
      <bk-table-column type="setting">
        <bk-table-setting-content
          :fields="setting.fieldList"
          :selected="setting.selectedFields"
          :size="setting.size"
          @setting-change="handleSettingChange" />
      </bk-table-column>
      <div
        slot="empty"
        class="empty-data">
        <NoData
          :type="isSearchEmpty ? 'search-empty' : 'empty'"
          :message="isSearchEmpty ? $t('搜索结果为空') : ''"
          @searchClear="updateSearchSelect" />
      </div>
    </bk-table>
    <!--决策表查看-->
    <decision-view
      :is-show="isDecisionViewShow"
      :row="selectedRow"
      :space-id="spaceId"
      path="admin_decision"
      @onDeleted="onDecisionDeleted"
      @close="isDecisionViewShow = false" />
  </div>
</template>

<script>
  import NoData from '@/components/common/base/NoData.vue';
  import DecisionView from './components/DecisionView.vue';
  import DecisionDelete from './components/DecisionDelete.vue';
  import { mapActions } from 'vuex';
  import CancelRequest from '@/api/cancelRequest.js';
  import moment from 'moment-timezone';
  import tableHeader from '@/mixins/tableHeader.js';
  import tableCommon from '../mixins/tableCommon.js';
  import TableOperate from '../common/TableOperate.vue';
  import i18n from '@/config/i18n/index.js';

  const TABLE_FIELDS = [
    {
      id: 'id',
      label: 'ID',
      disabled: true,
      width: 100,
    },
    {
      id: 'scope_type',
      label: i18n.t('所属作用域类型'),
      width: 160,
    },
    {
      id: 'scope_value',
      label: i18n.t('所属作用域值'),
      width: 160,
    },
    {
      id: 'name',
      label: i18n.t('名称'),
      disabled: true,
      min_width: 250,
    },
    {
      id: 'template_id',
      label: i18n.t('所属模板 ID'),
      width: 100,
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
  const SEARCH_LIST = [
    {
      id: 'id',
      name: 'ID',
    },
    {
      id: 'name',
      name: i18n.t('名称'),
      isDefaultOption: true,
    },
    {
      id: 'creator',
      name: i18n.t('创建人'),
    },
    {
      id: 'updated_by',
      name: i18n.t('更新人'),
    },
    {
      id: 'template_id',
      name: i18n.t('所属模板 ID'),
    },
    {
      id: 'scope_type',
      name: i18n.t('所属作用域类型'),
    },
    {
      id: 'scope_value',
      name: i18n.t('所属作用域值'),
    },
  ];
  export default {
    name: 'DecisionTableList',
    components: {
      NoData,
      DecisionView,
      DecisionDelete,
      TableOperate,
    },
    mixins: [tableHeader, tableCommon],
    data() {
      return {
        decisionList: [],
        tableFields: TABLE_FIELDS,
        defaultSelected: ['id', 'name', 'creator', 'create_at', 'update_by', 'update_at'],
        setting: {
          fieldList: TABLE_FIELDS,
          selectedFields: [],
          size: 'small',
        },
        dateFields: ['create_at', 'update_at'],
        isDecisionViewShow: false,
        selectedRow: {},
        searchList: SEARCH_LIST,
        pageType: 'decisionList', // 页面类型，在mixins中分页表格头显示使用
      };
    },
    mounted() {
      const { id, activeTab } = this.$route.query;
      if (id && activeTab === 'decisionTable') {
        this.requestData.id = this.$route.query.id;
      }
      this.getDecisionList();
    },
    methods: {
      ...mapActions('decisionTable/', [
        'loadDecisionList',
        'deleteDecision',
      ]),
      async getDecisionList() {
        try {
          if (!this.spaceId) return;
          this.listLoading = true;
          const data = this.getQueryData();
          const resp = await this.loadDecisionList(data);
          this.decisionList = resp.data.results;
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
      getQueryData() {
        const source = new CancelRequest();
        const {
          name,
          id,
          creator,
          updated_by,
          create_at: createAt,
          update_at: updateAt,
          scope_type,
          scope_value,
          template_id,
          limit = this.pagination.limit,
          current = this.pagination.current,
        } = this.requestData;
        const data = {
          space_id: this.spaceId,
          limit,
          offset: (current - 1) * limit,
          name__icontains: name,
          id,
          creator,
          updated_by,
          scope_type,
          scope_value,
          template_id,
          cancelToken: source.token,
          isAdmin: true,
        };
        if (createAt && createAt[0] && createAt[1]) {
          data.create_at__gte = moment(createAt[0]).format('YYYY-MM-DD HH:mm:ss');
          data.create_at__lte = moment(createAt[1]).format('YYYY-MM-DD HH:mm:ss');
        }
        if (updateAt && updateAt[0] && updateAt[1]) {
          data.update_at__gte = moment(updateAt[0]).format('YYYY-MM-DD HH:mm:ss');
          data.update_at__lte = moment(updateAt[1]).format('YYYY-MM-DD HH:mm:ss');
        }
        return data;
      },
      handleEdit(row = {}) {
        this.$router.push({
          name: 'decisionEdit',
          params: { decisionId: row.id, path: 'admin_decision' },
          query: { space_id: this.spaceId },
        });
      },
      onDecisionDeleted() {
        this.isDecisionViewShow = false;
        // 最后一页最后一条删除后，往前翻一页
        if (
          this.pagination.current > 1
          && this.totalPage === this.pagination.current
          && this.pagination.count - (this.totalPage - 1) * this.pagination.limit === 1
        ) {
          this.pagination.current -= 1;
        }
        this.getDecisionList();
        this.updateUrl({ current: 1 });
      },
      handleNameClick(row) {
        this.selectedRow = row;
        this.isDecisionViewShow = true;
      },
    },
  };
</script>

<style lang='scss' scoped>
  ::v-deep .bk-table-empty-text {
    width: 100%;
  }
  .decision-name {
    color: #3a84ff;
    font-size: 12px;
    cursor: pointer;
    &.disabled {
      color: #cccccc;
      cursor: not-allowed;
    }
  }
</style>
