<template>
  <div class="task-list">
    <table-operate
      ref="tableOperate"
      :space-id="spaceId"
      :placeholder="$t('ID/任务名称/创建人/执行人/所属模板 ID/所属作用域类型/所属作用域值')"
      :search-list="searchList"
      @updateSearchValue="searchValue = $event"
      @changeRequest="handleSearchSelectChange">
      <bk-button
        v-if="isAdmin"
        theme="primary"
        :disabled="!spaceId"
        @click="onEngineOperate">
        {{ $t('引擎操作') }}
      </bk-button>
    </table-operate>
    <bk-table
      v-bkloading="{ isLoading: listLoading }"
      :data="taskList"
      :pagination="pagination"
      :size="setting.size"
      :max-height="tableMaxHeight"
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
        <template slot-scope="props">
          <div v-if="item.id === 'name'">
            <router-link
              class="task-name"
              :to="{
                name: 'taskExecute',
                params: {
                  spaceId: spaceId
                },
                query: {
                  instanceId: props.row.id,
                  type: createMethod === 'MOCK' ? 'mock' : undefined
                }
              }">
              {{ props.row.name }}
            </router-link>
          </div>
          <div
            v-else-if="item.id === 'state'"
            class="task-status">
            <span :class="props.row.cls" />
            <span class="task-status-text">{{ props.row.state_text || '--' }}</span>
          </div>
          <div v-else-if="item.id === 'trigger_method'">
            <span>{{ $t(triggerMethodName[props.row.trigger_method]) }}</span>
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
        width="150">
        <template slot-scope="props">
          <bk-button
            theme="primary"
            text
            @click="onDeleteTask(props.row)">
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
        slot="empty"
        class="empty-data">
        <NoData
          :type="isSearchEmpty ? 'search-empty' : 'empty'"
          :message="isSearchEmpty ? $t('搜索结果为空') : ''"
          @searchClear="updateSearchSelect" />
      </div>
    </bk-table>
  </div>
</template>

<script>
  import { mapState, mapActions } from 'vuex';
  import CancelRequest from '@/api/cancelRequest.js';
  import NoData from '@/components/common/base/NoData.vue';
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
      label: i18n.t('任务名称'),
      disabled: true,
      min_width: 200,
    },
    {
      id: 'template_id',
      label: i18n.t('所属模板 ID'),
      width: 100,
    },
    {
      id: 'create_time',
      label: i18n.t('创建时间'),
      width: 280,
    },
    {
      id: 'creator',
      label: i18n.t('创建人'),
      width: 160,
    },
    {
      id: 'executor',
      label: i18n.t('执行人'),
      width: 160,
    },
    {
      id: 'state',
      label: i18n.t('状态'),
      width: 160,
    },
    {
      id: 'trigger_method',
      label: i18n.t('触发类型'),
      width: 160,
    },
    {
      id: 'start_time',
      label: i18n.t('开始时间'),
      width: 280,
    },
    {
      id: 'finish_time',
      label: i18n.t('结束时间'),
      width: 280,
    },
    {
      id: 'instance_id',
      label: i18n.t('引擎实例 Id'),
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
      name: i18n.t('任务名称'),
      isDefaultOption: true,
    },
    {
      id: 'creator',
      name: i18n.t('创建人'),
    },
    {
      id: 'executor',
      name: i18n.t('执行人'),
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
  const TRIGGER_METHOD = {
    api: 'api触发',
    manual: '手动触发',
    timing: '定时触发',
  };
  export default {
    name: 'TaskList',
    components: {
      NoData,
      TableOperate,
    },
    mixins: [tableHeader, tableCommon],
    data() {
      return {
        taskList: [],
        deleting: false,
        tableFields: TABLE_FIELDS,
        defaultSelected: ['id', 'name', 'creator_time', 'creator', 'executor', 'state', 'start_time', 'finish_time'],
        setting: {
          fieldList: TABLE_FIELDS,
          selectedFields: [],
          size: 'small',
        },
        dateFields: ['create_time', 'start_time', 'finish_time'],
        searchList: SEARCH_LIST,
        pageType: 'taskList', // 页面类型，在mixins中分页表格头显示使用
        triggerMethodName: TRIGGER_METHOD,
      };
    },
    computed: {
      ...mapState({
        isAdmin: state => state.isAdmin,
      }),
    },
    methods: {
      ...mapActions('taskList/', [
        'loadTaskList',
        'deleteTask',
      ]),
      ...mapActions('task/', [
        'getTaskStatus',
      ]),
      async getTaskList() {
        try {
          if (!this.spaceId) return;
          this.listLoading = true;
          const data = this.getQueryData();
          const resp = await this.loadTaskList(data);
          const list = await this.setFillTaskField(resp.data.results);
          this.taskList = list;
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
      async setFillTaskField(list) {
        try {
          const ids = list.map(task => task.id);
          const params = {
            space_id: this.spaceId,
            task_ids: ids,
          };
          const resp = await this.getTaskStatus(params);
          list.forEach((task) => {
            const status = {};
            if (task.is_expired) {
              status.cls = 'expired bk-icon icon-clock-shape';
              status.state_text = this.$t('已过期');
            } else if (task.is_finished) {
              status.cls = 'finished bk-icon icon-check-circle-shape';
              status.state_text = this.$t('完成');
            } else if (task.is_revoked) {
              status.cls = 'revoke common-icon-dark-stop';
              status.state_text = this.$t('终止');
            } else if (task.is_started) {
              status.cls = 'loading common-icon-loading';
              const { state } = resp.data[task.id];
              switch (state) {
                case 'RUNNING':
                case 'BLOCKED':
                  status.cls = 'running common-icon-dark-circle-ellipsis';
                  status.state_text = this.$t('执行中');
                  break;
                case 'READY':
                  status.cls = 'running common-icon-dark-circle-ellipsis';
                  status.state_text = this.$t('排队中');
                  break;
                case 'SUSPENDED':
                  status.cls = 'execute common-icon-dark-circle-pause';
                  status.state_text = this.$t('已暂停');
                  break;
                case 'NODE_SUSPENDED':
                  status.cls = 'execute';
                  status.state_text = this.$t('节点暂停');
                  break;
                case 'FAILED':
                  status.cls = 'failed common-icon-dark-circle-close';
                  status.state_text = this.$t('失败');
                  break;
                default:
                  status.state_text = this.$t('未知');
              }
            } else {
              status.cls = 'created common-icon-waitting';
              status.state_text = this.$t('未执行');
            }
            Object.assign(task, status);
          });
          return list;
        } catch (error) {
          console.warn(error);
        }
      },
      getQueryData() {
        const source = new CancelRequest();
        const { query } = this.$route;
        this.pagination.current = query.current ?  Number(query.current) : this.pagination.current;
        const {
          name,
          id,
          creator,
          create_time: createTime,
          start_time: startTime,
          finish_time: finishTime,
          executor,
          scope_type,
          scope_value,
          template_id,
          limit = this.pagination.limit,
        } = this.requestData;
        const data = {
          space_id: this.spaceId,
          limit,
          offset: (this.pagination.current - 1) * limit,
          name__icontains: name,
          id,
          creator,
          executor,
          scope_type,
          scope_value,
          template_id,
          cancelToken: source.token,
          create_method: this.createMethod,
        };
        if (createTime && createTime[0] && createTime[1]) {
          data.create_time__gte = moment(createTime[0]).format('YYYY-MM-DD HH:mm:ss');
          data.create_time__lte = moment(createTime[1]).format('YYYY-MM-DD HH:mm:ss');
        }
        if (startTime && startTime[0] && startTime[1]) {
          data.start_time__gte = moment(startTime[0]).format('YYYY-MM-DD HH:mm:ss');
          data.start_time__lte = moment(startTime[1]).format('YYYY-MM-DD HH:mm:ss');
        }
        if (finishTime && finishTime[0] && finishTime[1]) {
          data.finish_time__gte = moment(finishTime[0]).format('YYYY-MM-DD HH:mm:ss');
          data.finish_time__lte = moment(finishTime[1]).format('YYYY-MM-DD HH:mm:ss');
        }
        return data;
      },
      onDeleteTask(template) {
        const h = this.$createElement;
        this.$bkInfo({
          subHeader: h('div', { class: 'custom-header' }, [
            h('div', {
              class: 'custom-header-title',
              directives: [{
                name: 'bk-overflow-tips',
              }],
            }, [this.$t('确认删除任务"{0}"?', [template.name])]),
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
      async onDeleteConfirm(taskId) {
        if (this.deleting) return;
        this.deleting = true;
        try {
          const data = {
            space_id: this.spaceId,
            task_ids: [taskId],
          };
          const resp = await this.deleteTask(data);
          if (resp.result === false) return;
          // 最后一页最后一条删除后，往前翻一页
          if (
            this.pagination.current > 1
            && this.totalPage === this.pagination.current
            && this.pagination.count - (this.totalPage - 1) * this.pagination.limit === 1
          ) {
            this.pagination.current -= 1;
          }
          this.getTaskList();
          this.updateUrl({ current: 1 });
          this.$bkMessage({
            message: this.$t('任务删除成功！'),
            theme: 'success',
          });
        } catch (e) {
          console.log(e);
        } finally {
          this.deleting = false;
        }
      },
      onEngineOperate() {
        this.$router.push({
          name: 'EnginePanel',
          params: {
            spaceId: this.spaceId,
          },
          query: { type: this.$route.query.activeTab },
        });
      },
    },
  };
</script>

<style lang="scss" scoped>
  @import '../../../../scss/task.scss';
  .task-status {
    @include ui-task-status;
    .task-status-text {
      vertical-align: middle;
    }
  }
  ::v-deep .bk-table-empty-text {
    width: 100%;
  }
</style>
