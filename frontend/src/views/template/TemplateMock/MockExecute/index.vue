<template>
  <div
    v-bkloading="{ isLoading: isLoading, opacity: 1 }"
    class="mock-execute">
    <div class="form-wrapper">
      <div class="variable-wrap">
        <p class="wrap-title">
          {{ $t('填写调试入参') }}
        </p>
        <TaskParamEdit
          ref="taskParamEdit"
          :editable="tplActions.includes('MOCK')"
          :constants="pipelineTree.constants" />
      </div>
      <div class="mock-wrap">
        <p class="wrap-title">
          {{ $t('选择 Mock 数据') }}
        </p>
        <template v-if="!!Object.keys(nodeMockMap).length">
          <bk-form
            ref="mockForm"
            :label-width="200"
            :model="mockFormData"
            form-type="vertical"
            :rules="rules">
            <bk-form-item
              v-for="key in Object.keys(nodeMockMap)"
              :key="key"
              :label="pipelineTree.activities[key].name"
              :required="true"
              :property="key"
              :error-display-type="'normal'">
              <bk-select v-model="mockFormData[key]">
                <bk-option
                  :id="-1"
                  :name="$t('无需Mock，真执行')" />
                <bk-option
                  v-for="option in nodeMockMap[key]"
                  :id="option.id"
                  :key="option.id"
                  :name="option.name" />
              </bk-select>
            </bk-form-item>
          </bk-form>
        </template>
        <template v-if="!!unMockNodes.length">
          <p
            class="un-mock-title"
            @click="unMockExpend = !unMockExpend">
            <i
              class="bk-icon icon-angle-double-down"
              :class="{ 'is-expend': unMockExpend }" />
            <span>{{ unMockExpend ? $t('收起未设置 Mock数据 的节点') : $t('显示未设置 Mock数据 的节点') }}</span>
          </p>
          <ul
            v-if="unMockExpend"
            class="un-mock-list">
            <li
              v-for="key in unMockNodes"
              :key="key">
              {{ pipelineTree.activities[key].name }}
            </li>
          </ul>
        </template>
      </div>
    </div>
    <div
      v-if="!isLoading"
      class="action-wrapper">
      <bk-button
        theme="primary"
        :loading="createLoading"
        :disabled="!tplActions.includes('MOCK')"
        @click="onCreateTask">
        {{ $t('执行') }}
      </bk-button>
      <bk-button
        :disabled="createLoading"
        @click="$emit('onReturn')">
        {{ $t('取消') }}
      </bk-button>
    </div>
  </div>
</template>

<script>
  import { mapActions } from 'vuex';
  import tools from '@/utils/tools';
  import TaskParamEdit from './components/TaskParamEdit.vue';
  export default {
    name: 'MockExecute',
    components: {
      TaskParamEdit,
    },
    props: {
      headerLabel: {
        type: String,
        default: '',
      },
      creator: {
        type: String,
        default: '',
      },
      templateId: {
        type: [String, Number],
        default: '',
      },
      selectedNodes: {
        type: Array,
        default: () => ([]),
      },
      tplActions: {
        type: Array,
        default: () => ([]),
      },
    },
    data() {
      return {
        isLoading: true,
        createLoading: false,
        nodeMockMap: {},
        pipelineTree: {},
        mockFormData: {},
        initMockData: {},
        mockDataList: [],
        rules: {},
        unMockNodes: [],
        unMockExpend: false,
      };
    },
    created() {
      this.loadData();
    },
    methods: {
      ...mapActions('template/', [
        'gerTemplatePreviewData',
      ]),
      ...mapActions('task/', [
        'createMockTask',
      ]),
      async loadData() {
        try {
          const resp = await this.gerTemplatePreviewData({
            templateId: this.templateId,
            selectedNodes: this.selectedNodes,
          });
          const { mock_data: mockData, pipeline_tree: pipelineTree } = resp.data;
          this.pipelineTree = pipelineTree;
          this.nodeMockMap = mockData.reduce((acc, cur) => {
            // 过滤掉无mock的节点
            if (!(cur.node_id in pipelineTree.activities)) return acc;
            if (cur.node_id in acc) {
              acc[cur.node_id].push(cur);
            } else {
              acc[cur.node_id] = [cur];
            }
            if (!(cur.node_id in this.mockFormData) || cur.is_default) {
              this.$set(this.mockFormData, cur.node_id, cur.is_default ? cur.id : -1);
            }
            this.rules[cur.node_id] = [{
              required: true,
              message: this.$t('必填项'),
              trigger: 'blur',
            }];
            return acc;
          }, {});
          this.initMockData = tools.deepClone(this.mockFormData);
          this.mockDataList = mockData;
          this.unMockNodes = Object.keys(pipelineTree.activities).filter(key => !(key in this.nodeMockMap));
        } catch (error) {
          console.warn(error);
        } finally {
          this.isLoading = false;
        }
      },
      async onCreateTask() {
        try {
          const { taskParamEdit: paramEditComp, mockForm } = this.$refs;
          let validate = true;
          if (paramEditComp) {
            validate = paramEditComp.validate();
          }
          if (!validate) return;
          if (mockForm) {
            await mockForm.validate();
          }
          this.createLoading = true;
          const pipelineTree = tools.deepClone(this.pipelineTree);
          if (paramEditComp) {
            pipelineTree.constants = paramEditComp.getVariableData();
          }
          const mockData = Object.keys(this.mockFormData).reduce((acc, cur) => {
            const value = this.mockFormData[cur];
            if (value !== -1) {
              acc.nodes.push(cur);
              const mockInfo = this.mockDataList.find(item => item.id === value);
              acc.outputs[cur] = mockInfo ? mockInfo.data : {};
            }
            return acc;
          }, { nodes: [], outputs: {} });
          const params = {
            name: this.headerLabel,
            pipeline_tree: pipelineTree,
            mock_data: mockData,
            creator: this.creator,
          };
          const resp = await this.createMockTask({
            id: this.templateId,
            params,
          });
          if (resp.result) {
            this.$bkMessage({
              message: this.$t('任务创建成功'),
              theme: 'success',
            });
            // 更新数据，导航守卫会检查数据是否一致
            this.initMockData = tools.deepClone(this.mockFormData);
            if (paramEditComp) {
              paramEditComp.initialRenderData = tools.deepClone(paramEditComp.renderData);
            }
            this.$router.push({
              name: 'taskExecute',
              params: {
                spaceId: resp.data.space_id,
              },
              query: {
                instanceId: resp.data.id,
              },
            });
          }
        } catch (error) {
          console.warn(error);
        } finally {
          this.createLoading = false;
        }
      },
      judgeDataEqual() {
        const { taskParamEdit: paramEditComp } = this.$refs;
        let isEqual = paramEditComp ? paramEditComp.judgeDataEqual() : true;
        if (isEqual) {
          isEqual = tools.isDataEqual(this.initMockData, this.mockFormData);
        }
        return isEqual;
      },
    },
  };
</script>

<style lang="scss" scoped>
@import '../../../../scss/mixins/scrollbar.scss';
.mock-execute {
  flex: 1;
  display: flex;
  flex-direction: column;
  max-height: calc(100% - 60px);
  background: #f5f7fa;
  .form-wrapper {
    flex: 1;
    padding: 24px 270px;
    overflow-y: auto;
    @include scrollbar;
    .wrap-title {
      font-size: 14px;
      color: #63656e;
      line-height: 22px;
      font-weight: Bold;
      margin-bottom: 16px;
    }
    .variable-wrap {
      padding: 16px 24px;
      margin-bottom: 16px;
      background: #fff;
    }
    .mock-wrap {
      padding: 16px 24px;
      background: #fff;
      .bk-form {
        margin-bottom: 16px;
      }
      .un-mock-title {
        display: inline-flex;
        align-items: center;
        line-height: 20px;
        font-size: 12px;
        margin-bottom: 16px;
        color: #3a84ff;
        cursor: pointer;
        .icon-angle-double-down {
          font-size: 20px;
          &.is-expend {
            transform: rotate(180deg);
          }
        }
      }
      /deep/.bk-label {
        font-size: 12px;
      }
      .un-mock-list {
        padding: 12px 16px;
        color: #63656e;
        font-size: 12px;
        line-height: 20px;
        background: #f5f7fa;
        border-radius: 2px;
        li:not(:last-child) {
          position: relative;
          margin-bottom: 17px;
          &::after {
            content: '';
            display: block;
            height: 1px;
            width: 100%;
            position: absolute;
            bottom: -9px;
            background: #dcdee5;
          }
        }
      }
    }
  }
  .action-wrapper {
    height: 48px;
    z-index: 2;
    padding-left: 270px;
    background: #fafbfd;
    box-shadow: 0 -1px 0 0 #dcdee5;
    .bk-button {
      width: 88px;
      margin-top: 8px;
    }
  }
}
</style>
