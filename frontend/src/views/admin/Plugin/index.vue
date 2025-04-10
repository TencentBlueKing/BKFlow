<template>
  <div class="my-plugin">
    <table-operate
      ref="tableOperate"
      :placeholder="$t('搜索插件名称、code、授权状态、管理员、授权状态修改人')"
      :search-list="searchList"
      @updateSearchValue="searchValue = $event"
      @changeRequest="handleSearchSelectChange" />
    <bk-table
      v-bkloading="{ isLoading: listLoading }"
      :data="pluginList"
      :max-height="tableMaxHeight"
      :pagination="pagination"
      @header-dragend="handleColumnHeaderDragend"
      @page-change="handlePageChange"
      @page-limit-change="handlePageLimitChange">
      <bk-table-column
        v-for="item in tableFields"
        :key="item.id"
        :label="item.label"
        :prop="item.id"
        :width="item.width"
        show-overflow-tooltip
        :class-name="`${item.id}-column`"
        :min-width="item.min_width">
        <template slot-scope="{ row }">
          <span v-if="item.id === 'managers'">
            <MoreTags
              :tags="row.managers"
              :width="columnWidth.managers - 30" />
          </span>
          <span
            v-else-if="item.id === 'status'"
            :class="['plugin-status', { 'is-authorization': row.status }]">
            {{ row.status ? $t('已授权') : $t('未授权') }}
          </span>
          <span v-else-if="item.id === 'config'">
            <MoreTags
              :tags="getWhiteListTags(row.config)"
              :width="columnWidth.config - 30" />
          </span>
          <span
            v-else
            class="table-cell">{{ row[item.id] || '--' }}</span>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('操作')"
        fixed="right"
        width="250">
        <template slot-scope="{ row }">
          <bk-button
            text
            title="primary"
            class="mr16"
            @click="showRangeEditDialog(row)">
            {{ $t('编辑使用范围') }}
          </bk-button>
          <AuthorizeBtn
            :row="row"
            @update="getPluginList" />
        </template>
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
    <RangEditDialog
      :is-show="editDialogShow"
      :row="selectedRow"
      @close="handleDialogClose" />
  </div>
</template>

<script>
  import NoData from '@/components/common/base/NoData.vue';
  import TableOperate from '../Space/common/TableOperate.vue';
  import MoreTags from '@/components/common/MoreTags.vue';
  import AuthorizeBtn from './AuthorizeBtn.vue';
  import RangEditDialog from './RangEditDialog.vue';
  import tableCommon from '../Space/mixins/tableCommon.js';
  import { mapActions } from 'vuex';
  import i18n from '@/config/i18n/index.js';
  import tools from '@/utils/tools.js';

  const TABLE_FIELDS = [
    {
      id: 'name',
      label: i18n.t('插件名称'),
      width: 160,
    },
    {
      id: 'code',
      label: 'code',
      width: 160,
    },
    {
      id: 'managers',
      label: i18n.t('管理员'),
      disabled: true,
      min_width: 200,
    },
    {
      id: 'status',
      label: i18n.t('授权状态'),
      width: 120,
    },
    {
      id: 'config',
      label: i18n.t('使用范围'),
      min_width: 160,
    },
    {
      id: 'status_update_time',
      label: i18n.t('授权状态修改时间'),
      min_width: 180,
    },
    {
      id: 'status_updator',
      label: i18n.t('授权状态修改人'),
      width: 160,
    },
  ];
  const SEARCH_LIST = [
    {
      id: 'name',
      name: i18n.t('名称'),
      isDefaultOption: true,
    },
    {
      id: 'code',
      name: 'code',
    },
    {
      id: 'status',
      name: i18n.t('授权状态'),
      children: [
        { id: 0, name: i18n.t('未授权') },
        { id: 1, name: i18n.t('已授权') },
      ],
    },
    {
      id: 'managers',
      name: i18n.t('管理员'),
    },
    {
      id: 'status_updator',
      name: i18n.t('授权状态修改人'),
    },
  ];

  export default {
    name: 'MyPlugin',
    components: {
      NoData,
      TableOperate,
      MoreTags,
      AuthorizeBtn,
      RangEditDialog,
    },
    mixins: [tableCommon],
    props: {},
    data() {
      return {
        tableFields: TABLE_FIELDS,
        listLoading: false,
        pluginList: [],
        searchList: SEARCH_LIST,
        pageType: 'pluginList', // 页面类型，在mixins中分页表格头显示使用
        editDialogShow: false,
        selectedRow: {},
        columnWidth: {
          managers: 0,
          config: 0,
        },
      };
    },
    mounted() {
      window.addEventListener('resize', tools.debounce(this.handleResize, 300));
      this.$nextTick(() => {
        this.handleResize();
      });
    },
    beforeDestroy() {
      window.removeEventListener('resize', this.handleResize);
    },
    methods: {
      ...mapActions('plugin', [
        'loadPluginManagerList',
      ]),
      // 获取插件列表
      async getPluginList() {
        try {
          this.listLoading = true;

          const data = this.getQueryData();
          const resp = await this.loadPluginManagerList(data);
          this.pluginList = resp.data.plugins;
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
        const {
          code,
          name,
          status,
          managers: manager,
          status_updator,
          limit = this.pagination.limit,
          current = this.pagination.current,
        } = this.requestData;

        const params = {
          code,
          name__icontains: name,
          status,
          manager,
          status_updator,
          limit,
          offset: (current - 1) * limit,
        };

        return params;
      },
      getWhiteListTags(config) {
        return config.white_list.map(item => item.name);
      },
      showRangeEditDialog(row) {
        this.selectedRow = row;
        this.editDialogShow = true;
      },
      handleDialogClose(val) {
        this.selectedRow = {};
        this.editDialogShow = false;
        if (val) {
          this.getPluginList();
        }
      },
      handleColumnHeaderDragend(newWidth, _oldWidth, column) {
        if (['managers', 'config'].includes(column.property)) {
          this.columnWidth[column.property] = newWidth;
        }
      },
      handleResize() {
        const managerColumnDom = document.querySelector('.managers-column');
        const configColumnDom = document.querySelector('.config-column');
        if (managerColumnDom) {
          const { width } = managerColumnDom.getBoundingClientRect();
          this.columnWidth.managers = width;
        }
        if (configColumnDom) {
          const { width } = configColumnDom.getBoundingClientRect();
          this.columnWidth.config = width;
        }
      },
    },
  };
</script>

<style lang="scss" scoped>
  /deep/.bk-table-empty-text {
    width: 100%;
  }
  /deep/.bk-table-pagination-wrapper {
    background: #fff;
  }
  .plugin-status {
    display: inline-block;
    color: #63656E;
    line-height: 22px;
    padding: 0 8px;
    background: #F0F1F5;
    border-radius: 2px;
    &.is-authorization {
      color: #14A568;
      background: #E4FAF0;
    }
  }
  .mr16 {
    margin-right: 16px;
  }
</style>;
