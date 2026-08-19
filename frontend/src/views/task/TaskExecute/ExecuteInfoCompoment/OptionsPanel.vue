<template>
  <div>
    <bk-tab
      :active.sync="curActiveTab"
      type="unborder-card"
      ext-cls="execute-info-tab"
      @tab-change="onTabChange">
      <bk-tab-panel
        v-for="(item, index) in tabPanel"
        :key="index"
        :name="item.name"
        :label="item.label" />
    </bk-tab>
    <div class="scroll-area">
      <task-condition
        v-if="!currentNodeDetailConfig.nodeType"
        ref="conditionEdit"
        :is-readonly="true"
        :gateways="gateways"
        :condition-data="conditionData" />
      <template v-else>
        <!-- 执行次数-初始化默认显示最新执行信息 -->
        <section
          v-if="isExecuteTimeShow && !isShowSubflowExceutedCount"
          class="execute-time-section">
          <div
            v-if="loop > 1"
            class="cycle-wrap">
            <span>{{ $t('第') }}</span>
            <bk-select
              :clearable="false"
              :value="theExecuteLoop"
              @selected="onSelectExecuteLoopCount">
              <bk-option
                v-for="index in loop"
                :id="index"
                :key="index"
                :name="index" />
            </bk-select>
            <span>{{ $t('次循环') }}</span>
          </div>
          <span
            v-if="loop > 1 && historyInfo.length > 1"
            class="divid-line" />
          <div
            v-if="historyInfo.length > 1"
            class="time-wrap">
            <span>{{ $t('第') }}</span>
            <bk-select
              :clearable="false"
              :value="theExecuteRecord"
              @selected="selectExecuteCount">
              <bk-option
                v-for="index in historyInfo.length"
                :id="index"
                :key="index"
                :name="index" />
            </bk-select>
            <span>{{ $t('次执行') }}</span>
          </div>
        </section>
        <!-- 执行记录 -->
        <ExecuteRecord
          v-if="curActiveTab === 'record'"
          :admin-view="adminView"
          :location="location"
          :is-ready-status="isReadyStatus"
          :node-activity="nodeActivity"
          :execute-record="currentExecuteRecord"
          :node-detail-config="currentNodeDetailConfig"
          :plugin-code="pluginCode"
          :space-id="spaceId"
          :template-id="templateId"
          :is-sub-process-node="isSubProcessNode"
          :constants="currentExecuteRecord.constants"
          @updateOutputs="updateOutputs" />
        <!-- 配置快照 -->
        <ExecuteInfoForm
          v-else-if="curActiveTab === 'config'"
          :node-activity="nodeActivity"
          :execute-info="currentExecuteInfo"
          :node-detail-config="currentNodeDetailConfig"
          :constants="pipelineData.constants"
          :is-third-party-node="isThirdPartyNode"
          :third-party-node-code="thirdPartyNodeCode"
          :space-id="spaceId"
          :plugin-code="pluginCode"
          :template-id="templateId"
          :task_id="taskId"
          :scope-info="scopeInfo"
          :is-sub-process-node="isSubProcessNode" />
        <!-- 操作历史 -->
        <section
          v-else-if="curActiveTab === 'history'"
          class="info-section"
          data-test-id="taskExcute_form_operatFlow">
          <NodeOperationFlow
            :locations="pipelineData.location"
            :node-id="currentExecuteInfo.id"
            :sub-process-task-id="currentNodeDetailConfig.instance_id" />
        </section>
        <!-- 调用日志 -->
        <NodeLog
          v-else-if="curActiveTab === 'log'"
          ref="nodeLog"
          :admin-view="adminView"
          :node-detail-config="currentNodeDetailConfig"
          :execute-info="currentExecuteRecord"
          :third-party-node-code="thirdPartyNodeCode" />
      </template>
    </div>
  </div>
</template>

<script>
  import tools from '@/utils/tools.js';
  import { mapState, mapActions, mapMutations } from 'vuex';
  import taskCondition from '../taskCondition.vue';
  import NodeOperationFlow from './NodeOperationFlow.vue';
  import ExecuteRecord from './ExecuteRecord.vue';
  import NodeLog from './NodeLog.vue';
  import ExecuteInfoForm from './ExecuteInfoForm.vue';
  import i18n from '@/config/i18n/index.js';

  export default {
    name: 'ExecuteInfoOptionsPanel',
    components: {
      ExecuteRecord,
      ExecuteInfoForm,
      NodeOperationFlow,
      NodeLog,
      taskCondition,
    },
    props: {
        nodeDetailConfig: {
            type: Object,
            default: () => ({}),
        },
        nodeActivity: { // 节点在pipelineTree的参数信息
            type: Object,
            default: () => ({}),
        },
        location: { // 节点位置信息
            type: Object,
            default: () => ({}),
        },
        adminView: {
          type: Boolean,
          default: false,
        },
        spaceId: {
            type: Number,
            default: 0,
        },
        templateId: {
            type: [Number, String],
            default: '',
        },
        taskId: {
          type: [String, Number],
          default: '',
        },
        scopeInfo: { // api插件请求参数
          type: Object,
          default() {
            return {};
          },
        },
        pipelineData: { // 外层任务实例树
          type: Object,
          default: () => ({}),
        },
        historyInfo: { // 执行记录
          type: Array,
          default: () => ([]),
        },
        executeRecord: { // 当前执行记录信息
          type: Object,
          default: () => ({}),
        },
        isReadyStatus: {
          type: Boolean,
          default: true,
        },
        theExecuteTime: {
          type: [Number, String],
          default: undefined,
        },
        loop: { // 循环次数
          type: Number,
          default: 1,
        },
        executeInfo: { // 当前执行信息
          type: Object,
          default: () => ({}),
        },
        thirdPartyNodeCode: {
          type: String,
          default: '',
        },
        gateways: { // 外层画布的网关节点
          type: Object,
          default() {
            return {};
          },
        },
        conditionData: {
          type: Object,
          default() {
            return {};
          },
        },
        isShowSubflowExceutedCount: {
          type: Boolean,
          default: false,
        },
    },
    data() {
      return {
        curActiveTab: 'record',
        theExecuteLoop: this.theExecuteTime, // 当前选中的第几次循环
        theExecuteRecord: 0, // 当前选中的第几次执行次数
        currentNodeDetailConfig: tools.deepClone(this.nodeDetailConfig),
        currentExecuteRecord: tools.deepClone(this.executeRecord),
        currentExecuteInfo: tools.deepClone(this.executeInfo),
        gatewayStartEndType: ['parallel-gateway', 'converge-gateway', 'branch-gateway', 'conditional-parallel-gateway', 'empty-end-event', 'empty-start-event'],
      };
    },
    computed: {
      ...mapState({
        atomFormConfig: state => state.atomForm.config,
        atomOutputConfig: state => state.atomForm.outputConfig,
        atomFormInfo: state => state.atomForm.form,
        pluginOutput: state => state.atomForm.output,
      }),
      ...mapState('project', {
        project_id: state => state.project_id,
      }),
      // 是否显示执行次数/循环次数
      isExecuteTimeShow() {
        return ['record', 'log'].includes(this.curActiveTab) && (this.loop > 1 || this.historyInfo.length > 1);
      },
      pluginCode() {
        return this.currentNodeDetailConfig.component_code;
      },
      isThirdPartyNode() {
        return this.pluginCode === 'remote_plugin';
      },
      isSubProcessNode() {
        return this.pluginCode === 'subprocess_plugin';
      },
      // 并行网关、汇聚网关、并行条件、分支网关没有配置快照 条件只有配置快照
      isNeedShowConfig() {
        const { nodeType } = this.currentNodeDetailConfig;
        if (this.gatewayStartEndType.includes(nodeType)) {
          return false;
        }
        return true;
      },
      isCondition() {
        const { nodeType } = this.currentNodeDetailConfig;
        if (this.gatewayStartEndType.includes(nodeType) || nodeType === 'task' || nodeType === 'tasknode') {
          return false;
        }
        return true;
      },
      tabPanel() {
        const baseTabs = [
          { label: i18n.t('执行记录'), name: 'record' },
          { label: i18n.t('操作历史'), name: 'history' },
          { label: i18n.t('调用日志'), name: 'log' },
        ];
        const configTab = { label: i18n.t('配置快照'), name: 'config' };
        const shouldShowConfig = this.isNeedShowConfig || ['tasknode', 'subflow', 'ServiceActivity', 'SubProcess'].includes(this.location.type);
        if (this.isCondition) {
          return [configTab];
        } if (shouldShowConfig) {
         return [baseTabs[0], configTab, ...baseTabs.slice(1)];
        }
        return baseTabs;
      },
    },
    watch: {
      executeRecord: {
        handler(val) {
          this.currentExecuteRecord = tools.deepClone(val);
        },
        deep: true,
      },
      theExecuteTime(val) {
        this.theExecuteLoop = tools.deepClone(val);
      },
      historyInfo: {
        handler(val, oldVal) {
          if (!tools.isDataEqual(val, oldVal)) {
            this.theExecuteRecord  = val.length;
          }
        },
        deep: true,
        immediate: true,
      },
      executeInfo: {
        handler(val) {
          this.currentExecuteInfo = tools.deepClone(val);
          this.curActiveTab = 'record';
        },
        deep: true,
        immediate: true,
      },
      nodeDetailConfig: {
        handler(val) {
          this.currentNodeDetailConfig = tools.deepClone(val);
        },
        deep: true,
        immediate: true,
      },
    },
    mounted() {
    },
    methods: {
      ...mapActions('task/', [
        'getNodeActDetail',
        'loadSubflowConfig',
        'getInstanceStatus',
        'getTaskInstanceData',
      ]),
      ...mapActions('template/', [
        'loadUniformApiMeta',
      ]),
      ...mapActions('atomForm/', [
        'loadAtomConfig',
        'loadPluginServiceDetail',
        'loadPluginServiceAppDetail',
      ]),
      ...mapMutations('task/', [
        'setNodeDetailActivityPanel',
      ]),
      // 选项卡切换
      onTabChange(name) {
        this.curActiveTab = name;
        this.setNodeDetailActivityPanel(name);
        if (['record', 'log'].includes(name)) {
          this.$emit('selectExecuteRecord', this.theExecuteRecord, this.historyInfo);
        }
      },
      // 执行记录
      // 切换执行次数
      selectExecuteCount(value) {
        this.theExecuteRecord = value;
        this.$emit('selectExecuteRecord', value, this.historyInfo);
      },
      // 切换循环次数
      onSelectExecuteLoopCount(value) {
        this.theExecuteLoop = value;
        this.$emit('selectExecuteLoop', value);
      },
      updateOutputs(outputs) {
        this.currentExecuteRecord.outputsInfo = this.currentExecuteRecord.outputsInfo.reduce((acc, cur) => {
          const info = outputs.find(item => [cur.name].includes(item.key));
          if (info) {
            acc.push({
              ...cur,
              name: info.name,
            });
          } else {
            acc.push(cur);
          }
          return acc;
        }, []);
      },
    },
  };
</script>

<style lang="scss">
    .log-info {
        .common-section-title {
            margin-bottom: 10px;
        }
        .bk-tab-header {
            top: -10px;
        }
        .bk-tab-section {
            padding: 0px;
        }
        .no-data-wrapper {
            margin-top: 50px;
        }
    }
</style>
<style lang="scss" scoped>
@import '@/scss/mixins/scrollbar.scss';
@import '@/scss/config.scss';
.execute-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding-bottom: 0;
    width: 500px;
    height: 100%;
    color: #313238;
    &.loading {
        overflow: hidden;
    }
    &.admin-view {
        .code-block-wrap {
            background: #313238;
            padding: 10px;
            ::v-deep .vjs-tree {
                color: #ffffff;
            }
        }
    }
    ::v-deep .vjs-tree {
        font-size: 12px;
    }
    .execute-body{
      overflow-y: auto;
      @include scrollbar;
    }
    ::v-deep .execute-info-tab .bk-tab-section{
        padding: 0;
    }
    .scroll-area {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow-y: auto;
        padding: 16px 24px 16px 16px;
        height: 100%;
        @include scrollbar;
    }
    .execute-time-section {
        display: flex;
        align-items: center;
        height: 40px;
        font-size: 12px;
        padding: 8px 16px;
        background: #f5f7fa;
        margin-bottom: 24px;
        .cycle-wrap,
        .time-wrap {
            display: flex;
            align-items: center;
            ::v-deep .bk-select {
                width: 64px;
                height: 24px;
                line-height: 22px !important;
                margin: 0 8px;
                .bk-select-angle {
                    top: 0;
                }
                .bk-select-name {
                    height: 24px;
                }
            }
        }
        .divid-line {
            display: inline-block;
            width: 1px;
            height: 16px;
            margin: 0 16px;
            background: #dcdee5;
        }
    }
    .panel-title {
        margin: 0;
        color: #313238;
        font-size: 14px;
        font-weight: 600;
    }
    ::v-deep .common-section-title {
        color: #313238;
        font-weight: 600;
        line-height: 18px;
        font-size: 12px;
        margin-bottom: 16px;
        &::before {
            height: 18px;
            top: 0;
        }
    }
    .common-icon-dark-circle-ellipsis {
        font-size: 14px;
        color: #3a84ff;
    }
    .common-icon-dark-circle-pause {
        font-size: 14px;
        color: #f8B53f;
    }
    .icon-check-circle-shape {
        font-size: 14px;
        color: #30d878;
    }
    .common-icon-dark-circle-close {
        font-size: 14px;
        color: #ff5757;
    }
    .common-icon-waitting {
        font-size: 16px;
        color: #dcdee5;
    }
    .common-icon-fail-skip {
        font-size: 14px;
        color: #f7b6b6;
    }
    .icon-circle-shape {
        display: inline-block;
        height: 14px;
        width: 14px;
        background: #f0f1f5;
        border: 1px solid #c4c6cc;
        border-radius: 50%;
        &::before {
            content: initial;
        }
    }
    ::v-deep .primary-value.code-editor {
        height: 300px;
    }
}
// 子流程画布
.sub-process{
  position: relative;
  margin: 0 25px 8px 15px;
    .flow-option {
        width: 68px;
        height: 32px;
        position: absolute;
        bottom: 16px;
        right: 16px;
        z-index: 5;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        color: #979ba5;
        background: #fff;
        box-shadow: 0 2px 4px 0 #0000001a;
        border-radius: 2px;
        i {
            cursor: pointer;
            &:last-child {
                margin-left: 14px;
            }
            &:hover {
                color: #3a84ff;
            }
            &.disabled {
                color: #ccc;
                cursor: not-allowed;
            }
        }
  }
}
</style>
