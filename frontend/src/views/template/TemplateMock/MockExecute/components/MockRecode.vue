<template>
  <div class="mock-recode">
    <div
      :class="['recode-nav', { 'is-fold': isFold }]"
      @click="isFold = !isFold">
      <i class="bk-icon icon-arrow-right" />
      <span>{{ '历史调试' }}</span>
    </div>
    <div
      v-if="!isFold"
      class="recode-panel">
      <h3 class="title">
        {{ '历史调试' }}
      </h3>
      <ul v-bkloading="{ isLoading: listLoading }">
        <li
          v-for="task in taskList"
          :key="task.id"
          class="recode-item">
          <div class="top-wrap">
            <span class="id-tag">{{ `ID${task.id}` }}</span>
            <span class="name">{{ task.name }}</span>
          </div>
          <div class="bottom-wrap">
            <span>{{ task.creator }}</span>
            <span>{{ task.create_time }}</span>
            <div
              class="reuse-wrap"
              @click="onReuse(task.id)">
              <i class="bk-icon icon-arrows-left-circle" />
              <span>{{ '一键复用' }}</span>
            </div>
          </div>
        </li>
      </ul>
    </div>
    <DiffDialog
      :is-diff-dialog-show="isDiffDialogShow"
      :diff-list="diffList"
      @confirm="onConfirmReuse"
      @cancel="onDialogCancel" />
  </div>
</template>

<script>
  import { mapState, mapActions } from 'vuex';
  import DiffDialog from './DiffDialog.vue';
  export default {
    name: 'MockRecode',
    components: {
      DiffDialog,
    },
    props: {
      templateId: {
        type: [String, Number],
        default: '',
      },
      mockFormData: {
        type: Object,
        default: () => ({}),
      },
      nodeMockMap: {
        type: Object,
        default: () => ({}),
      },
      activities: {
        type: Object,
        default: () => ({}),
      },
      constants: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        isFold: false,
        listLoading: false,
        taskList: [],
        isDiffDialogShow: false,
        diffList: [],
        recodeData: {},
      };
    },
    computed: {
      ...mapState({
        spaceId: state => state.template.spaceId,
      }),
      disabledReuse() {
        let isDisable = !Object.keys(this.nodeMockMap).length;
        isDisable = isDisable ? !Object.values(this.constants).some(item => item.show_type === 'show').length : isDisable;
        return isDisable;
      },
    },
    created() {
      this.getTaskList();
    },
    methods: {
      ...mapActions('template/', [
        'getTemplateMockTaskList',
      ]),
      ...mapActions('task/', [
        'getTaskInstanceData',
        'getTaskMockData',
      ]),
      async getTaskList() {
        try {
          if (!this.spaceId) return;
          this.listLoading = true;
          const resp = await this.getTemplateMockTaskList({
            space_id: this.spaceId,
            template_id: this.templateId,
          });
          this.taskList = resp.data.results;
        } catch (error) {
          console.warn(error);
        } finally {
          this.listLoading = false;
        }
      },
      async onReuse(taskId) {
        try {
          const [resp1, resp2] = await Promise.all([
            this.getTaskInstanceData(taskId),
            this.getTaskMockData({ id: taskId, spaceId: this.spaceId }),
          ]);

          // 新旧diff
          const { constants } = resp1.pipeline_tree;
          const { mock_data_ids } = resp2.data;
          const diffList = this.getDiffList(mock_data_ids);
          this.recodeData = { constants, mock_data_ids };

          if (!diffList.length) {
            this.onConfirmReuse();
            return;
          }

          this.diffList = diffList;
          this.isDiffDialogShow = !!diffList.length;
        } catch (error) {
          console.warn(error);
        }
      },
      getDiffList(mockIds) {
        // mock diff
        const oldMock = mockIds;
        const newMock = this.mockFormData;
        const diffList = Object.keys(newMock).reduce((acc, nodeId) => {
          const nodeName = this.activities[nodeId]?.name;
          let mockId = 0;

          // 只记录历史mock方案不存在的diff
          mockId = oldMock[nodeId];
          if (!mockId || mockId === -1) return acc;
          const isExist = this.nodeMockMap[nodeId].some(item => item.id === mockId);
          if (isExist) return acc;

          // right
          const right = { id: mockId, node_name: nodeName };
          // left
          let left = {};
          mockId = newMock[nodeId];
          if (mockId === -1) {
            left = { name: '无需Mock，真执行', node_name: nodeName };
          } else if (mockId) {
            const mockInfo = this.nodeMockMap[nodeId].find(item => item.id === mockId);
            left = { ...mockInfo, node_name: nodeName };
          }

          acc.push({
            left,
            right,
          });

          return acc;
        }, []);

        return diffList;
      },
      onConfirmReuse() {
        this.$emit('change', this.recodeData);
        this.isDiffDialogShow = false;
      },
      onDialogCancel() {
        this.diffList = [];
        this.recodeData = {};
        this.isDiffDialogShow = false;
      },
    },
  };
</script>

<style lang="scss" scoped>
  @import '../../../../../scss/mixins/scrollbar.scss';
  .mock-recode {
    display: flex;
    position: relative;
    height: 100%;
    font-size: 12px;
    .recode-nav {
      width: 20px;
      height: 110px;
      position: absolute;
      top: 24px;
      left: -20px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      text-align: center;
      color: #fff;
      background: #C4C6CC;
      border-radius: 4px 0 0  4px;
      cursor: pointer;
      i {
        font-size: 16px;
        margin-bottom: 6px;
      }
      &:hover {
        background: #3a84ff;
      }
      &.is-fold {
        background: #3a84ff;
        i {
          transform: rotate(180deg);
        }
      }
    }
    .recode-panel {
      width: 360px;
      height: 100%;
      display: flex;
      flex-direction: column;
      padding: 16px 24px;
      background: #FFFFFF;
      box-shadow: -1px 0 0 0 #DCDEE5;
      h4 {
        margin-bottom: 16px;
      }
      ul {
        flex: 1;
        overflow-y: auto;
        @include scrollbar;
      }
      .recode-item {
        padding: 12px 0;
        border-top: 1px solid #c4c6cc;
        border-radius: 2px;
        .top-wrap {
          display: flex;
          margin-bottom: 8px;
          line-height: 22px;
          color: #63656E;
          .id-tag {
            padding: 0 8px;
            display: inline-block;
            margin-right: 8px;
            background: #F0F1F5;
            border-radius: 2px;
          }
          .name {
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
        }
        .bottom-wrap {
          display: flex;
          align-items: center;
          justify-content: flex-start;
          color: #979BA5;
          line-height: 20px;
          span {
            margin-right: 16px;
            &:nth-child(2) {
              overflow: hidden;
              white-space: nowrap;
              text-overflow: ellipsis;
            }
          }
          .reuse-wrap {
            flex-shrink: 0;
            margin-left: auto;
            color: #3a84ff;
            cursor: pointer;
            i {
              font-size: 14px;
            }
          }
        }
        &:last-of-type {
          border-bottom: 1px solid #c4c6cc;
        }
      }
    }
  }
</style>./DiffDialog.vue
