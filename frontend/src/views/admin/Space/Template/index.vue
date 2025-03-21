<template>
  <div class="template-list">
    <table-operate
      ref="tableOperate"
      :space-id="spaceId"
      :placeholder="$t('ID/流程名称/创建人/更新人/启用/所属作用域类型/所属作用域值')"
      :search-list="searchList"
      @updateSearchValue="searchValue = $event"
      @changeRequest="handleSearchSelectChange">
      <bk-button
        theme="primary"
        :disabled="!spaceId"
        class="mr10"
        @click="showCreateTplDialog = true">
        {{ $t('创建流程') }}
      </bk-button>
      <bk-button
        v-if="selectedTpls.length"
        @click="onBatchDelete">
        {{ $t('删除') }}
      </bk-button>
    </table-operate>
    <bk-table
      v-bkloading="{ isLoading: listLoading }"
      :data="templateList"
      :pagination="pagination"
      :size="setting.size"
      :max-height="tableMaxHeight"
      @page-change="handlePageChange"
      @page-limit-change="handlePageLimitChange">
      <bk-table-column
        width="70"
        :render-header="renderHeaderCheckbox">
        <template slot-scope="props">
          <bk-checkbox
            :value="!!selectedTpls.find(tpl => tpl.id === props.row.id)"
            @change="onToggleTplItem($event, props.row)" />
        </template>
      </bk-table-column>
      <bk-table-column
        v-for="item in setting.selectedFields"
        :key="item.id"
        :label="item.label"
        :label-class-name="item.id === 'id' ? 'task-id' : ''"
        :prop="item.id"
        :render-header="renderTableHeader"
        :width="item.width"
        show-overflow-tooltip
        :min-width="item.min_width">
        <template slot-scope="props">
          <div v-if="item.id === 'name'">
            <router-link
              class="template-name"
              :to="{
                name: 'templatePanel',
                params: {
                  templateId: props.row.id,
                  type: 'view'
                }
              }">
              {{ props.row.name }}
            </router-link>
          </div>
          <!-- 其他 -->
          <template v-else>
            <span>{{ props.row[item.id] || '--' }}</span>
          </template>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('操作')"
        fixed="right"
        width="200">
        <template slot-scope="props">
          <bk-button
            theme="primary"
            text
            @click="onCreateTask(props.row)">
            {{ $t('新建任务') }}
          </bk-button>
          <bk-button
            theme="primary"
            class="ml10"
            text
            @click="onDeleteTemplate(props.row)">
            {{ $t('删除') }}
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
      <div
        v-if="selectedTpls.length > 0"
        slot="prepend"
        class="selected-tpl-num">
        {{ $t('当前已选择 x 条数据', { num: selectedTpls.length }) }}{{ $t('，') }}
        <bk-link
          theme="primary"
          @click="selectedTpls = []">
          {{ $t('清除选择') }}
        </bk-link>
      </div>
      <div
        slot="empty"
        class="empty-data">
        <NoData
          :type="isSearchEmpty ? 'search-empty' : 'empty'"
          :message="isSearchEmpty ? $t('搜索结果为空') : ''"
          @searchClear="updateSearchSelect" />
      </div>
    </bk-table>
    <CreateTaskSideslider
      :is-show="showCreateTaskSlider"
      :row="selectRow"
      @close="showCreateTaskSlider = false" />
    <create-template-dialog
      :is-show="showCreateTplDialog"
      @close="showCreateTplDialog = false"
      @updateList="getTemplateList" />
  </div>
</template>

<script>
  import { mapActions } from 'vuex';
  import CancelRequest from '@/api/cancelRequest.js';
  import NoData from '@/components/common/base/NoData.vue';
  import moment from 'moment-timezone';
  import tableHeader from '@/mixins/tableHeader.js';
  import tableCommon from '../mixins/tableCommon.js';
  import TableOperate from '../common/TableOperate.vue';
  import CreateTaskSideslider from './CreateTaskSideslider.vue';
  import CreateTemplateDialog from './CreateTemplateDialog.vue';
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
      label: i18n.t('流程名称'),
      disabled: true,
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
    {
      id: 'is_enabled',
      label: i18n.t('启用'),
      width: 160,
    },
  ];
  const SEARCH_LIST = [
    {
      id: 'id',
      name: 'ID',
    },
    {
      id: 'name',
      name: i18n.t('流程名称'),
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
      id: 'is_enabled',
      name: i18n.t('启用'),
      children: [
        { id: 'true', name: true },
        { id: 'false', name: false },
      ],
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
    name: 'TemplateList',
    components: {
      NoData,
      TableOperate,
      CreateTemplateDialog,
      CreateTaskSideslider,
    },
    mixins: [tableHeader, tableCommon],
    data() {
      return {
        templateList: [],
        selectRow: {},
        showCreateTaskSlider: false,
        showCreateTplDialog: false,
        selectedTpls: [], // 选中的流程模板
        batchDeleting: false,
        deleting: false,
        tableFields: TABLE_FIELDS,
        defaultSelected: ['id', 'name', 'creator', 'create_at', 'update_by', 'update_at'],
        setting: {
          fieldList: TABLE_FIELDS,
          selectedFields: [],
          size: 'small',
        },
        dateFields: ['create_at', 'update_at'],
        searchList: SEARCH_LIST,
        pageType: 'templateList', // 页面类型，在mixins中分页表格头显示使用
      };
    },
    computed: {
      crtPageSelectedAll() {
        return this.templateList.length > 0
          && this.templateList.every(item => this.selectedTpls.find(tpl => tpl.id === item.id));
      },
    },
    methods: {
      ...mapActions('templateList/', [
        'loadTemplateList',
        'deleteTemplate',
      ]),
      ...mapActions('task/', [
        'createTask',
      ]),
      async getTemplateList() {
        try {
          if (!this.spaceId) return;
          this.listLoading = true;
          const data = this.getQueryData();
          const resp = await this.loadTemplateList(data);
          this.templateList = resp.data.results;
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
          is_enabled,
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
          is_enabled,
          cancelToken: source.token,
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
      onCreateTask(row) {
        this.selectRow = row;
        this.showCreateTaskSlider = true;
      },
      renderHeaderCheckbox(h) {
        const self = this;
        return h('div', {
          class: {
            'select-all-cell': true,
            'full-selected': this.pagination.count === this.selectedTpls.length,
          },
        }, [
          h('bk-checkbox', {
            props: {
              value: this.crtPageSelectedAll,
            },
            on: {
              change(val) {
                self.onToggleTplAll(val);
              },
            },
          }),
          h('bk-popover', {
            props: {
              placement: 'bottom',
              theme: 'light',
              distance: 0,
              'tippy-options': {
                hideOnClick: false,
              },
              'ext-cls': 'select-all-tpl-popover',
            },
          }, [
            h('i', {
              class: 'bk-icon icon-angle-down',
            }),
            h('div', {
              slot: 'content',
            }, [
              h('div', {
                class: 'mode-item',
                on: {
                  click() {
                    self.onSelectTplAll('current');
                  },
                },
              }, [this.$t('本页全选')]),
              h('div', {
                class: 'mode-item',
                on: {
                  click() {
                    self.onSelectTplAll('full');
                  },
                },
              }, [this.$t('跨页全选')]),
            ]),
          ]),
        ]);
      },
      // 本页全选、取消本页/跨页全选
      onToggleTplAll(val) {
        if (val) {
          this.onSelectTplAll('current');
        } else {
          if (this.selectedTpls.length === this.pagination.count) {
            this.selectedTpls = [];
          } else {
            this.templateList.forEach((tpl) => {
              const index = this.selectedTpls.findIndex(item => item.id === tpl.id);
              this.selectedTpls.splice(index, 1);
            });
          }
        }
      },
      // 本页全选、跨页全选
      async onSelectTplAll(type) {
        if (type === 'full') {
          const data = this.getQueryData();
          data.limit = -1;
          data.offset = 0;
          const resp = await this.loadTemplateList(data);
          if (resp.result) {
            this.selectedTpls = resp.data.results.slice(0);
          }
        } else {
          this.templateList.forEach((item) => {
            if (!this.selectedTpls.find(tpl => tpl.id === item.id)) {
              this.selectedTpls.push(item);
            }
          });
        }
      },
      onToggleTplItem(val, tpl) {
        if (val) {
          this.selectedTpls.push(tpl);
        } else {
          const index = this.selectedTpls.findIndex(item => item.id === tpl.id);
          this.selectedTpls.splice(index, 1);
        }
      },
      onBatchDelete() {
        if (this.selectedTpls.length === 0 || this.batchDeleting) {
          return;
        }
        this.$bkInfo({
          title: this.$t('确认删除所选的 {0} 项流程吗?', [this.selectedTpls.length]),
          maskClose: false,
          width: 450,
          confirmLoading: true,
          confirmFn: async () => {
            await this.batchDeleteConfirm();
          },
        });
      },
      async batchDeleteConfirm() {
        const data = {
          space_id: this.spaceId,
          is_full: this.pagination.count === this.selectedTpls.length,
          template_ids: this.selectedTpls.map(tpl => tpl.id),
        };
        const res = await this.deleteTemplate(data);
        if (res.result) {
          this.selectedTpls = [];
          this.pagination.current = 1;
          this.updateUrl({ current: 1 });
          this.getTemplateList();
          this.$bkMessage({
            message: this.$t('流程删除成功！'),
            theme: 'success',
          });
        }
        return Promise.resolve();
      },
      onDeleteTemplate(template) {
        const h = this.$createElement;
        this.$bkInfo({
          subHeader: h('div', { class: 'custom-header' }, [
            h('div', {
              class: 'custom-header-title',
              directives: [{
                name: 'bk-overflow-tips',
              }],
            }, [this.$t('确认删除流程"{0}"?', [template.name])]),
          ]),
          extCls: 'dialog-custom-header-title',
          maskClose: false,
          width: 450,
          confirmLoading: true,
          cancelText: this.$t('取消'),
          confirmFn: async () => {
            await this.onDeleteConfirm(template.id);
          },
        });
      },
      async onDeleteConfirm(templateId) {
        if (this.deleting) return;
        this.deleting = true;
        try {
          const data = {
            space_id: this.spaceId,
            template_ids: [templateId],
          };
          const resp = await this.deleteTemplate(data);
          if (resp.result === false) return;
          if (this.selectedTpls.find(tpl => tpl.id === templateId)) {
            const index = this.selectedTpls.findIndex(tpl => tpl.id === templateId);
            this.selectedTpls.splice(index, 1);
          }
          // 最后一页最后一条删除后，往前翻一页
          if (
            this.pagination.current > 1
            && this.totalPage === this.pagination.current
            && this.pagination.count - (this.totalPage - 1) * this.pagination.limit === 1
          ) {
            this.pagination.current -= 1;
          }
          this.getTemplateList();
          this.updateUrl({ current: 1 });
          this.$bkMessage({
            message: this.$t('流程') + this.$t('删除成功！'),
            theme: 'success',
          });
        } catch (e) {
          console.log(e);
        } finally {
          this.deleting = false;
        }
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
  .selected-tpl-num {
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    background: #f0f1f5;
    border-bottom: 1px solid #dfe0e5;
    /deep/.bk-link-text {
      margin-left: 6px;
      font-size: 12px;
      line-height: 1;
    }
  }
  /deep/.select-all-cell {
    display: flex;
    align-items: center;
    &.full-selected {
      .bk-form-checkbox {
        .bk-checkbox {
          background: #ffffff;
          &:after {
            border-color: #3a84ff;
          }
        }
      }
    }
    .icon-angle-down {
      margin-left: 2px;
      font-size: 18px;
      color: #979ba5;
    }
  }
  /deep/.bk-table-empty-text {
    width: 100%;
  }
</style>
