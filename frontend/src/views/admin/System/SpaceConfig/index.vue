<template>
  <div
    v-bkloading="{ isLoading: listLoading }"
    class="space-config">
    <bk-button
      theme="primary"
      class="mb20"
      :disabled="listLoading"
      @click="openSpaceDialog()">
      {{ $t('新增') }}
    </bk-button>
    <bk-table
      v-if="setting.selectedFields.length"
      :data="spaceList"
      :pagination="pagination"
      :max-height="tableMaxHeight"
      :size="setting.size"
      @page-change="handlePageChange"
      @page-limit-change="handlePageLimitChange">
      <bk-table-column
        v-for="field in setting.selectedFields"
        :key="field.key"
        :label="field.label"
        :prop="field.key"
        show-overflow-tooltip>
        <template slot-scope="{ row }">
          <span>{{ row[field.key] || '--' }}</span>
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
            @click="openSpaceDialog(row)">
            {{ $t('编辑') }}
          </bk-button>
        </template>
      </bk-table-column>
      <bk-table-column type="setting">
        <bk-table-setting-content
          :fields="setting.fieldList"
          :selected="setting.selectedFields"
          :size="setting.size"
          @setting-change="handleSettingChange" />
      </bk-table-column>
      <NoData
        slot="empty"
        type="empty" />
    </bk-table>
    <NoData
      v-else
      slot="empty"
      type="empty" />
    <!--新建空间弹框-->
    <SpaceDialog
      :is-show="editDialogShow"
      :space-info="spaceFormData"
      :fields="fields"
      @close="editDialogShow = false" />
  </div>
</template>

<script>
  import { mapActions } from 'vuex';
  import NoData from '@/components/common/base/NoData.vue';
  import tableCommon from '../../Space/mixins/tableCommon.js';
  import bus from '@/utils/bus.js';
  import SpaceDialog from '../../common/SpaceDialog.vue';
  export default {
    name: 'SpaceConfigList',
    components: {
      NoData,
      SpaceDialog,
    },
    mixins: [tableCommon],
    data() {
      return {
        spaceList: [],
        tableFields: [],
        editDialogShow: false,
        spaceFormData: {},
        fields: [],
        setting: {
          fieldList: [],
          selectedFields: [],
          size: 'small',
        },
        defaultSelected: ['id', 'name', 'creator', 'updated_by', 'app_code', 'desc', 'platform_url', 'create_type'],
        pageType: 'spaceList', // 页面类型，在mixins中分页表格头显示使用
      };
    },
    created() {
      this.getSpaceList();

      bus.$on('updateSpaceList', () => {
        this.getSpaceList();
        this.spaceFormData = {};
      });
    },
    methods: {
      ...mapActions([
        'loadSpaceList',
      ]),
      ...mapActions('system/', [
        'getSpaceMeta',
        'updateSpaceConfig',
      ]),
      async getSpaceList() {
        try {
          this.listLoading = true;
          const { limit, current } = this.pagination;
          const [resp1, resp2] = await Promise.all([
            this.loadSpaceList({
              limit,
              offset: (current - 1) * limit,
            }),
            this.getSpaceMeta(),
          ]);
          // 将排序返回
          const fieldSortList = [
            'id', 'name', 'creator', 'create_at', 'updated_by', 'update_at', 'app_code',
            'desc', 'platform_url', 'create_type',
          ];
          // 获取表格列
          this.tableFields = fieldSortList.map((key) => {
            const { verbose_name: value, choices } = resp2.data[key];
            return {
              id: key,
              key,
              label: value,
              disabled: key === 'id',
              choices,
            };
          });
          this.setting.fieldList = [...this.tableFields];
          // 获取当前视图表格头显示字段
          this.getFields();
          // 获取空间列表
          this.spaceList = resp1.data.results;
          this.pagination.count = resp1.data.count;
          // 计算总页数
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
      openSpaceDialog(config) {
        this.spaceFormData = config || {};
        const fields = ['name', 'app_code', 'desc', 'platform_url', 'create_type'];
        if (config) {
          fields.unshift('id');
        }
        this.fields = fields.map((field) => {
          const info = this.tableFields.find(item => item.key === field);
          let placeholder = field === 'platform_url' ? this.$t('请提供以 https:// 或 http:// 开头的服务地址') : '';
          placeholder = field === 'app_code' ? this.$t('仅支持您是开发者的 app_code') : placeholder;
          return {
            ...info,
            placeholder,
          };
        });
        this.editDialogShow = true;
      },
    },
  };
</script>

<style lang="scss" scoped>
  .space-config {
    ::v-deep .bk-table-empty-text {
      width: 100%;
    }
  }
</style>
