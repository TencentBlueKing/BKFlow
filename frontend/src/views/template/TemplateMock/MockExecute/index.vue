<template>
  <div
    v-bkloading="{ isLoading: isLoading, opacity: 1 }"
    class="mock-execute">
    <div class="left-wrapper">
      <div class="form-wrapper">
        <div class="variable-wrap">
          <p class="wrap-title">
            {{ $t('填写调试入参') }}
          </p>
          <TaskParamEdit
            ref="taskParamEdit"
            :template-id="templateId"
            :editable="tplActions.includes('MOCK')"
            :constants="pipelineTree.constants" />
          <bk-collapse
            v-if="isUnreferencedShow"
            accordion>
            <bk-collapse-item name="1">
              {{ $t('查看未引用变量') }}
              <div slot="content">
                <TaskParamEdit
                  :template-id="templateId"
                  :editable="false"
                  :constants="unReferencedConstants" />
              </div>
            </bk-collapse-item>
          </bk-collapse>
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
    <MockRecode
      :template-id="templateId"
      :node-mock-map="nodeMockMap"
      :mock-form-data="mockFormData"
      :activities="pipelineTree.activities"
      :constants="pipelineTree.constants"
      @change="updateFormData" />
  </div>
</template>

<script>
  import { mapActions, mapState } from 'vuex';
  import tools from '@/utils/tools';
  import TaskParamEdit from './components/TaskParamEdit.vue';
  import MockRecode from './components/MockRecode.vue';
  export default {
    name: 'MockExecute',
    components: {
      TaskParamEdit,
      MockRecode,
    },
    props: {
      mockTaskName: {
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
        unReferencedConstants: {},
        mockFormData: {},
        initMockData: {},
        mockDataList: [],
        rules: {},
        unMockNodes: [],
        unMockExpend: false,
      };
    },
    computed: {
      ...mapState({
        creator: state => state.username,
      }),
      isUnreferencedShow() {
        if (this.isLoading) return false;
        const variableKeys = Object.keys(this.unReferencedConstants);
        const unreferenced = variableKeys.filter(key => this.unReferencedConstants[key].show_type === 'show');
        return !!unreferenced.length;
      },
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
            is_draft: this.$route.params.isEnableVersionManage === 'true' || this.$route.params.isEnableVersionManage === true,
          });
          const {
            constants_not_referred: unReferencedConstants,
            mock_data: mockData,
            pipeline_tree: pipelineTree,
          } = resp.data;
          this.pipelineTree = pipelineTree;
          this.unReferencedConstants = unReferencedConstants;
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
      updateFormData(data) {
        const { constants, mock_data_ids } = data;

        Object.entries(mock_data_ids).forEach(([key, value]) => {
          const isMockExist = this.mockDataList.some(item => item.id === value && item.node_id === key);
          if (key in this.mockFormData && isMockExist) {
            this.mockFormData[key] = value;
          }
        });

        const { taskParamEdit: paramEditComp } = this.$refs;
        if (!paramEditComp) return;

        paramEditComp.renderData = Object.keys(constants).reduce((acc, key) => {
          if (key in paramEditComp.renderData) {
            acc[key] = constants[key].value;
          }
          return acc;
        }, {});

        this.$bkMessage({
          message: this.$t('复用成功'),
          theme: 'success',
        });
      },
      async onCreateTask() {
        try {
          if (!this.mockTaskName) return;
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
              acc.mock_data_ids[cur] = value;
            }
            return acc;
          }, {
            nodes: [],
            outputs: {},
            mock_data_ids: {},
          });
          const params = {
            name: this.mockTaskName,
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
  max-height: calc(100% - 60px);
  background: #f5f7fa;
  .left-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    margin: 24px;
  }
  .form-wrapper {
    display: flex;
    flex-direction: column;
    flex: 1;
    overflow-y: auto;
    position: relative;
    @include scrollbar;
    .wrap-title {
      font-size: 14px;
      color: #63656e;
      line-height: 22px;
      font-weight: Bold;
      margin-bottom: 16px;
    }
    .variable-wrap {
      flex: 1;
      display: flex;
      flex-direction: column;
      padding: 16px 24px;
      margin-bottom: 16px;
      background: #fff;
      box-shadow: 0 2px 4px 0 #1919290d;
    }
    .mock-wrap {
      flex: 1;
      padding: 16px 24px;
      margin-bottom: 4px;
      background: #fff;
      box-shadow: 0 2px 4px 0 #1919290d;
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
      ::v-deep .bk-label {
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
    position: sticky;
    bottom: 0;
    padding-top: 20px;
    background: #f5f7fa;
    .bk-button {
      width: 88px;
    }
  }
  ::v-deep .bk-collapse {
    margin-top: auto;
    .bk-collapse-item-header {
      font-weight: 600;
      color: #313238;
      background: #e4e6ed;
      &:hover {
        background: #e4e6ed;
      }
    }
  }
}
</style>
