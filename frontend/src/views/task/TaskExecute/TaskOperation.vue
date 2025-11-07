/**
* Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
* Edition) available.
* Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
* Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
* http://opensource.org/licenses/MIT
* Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
* an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
* specific language governing permissions and limitations under the License.
*/
<template>
  <div class="task-operation">
    <task-operation-header
      :node-nav="nodeNav"
      :space-id="spaceId"
      :template-id="templateId"
      :primitive-tpl-id="primitiveTplId"
      :primitive-tpl-source="primitiveTplSource"
      :template-source="templateSource"
      :node-info-type="nodeInfoType"
      :task-operation-btns="taskOperationBtns"
      :instance-actions="instanceActions"
      :admin-view="adminView"
      :state-str="taskState"
      :state="state"
      :is-breadcrumb-show="isBreadcrumbShow"
      :is-show-view-process="isShowViewProcess"
      :is-task-operation-btns-show="isTaskOperationBtnsShow"
      :params-can-be-modify="paramsCanBeModify"
      :trigger-method="triggerMethod"
      :parent-task-info="parentTaskInfo"
      @onOperationClick="onOperationClick"
      @onTaskParamsClick="onTaskParamsClick"
      @onInjectGlobalVariable="onInjectGlobalVariable" />
    <bk-alert
      v-if="isFailedSubproceeNodeInfo"
      type="error"
      class="subprocess-failed-tips">
      <template slot="title">
        <span>{{ $t('存在子流程节点执行失败，可从节点执行记录去往子任务处理，并及时') }}</span>
        <bk-link
          theme="primary"
          @click="handleRefreshTaskStatus">
          {{ $t('刷新任务状态') }}
        </bk-link>
        {{ $t('。') }}
      </template>
    </bk-alert>
    <div class="task-container">
      <div class="pipeline-nodes">
        <component
          :is="templateComponentName"
          v-if="!nodeSwitching"
          ref="processCanvas"
          class="canvas-comp-wrapper"
          :editable="false"
          :show-palette="false"
          :canvas-data="canvasData"
          :node-variable-info="nodeVariableInfo"
          :is-execute="true"
          :template-id="templateId"
          :instance-id="instanceId"
          :space-id="spaceId"
          :overall-state="state"
          @onNodeClick="onNodeClick"
          @onConditionClick="onOpenConditionEdit"
          @onRetryClick="onRetryClick"
          @onForceFail="onForceFailClick"
          @onSkipClick="onSkipClick"
          @onModifyTimeClick="onModifyTimeClick"
          @onGatewaySelectionClick="onGatewaySelectionClick"
          @onTaskNodeResumeClick="onTaskNodeResumeClick"
          @onApprovalClick="onApprovalClick"
          @onTogglePerspective="onTogglePerspective"
          @onSubprocessPauseResumeClick="onSubprocessPauseResumeClick" />
      </div>
    </div>
    <bk-sideslider
      :is-show.sync="isNodeInfoPanelShow"
      :width="960"
      :quick-close="true"
      :before-close="onBeforeClose"
      @hidden="onHiddenSideslider">
      <div slot="header">
        <div class="header">
          <span>{{ sideSliderTitle }}</span>
        </div>
      </div>
      <div
        v-if="isNodeInfoPanelShow"
        ref="nodeInfoPanel"
        slot="content"
        class="node-info-panel">
        <ModifyParams
          v-if="nodeInfoType === 'modifyParams'"
          ref="modifyParams"
          :state="state"
          :params-can-be-modify="paramsCanBeModify"
          :instance-actions="instanceActions"
          :instance-name="instanceName"
          :instance_id="instanceId"
          :template-id="templateId"
          :retry-node-id="retryNodeId"
          @nodeTaskRetry="nodeTaskRetry"
          @packUp="packUp" />
        <ExecuteInfo
          v-if="nodeInfoType === 'executeInfo' || nodeInfoType === 'viewNodeDetails'"
          ref="executeInfo"
          :state="state"
          :node-data="nodeData"
          :node-nav="nodeNav"
          :node-display-status="nodeDisplayStatus"
          :selected-flow-path="selectedFlowPath"
          :admin-view="adminView"
          :pipeline-data="nodePipelineData"
          :default-active-id="defaultActiveId"
          :is-condition="isCondition"
          :node-detail-config="nodeDetailConfig"
          :is-readonly="true"
          :constants="pipelineData.constants"
          :gateways="pipelineData.gateways"
          :condition-data="conditionData"
          :space-id="spaceId"
          :task-id="taskId"
          :scope-info="scopeInfo"
          :template-id="templateId"
          :instance-actions="instanceActions"
          @onOpenConditionInfo="onOpenConditionInfo"
          @onRetryClick="onRetryClick"
          @onSkipClick="onSkipClick"
          @onForceFail="onForceFailClick"
          @onModifyTimeClick="onModifyTimeClick"
          @onTaskNodeResumeClick="onTaskNodeResumeClick"
          @onApprovalClick="onApprovalClick"
          @onClickTreeNode="onClickTreeNode" />
        <RetryNode
          v-if="nodeInfoType === 'retryNode'"
          ref="retryNode"
          :node-detail-config="nodeDetailConfig"
          :node-info="nodeInfo"
          :retrying="pending.retry"
          :node-inputs="nodeInputs"
          @retrySuccess="onRetrySuccess"
          @retryCancel="onRetryCancel" />
        <ModifyTime
          v-if="nodeInfoType === 'modifyTime'"
          ref="modifyTime"
          :node-detail-config="nodeDetailConfig"
          @modifyTimeSuccess="onModifyTimeSuccess"
          @modifyTimeCancel="onModifyTimeCancel" />
        <OperationFlow
          v-if="nodeInfoType === 'operateFlow'"
          :locations="canvasData.locations"
          class="operation-flow" />
        <GlobalVariable
          v-if="nodeInfoType === 'globalVariable'"
          :task-id="instanceId" />
        <TaskInfo
          v-if="nodeInfoType === 'taskExecuteInfo'"
          :task-id="instanceId" />
        <TemplateData
          v-if="nodeInfoType === 'templateData'"
          :template-data="templateData"
          @onshutDown="onshutDown" />
      </div>
    </bk-sideslider>
    <gatewaySelectDialog
      :is-gateway-select-dialog-show="isGatewaySelectDialogShow"
      :is-cond-parallel-gw="isCondParallelGw"
      :gateway-branches="gatewayBranches"
      @onConfirm="onConfirmGatewaySelect"
      @onCancel="onCancelGatewaySelect" />
    <injectVariableDialog
      :is-inject-var-dialog-show="isInjectVarDialogShow"
      @onConfirmInjectVar="onConfirmInjectVar"
      @onCancelInjectVar="onCancelInjectVar" />
    <bk-dialog
      width="600"
      :theme="'primary'"
      :mask-close="false"
      :auto-close="false"
      header-position="left"
      :title="$t('审批')"
      :loading="approval.pending"
      :value="approval.dialogShow"
      @confirm="onApprovalConfirm"
      @cancel="onApprovalCancel">
      <bk-form
        ref="approvalForm"
        class="approval-dialog-content"
        form-type="vertical"
        :model="approval"
        :rules="approval.rules">
        <bk-form-item
          :label="$t('审批意见')"
          :required="true">
          <bk-radio-group
            v-model="approval.is_passed"
            @change="$refs.approvalForm.clearError()">
            <bk-radio :value="true">
              {{ $t('通过') }}
            </bk-radio>
            <bk-radio :value="false">
              {{ $t('拒绝') }}
            </bk-radio>
          </bk-radio-group>
        </bk-form-item>
        <bk-form-item
          :label="$t('备注')"
          property="message"
          :required="!approval.is_passed">
          <bk-input
            v-model="approval.message"
            type="textarea"
            :row="4" />
        </bk-form-item>
      </bk-form>
    </bk-dialog>
  </div>
</template>
<script>
  import i18n from '@/config/i18n/index.js';
  import { mapActions, mapState } from 'vuex';
  import axios from 'axios';
  import tools from '@/utils/tools.js';
  import { TASK_STATE_DICT, NODE_DICT } from '@/constants/index.js';
  import ModifyParams from './ModifyParams.vue';
  // import ExecuteInfo from './ExecuteInfo.vue';
  import ExecuteInfo from './SideDrawerExecuteInfo.vue';
  import RetryNode from './RetryNode.vue';
  import ModifyTime from './ModifyTime.vue';
  import OperationFlow from './OperationFlow.vue';
  import GlobalVariable from './GlobalVariable.vue';
  import TaskInfo from './TaskInfo.vue';
  import gatewaySelectDialog from './GatewaySelectDialog.vue';
  import permission from '@/mixins/permission.js';
  import TaskOperationHeader from './TaskOperationHeader';
  import TemplateData from './TemplateData';
  import injectVariableDialog from './InjectVariableDialog.vue';
  import tplPerspective from '@/mixins/tplPerspective.js';
  import { graphToJson } from '@/utils/graphJson.js';
  import VerticalCanvas from '@/components/canvas/VerticalCanvas/index.vue';
  import ProcessCanvas from '@/components/canvas/ProcessCanvas/index.vue';
  import StageCanvas from '@/components/canvas/StageCanvas/index.vue';

  const { CancelToken } = axios;
  let source = CancelToken.source();

  const TASK_OPERATIONS = {
    execute: {
      action: 'execute',
      icon: 'common-icon-right-triangle',
      text: i18n.t('执行'),
    },
    pause: {
      action: 'pause',
      icon: 'common-icon-double-vertical-line',
      text: i18n.t('暂停'),
    },
    resume: {
      action: 'resume',
      icon: 'common-icon-right-triangle',
      text: i18n.t('继续'),
    },
    revoke: {
      action: 'revoke',
      icon: 'common-icon-stop',
      text: i18n.t('终止'),
    },
  };
  // 执行按钮的变更
  const STATE_OPERATIONS = {
    RUNNING: 'pause',
    SUSPENDED: 'resume',
    CREATED: 'execute',
    FAILED: 'pause',
  };
  export default {
    name: 'TaskOperation',
    components: {
      ModifyParams,
      ExecuteInfo,
      RetryNode,
      ModifyTime,
      OperationFlow,
      GlobalVariable,
      TaskInfo,
      gatewaySelectDialog,
      TaskOperationHeader,
      TemplateData,
      injectVariableDialog,
      ProcessCanvas,
      VerticalCanvas,
      StageCanvas,
    },
    mixins: [permission, tplPerspective],
    props: {
      spaceId: {
        type: [Number, String],
        default: '',
      },
      instanceId: {
        type: [Number, String],
        default: '',
      },
      instanceFlow: {
        type: Object,
        default: () => ({}),
      },
      instanceName: {
        type: String,
        default: '',
      },
      primitiveTplId: {
        type: [Number, String],
        default: '',
      },
      primitiveTplSource: {
        type: String,
        default: '',
      },
      templateSource: {
        type: String,
        default: '',
      },
      instanceActions: {
        type: Array,
        default: () => ([]),
      },
      routerType: {
        type: String,
        default: '',
      },
      scopeInfo: {
        type: Object,
        default: () => ({}),
      },
      createMethod: {
        type: String,
        default: '',
      },
      canvasMode: {
        type: String,
        default: '',
      },
      templateId: {
        type: [Number, String],
        default: '',
      },
      triggerMethod: {
        type: String,
        default: '',
      },
      parentTaskInfo: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      const $this = this;
      const pipelineData = { ...this.instanceFlow };
      const path = [];
      path.push({
        id: this.instanceId,
        name: this.instanceName,
        nodeId: pipelineData.id,
        type: 'root',
      });

      return {
        templateData: '', // 模板数据
        defaultActiveId: '',
        setNodeDetail: true,
        atomList: [],
        sideSliderTitle: '',
        taskId: this.instanceId,
        isNodeInfoPanelShow: false,
        nodeInfoType: '',
        state: '', // 当前流程状态，画布切换时会更新
        rootState: '', // 根流程状态
        selectedNodeId: '',
        selectedFlowPath: path, // 选择面包屑路径
        cacheStatus: undefined, // 总任务缓存状态信息；只有总任务完成、终止时才存在
        instanceStatus: {},
        taskParamsType: '',
        timer: null,
        pipelineData,
        treeNodeConfig: {},
        nodeDetailConfig: {},
        nodeSwitching: false,
        isGatewaySelectDialogShow: false,
        isCondParallelGw: false,
        gatewayBranches: [],
        canvasMountedQueues: [], // canvas pending queues
        pending: {
          skip: false,
          retry: false,
          forceFail: false,
          selectGateway: false,
          task: false,
          parseNodeResume: false,
          subflowPause: false,
          subflowResume: false,
        },
        activeOperation: '', // 当前任务操作（头部区域操作按钮触发）
        retryNodeId: undefined,
        operateLoading: false,
        retrievedCovergeGateways: [], // 遍历过的汇聚节点
        pollErrorTimes: 0, // 任务状态查询异常连续三次后，停止轮询
        conditionData: {},
        tabIconState: '',
        approval: { // 节点审批
          id: '',
          dialogShow: false,
          pending: false,
          is_passed: true, // 是否通过
          message: '', // 备注信息
          rules: {
            message: [{
              validator(val) {
                console.log($this.approval.is_passed, val);
                return $this.approval.is_passed || val !== '';
              },
              message: i18n.t('必填项'),
              trigger: 'blur',
            }],
          },
        },
        nodePipelineData: {},
        isFailedSubproceeNodeInfo: null,
        nodeInfo: {},
        nodeInputs: {},
        isExecRecordOpen: false,
        nodeExecRecordInfo: {},
        isInjectVarDialogShow: false,
        nodeIds: [],
        nodeDisplayStatus: {},
        showNodeList: [0, 1, 2],
        converNodeList: [],
        isCondition: false,
        conditionOutgoing: [],
        translateNodeType: {
          ParallelGateway: 'parallel-gateway',
          ConvergeGateway: 'converge-gateway',
          ExclusiveGateway: 'branch-gateway',
          ConditionalParallelGateway: 'conditional-parallel-gateway',
          ServiceActivity: 'task',
          EmptyEndEvent: 'empty-end-event',
          EmptyStartEvent: 'empty-start-event',
          SubProcess: 'task',
        },
        subflowInfo: {}, // 子流程根节点id和任务id
      };
    },
    computed: {
      ...mapState({
        view_mode: state => state.view_mode,
        infoBasicConfig: state => state.infoBasicConfig,
        locations: state => state.template.location,
      }),
      ...mapState('project', {
        projectName: state => state.projectName,
      }),
      ...mapState('task', {
        subActivities: state => state.subActivities,
      }),
      completePipelineData() {
        return { ...this.instanceFlow };
      },
      isBreadcrumbShow() {
        return this.completePipelineData.location.some(item => item.type === 'subflow');
      },
      canvasData() {
        const { line, location, activities } = { ... tools.deepClone(this.instanceFlow)};
        const locations = location.map((item) => {
          const code = item.type === 'tasknode' ? activities[item.id].component.code : '';
          const mode = this.hasOperatePerm ? 'execute' : '';
          return { ...item, mode, checked: true, code, ready: true };
        });
        return graphToJson({
          locations,
          lines: line,
        });
      },
      previewData() {
        return tools.deepClone(this.pipelineData);
      },
      common() {
        return this.templateSource !== 'project';
      },
      nodeData() {
        const data = this.getOrderedTree(this.completePipelineData);// 外层无子流程的节点pipelineTree
        data.forEach((item) => {
          if (item?.component?.code === 'subprocess_plugin') {
            this.addUnexecued(item);
          }
        });
        // data.forEach((item) => {
        //   if (item.id === this.defaultActiveId) {
        //     item.expanded = true;
        //   } else if (!item.children) {
        //     item.expanded = false;
        //   }
        //   if (item.children) {
        //     item.children.forEach((item) => {
        //       if (item.id === this.defaultActiveId) {
        //         item.expanded = true;
        //       }
        //     });
        //   }
        // });
        return [{
          id: this.instanceId,
          name: this.instanceName,
          title: this.instanceName,
          expanded: true,
          children: data,
        }];
      },
      taskState() {
        return TASK_STATE_DICT[this.state];
      },
      nodeNav() {
        return this.selectedFlowPath?.filter(item => item.type !== 'ServiceActivity');
      },
      // 当前画布是否为最外层
      isTopTask() {
        return this.nodeNav.length === 1;
      },
      isTaskOperationBtnsShow() {
        return this.state !== 'REVOKED' && this.state !== 'FINISHED';
      },
      taskOperationBtns() {
        const operationBtns = [];
        const operationType = STATE_OPERATIONS[this.state];
        if (this.state && operationType) {
          const executePauseBtn = Object.assign({}, TASK_OPERATIONS[operationType]);
          const revokeBtn = Object.assign({}, TASK_OPERATIONS.revoke);

          if (this.pending.task) {
            executePauseBtn.loading = this.activeOperation === executePauseBtn.action;
            revokeBtn.loading = this.activeOperation === revokeBtn.action;
          }

          executePauseBtn.disabled = !this.getOptBtnIsClickable(executePauseBtn.action);
          revokeBtn.disabled = !this.getOptBtnIsClickable(revokeBtn.action);

          operationBtns.push(executePauseBtn, revokeBtn);
        }
        return operationBtns;
      },
      paramsCanBeModify() {
        return this.isTopTask && !['FINISHED', 'REVOKED'].includes(this.state);
      },
      // 只有mock任务才可以跳转到流程
      isShowViewProcess() {
        return this.createMethod === 'MOCK';
      },
      adminView() {
        return false;
      },
      hasOperatePerm() {
        return this.instanceActions.includes('OPERATE');
      },
      templateComponentName() {
          const canvasModeToComponentMap = {
            horizontal: 'ProcessCanvas',
            vertical: 'VerticalCanvas',
            stage: 'StageCanvas',
          };
          return canvasModeToComponentMap[this.canvasMode] || canvasModeToComponentMap.horizontal;
      },
    },
    watch: {
      instanceFlow: {
        handler(val) {
          this.loadTaskStatus();
        },
        deep: true,
      },
    },
    mounted() {
      this.loadMockData();
      this.loadTaskStatus();
      this.getSingleAtomList();
      const { is_now: isNow } = this.$route.params;
      if (isNow) {
        this.$nextTick(() => {
          this.onOperationClick('execute');
        });
      }
    },
    beforeDestroy() {
      if (source) {
        source.cancel('cancelled');
      }
      this.cancelTaskStatusTimer();
    },
    methods: {
      ...mapActions('task/', [
        'getTaskMockData',
        'getInstanceStatus',
        'instanceStart',
        'instancePause',
        'subInstancePause',
        'instanceResume',
        'subInstanceResume',
        'instanceOperate',
        'instanceNodeOperate',
        'instanceRevoke',
        'instanceNodeSkip',
        'instanceBranchSkip',
        'pauseNodeResume',
        'getNodeActInfo',
        'forceFail',
        'itsmTransition',
        'getInstanceRetryParams',
        'getNodeExecutionRecord',
        'instanceRetry',
        'subflowNodeRetry',
        'loadSubflowConfig',
        'getNodeActDetail',
      ]),
      ...mapActions('atomForm/', [
        'loadSingleAtomList',
      ]),
      ...mapActions('admin/', [
        'taskFlowUpdateContext',
      ]),
      addUnexecued(node) {
        if (node.children) {
          node.children.forEach((item) => {
              item.isFirstSubUnexecuted = true; // 顶层子流程是否未执行
              if (item.children) {
                this.addUnexecued(item);
              }
          });
        }
      },
      async loadMockData() {
        try {
          if (this.createMethod !== 'MOCK') return;
          const resp = await this.getTaskMockData({ id: this.taskId, spaceId: this.spaceId });
          const { nodes = [] } = resp.data.data;
          nodes.forEach((node) => {
            this.setTaskNodeStatus(node, { create_method: 'mock' });
          });
        } catch (error) {
          console.warn(error);
        }
      },
      async loadTaskStatus() {
        try {
          let instanceStatus = {};
          if (['FINISHED', 'REVOKED'].includes(this.state) && this.cacheStatus && this.cacheStatus.children[this.taskId]) { // 总任务：完成/终止时,取实例缓存数据
            instanceStatus = await this.getGlobalCacheStatus(this.taskId);
          } else if (
            this.instanceStatus.state
            && this.instanceStatus.state === 'FINISHED' // 任务实例才会出现终止，子流程不存在
            && this.instanceStatus.children
            && this.instanceStatus.children[this.taskId]
          ) { // 局部：完成时，取局部缓存数据
            instanceStatus = await this.getLocalCacheStatus();
          } else {
            if (source) {
              source.cancel('cancelled'); // 取消定时器里已经执行的请求
            }
            source = CancelToken.source();
            const data = {
              instance_id: this.taskId,
              project_id: this.project_id,
              cancelToken: source.token,
            };
            if (!this.isTopTask) {
              data.instance_id = this.instanceId;
              data.subprocess_id = this.taskId;
            }
            instanceStatus = await this.getInstanceStatus(data);
          }
          // 处理返回数据
          if (instanceStatus.result) {
            this.state = instanceStatus.data.state;
            this.instanceStatus = instanceStatus.data;
            this.pollErrorTimes = 0;
            if (this.isTopTask) {
              this.rootState = this.state;
            }
            if (
              !this.cacheStatus
              && ['FINISHED', 'REVOKED'].includes(this.state)
              && this.taskId === this.instanceId
            ) { // save cacheStatus
              this.cacheStatus = instanceStatus.data;
            }
            // 任务暂停时如果有节点正在执行，需轮询节点状态
            let suspendedRunning = false;
            if (this.state === 'SUSPENDED') {
              suspendedRunning = Object.values(instanceStatus.data.children).some(item => item.state === 'RUNNING');
            }
            // 节点执行记录显示时，重新计算当前执行时间/判断是否还在执行中
            if (this.isExecRecordOpen) {
              const execNodeConfig = this.instanceStatus.children[this.nodeExecRecordInfo.nodeId];
              if (execNodeConfig) {
                const elapsedTime = this.formatDuring(execNodeConfig.elapsed_time);
                if (execNodeConfig.state === 'RUNNING') {
                  this.nodeExecRecordInfo.curTime = elapsedTime;
                } else if (this.nodeExecRecordInfo.curTime) {
                  // 如果节点执行完成，需要把当前执行的时间插入到执行历史里面，count + 1
                  this.nodeExecRecordInfo.curTime = '';
                  this.nodeExecRecordInfo.execTime.unshift(elapsedTime);
                  this.nodeExecRecordInfo.count += 1;
                }
                this.nodeExecRecordInfo.state = execNodeConfig.state;
              }
            }
            if (this.state === 'RUNNING' || (!this.isTopTask && this.state === 'FINISHED' && !['FINISHED', 'REVOKED', 'FAILED'].includes(this.rootState)) || suspendedRunning) {
              if (this.isExecRecordOpen && this.nodeExecRecordInfo.state) { // 节点执行中一秒查一次
                this.setTaskStatusTimer(1000);
              } else {
                this.setTaskStatusTimer();
              }
              this.setRunningNode(instanceStatus.data.children);
            }
            this.updateNodeInfo();
          } else {
            // 查询流程状态接口返回失败后再请求一次
            this.pollErrorTimes += 1;
            if (this.pollErrorTimes > 2) {
              this.cancelTaskStatusTimer();
            } else {
              this.setTaskStatusTimer();
            }
          }
          this.nodeDisplayStatus = tools.deepClone(this.instanceStatus);
        } catch (e) {
          this.cancelTaskStatusTimer();
          if (e.message !== 'cancelled') {
            console.log(e);
          }
        } finally {
          source = null;
        }
      },
      /**
       * 加载标准插件列表
       */
      async getSingleAtomList() {
        try {
          const params = {
            space_id: this.spaceId,
          };
          const data = await this.loadSingleAtomList(params);
          const atomList = [];
          data.forEach((item) => {
            const atom = atomList.find(atom => atom.code === item.code);
            if (atom) {
              atom.list.push(item);
            } else {
              const { code, desc, name, group_name, group_icon } = item;
              atomList.push({
                code,
                desc,
                name,
                group_name,
                group_icon,
                type: group_name,
                list: [item],
              });
            }
          });
          this.atomList = atomList;
          this.markNodesPhase();
        } catch (e) {
          console.log(e);
        } finally {
          this.singleAtomListLoading = false;
        }
      },
      /**
       * 标记任务节点的生命周期
       */
      markNodesPhase() {
        Object.keys(this.pipelineData.activities).forEach((id) => {
          const node = this.pipelineData.activities[id];
          if (node.type === 'ServiceActivity') {
            let atom = '';
            this.atomList.some((group) => {
              let result = false;
              if (group.code === node.component.code) {
                result = group.list.some((item) => {
                  if (item.version === (node.component.version || 'legacy')) {
                    atom = item;
                    result = true;
                  }
                  return result;
                });
              }
              return result;
            });
            if (atom) {
              this.$refs.processCanvas.onUpdateNodeInfo(node.id, { phase: atom.phase });
            }
          }
        });
      },
      /**
       * 从总任务实例状态信息中取数据
       */
      getGlobalCacheStatus() {
        return new Promise((resolve) => {
          const levels = this.nodeNav.map(nav => nav.id).slice(1);
          let instanStatus = tools.deepClone(this.cacheStatus);
          levels.forEach((subNodeId) => {
            instanStatus = instanStatus.children[subNodeId];
          });
          setTimeout(() => {
            resolve({
              data: instanStatus,
              result: true,
            });
          }, 0);
        });
      },
      /**
       * 获取局部（子流程）缓存状态数据
       * @description
       * 待jsFlow更新 updateCanvas 方法解决后删除异步代码，
       * 然后使用 updateCanvas 替代 v-if
       */
      getLocalCacheStatus() {
        return new Promise((resolve) => {
          const cacheStatus = this.instanceStatus.children;
          setTimeout(() => {
            resolve({
              data: cacheStatus[this.taskId],
              result: true,
            });
          }, 0);
        });
      },
      async taskExecute() {
        try {
          const res = await this.instanceOperate({
            instance_id: this.instanceId,
            operation: 'start',
          });
          if (res.result) {
            this.state = 'RUNNING';
            this.setTaskStatusTimer();
            this.$bkMessage({
              message: i18n.t('任务开始执行'),
              theme: 'success',
            });
          }
        } catch (e) {
          console.log(e);
        } finally {
          this.pending.task = false;
        }
      },
      async taskPause(subflowPause, nodeId) {
        let res;
        try {
          if (!this.isTopTask || subflowPause) { // 子流程画布暂停或子流程节点暂停
            const data = {
              instance_id: this.instanceId,
              node_id: nodeId || this.taskId,
            };
            res = await this.subInstancePause(data);
          } else {
            res = await this.instanceOperate({
              instance_id: this.instanceId,
              operation: 'pause',
            });
          }
          if (res.result) {
            this.state = 'SUSPENDED';
            this.$bkMessage({
              message: i18n.t('任务已暂停执行'),
              theme: 'success',
            });
          }
        } catch (e) {
          console.log(e);
        } finally {
          this.pending.task = false;
        }
      },
      async taskResume(subflowResume, nodeId) {
        let res;
        try {
          if (!this.isTopTask || subflowResume) {
            const data = {
              instance_id: this.instanceId,
              node_id: nodeId || this.taskId,
            };
            res = await this.subInstanceResume(data);
          } else {
            res = await this.instanceOperate({
              instance_id: this.instanceId,
              operation: 'resume',
            });
          }
          if (res.result) {
            this.state = 'RUNNING';
            this.setTaskStatusTimer();
            this.$bkMessage({
              message: i18n.t('任务已继续执行'),
              theme: 'success',
            });
          }
        } catch (e) {
          console.log(e);
        } finally {
          this.pending.task = false;
        }
      },
      async taskRevoke() {
        try {
          this.activeOperation = 'revoke';
          const res = await this.instanceOperate({
            instance_id: this.instanceId,
            operation: 'revoke',
          });
          if (res.result) {
            this.state = 'REVOKED';
            this.$bkMessage({
              message: i18n.t('任务终止成功'),
              theme: 'success',
            });
            setTimeout(() => {
              this.setTaskStatusTimer();
            }, 1000);
          }
        } catch (e) {
          console.log(e);
        } finally {
          this.pending.task = false;
        }
      },
      async updateExecuteInfo() {
        const execInfoInstance = this.$refs.executeInfo;
        try {
          execInfoInstance.loading = true;
          await execInfoInstance.loadNodeInfo();
          execInfoInstance.setTaskStatusTimer();
        } catch (error) {
          execInfoInstance.loading = false;
        }
      },
      async nodeTaskSkip(id, subflowInfo, isTopSubflow) {
        if (this.pending.skip) {
          return;
        }

        this.pending.skip = true;
        this.isFailedSubproceeNodeInfo = null;
        try {
          const data = {
            instance_id: subflowInfo?.taskId || this.instanceId,
            node_id: id,
            operation: 'skip',
          };
          const res = await this.instanceNodeOperate(data);
          if (res.result) {
            this.$bkMessage({
              message: i18n.t('跳过成功'),
              theme: 'success',
            });
            if (subflowInfo?.taskId || isTopSubflow) {
              this.updateExecuteInfo();
            } else {
              this.nodeInfoType = '';
              this.isNodeInfoPanelShow = false;
            }
            setTimeout(() => {
                this.setTaskStatusTimer();
              }, 1000);
          }
        } catch (e) {
          console.log(e);
        } finally {
          this.pending.skip = false;
        }
      },
      async nodeForceFail(id, subflowInfo) {
        if (this.pending.forceFail) {
          return;
        }
        this.pending.forceFail = true;
        try {
          const params = {
            instance_id: subflowInfo?.taskId || this.instanceId,
            node_id: id,
            operation: 'forced_fail',
          };
          const res = await this.instanceNodeOperate(params);
          if (res.result) {
            this.$bkMessage({
              message: i18n.t('强制终止执行成功'),
              theme: 'success',
            });
            // this.nodeInfoType = '';
            if (subflowInfo?.taskId) {
              this.updateExecuteInfo();
            } else {
              this.nodeInfoType = '';
              this.isNodeInfoPanelShow = false;
            }
            setTimeout(() => {
              this.setTaskStatusTimer();
            }, 1000);
          }
        } catch (e) {
          console.log(e);
        } finally {
          this.pending.forceFail = false;
        }
      },
      async selectGatewayBranch(data) {
        this.pending.selectGateway = true;
        try {
          const res = await this.instanceNodeOperate(data);
          if (res.result) {
            this.$bkMessage({
              message: i18n.t('跳过成功'),
              theme: 'success',
            });
            setTimeout(() => {
              this.setTaskStatusTimer();
            }, 1000);
          }
        } catch (e) {
          console.log(e);
        } finally {
          this.pending.selectGateway = false;
        }
      },
      async nodeResume(id, subflowInfo) {
        if (this.pending.parseNodeResume) {
          return;
        }
        this.pending.parseNodeResume = true;
        try {
          const data = {
            instance_id: subflowInfo?.taskId || this.instanceId,
            node_id: id,
            operation: 'callback',
            data: { data: {} },
          };
          const res = await this.instanceNodeOperate(data);
          if (res.result) {
            this.$bkMessage({
              message: i18n.t('继续成功'),
              theme: 'success',
            });
            // this.nodeInfoType = '';
            if (subflowInfo?.taskId) {
              this.updateExecuteInfo();
            } else {
              this.nodeInfoType = '';
              this.isNodeInfoPanelShow = false;
            }
            setTimeout(() => {
              this.setTaskStatusTimer();
            }, 1000);
          }
        } catch (e) {
          console.log(e);
        } finally {
          this.pending.parseNodeResume = false;
        }
      },
      setTaskStatusTimer(time = 2000) {
        this.cancelTaskStatusTimer();
        this.timer = setTimeout(() => {
          this.loadTaskStatus();
        }, time);
        this.canvasMode === 'stage' && this.$refs.processCanvas.setRefreshTaskStageCanvasData();
      },
      cancelTaskStatusTimer() {
        if (this.timer) {
          clearTimeout(this.timer);
          this.timer = null;
        }
      },
      async updateTaskStatus(id) {
        this.taskId = id;
        this.setCanvasData();
        await this.loadTaskStatus();
      },
      // 更新节点状态
      updateNodeInfo() {
        const nodes = this.instanceStatus.children;

        nodes && Object.keys(nodes).forEach((id) => {
          let code; let skippable; let retryable; let errorIgnorable; let autoRetry;
          const currentNode = nodes[id];
          const nodeActivities = this.pipelineData.activities[id];

          if (nodeActivities) {
            code = nodeActivities.component ? nodeActivities.component.code : '';
            skippable = nodeActivities.isSkipped || nodeActivities.skippable;
            retryable = nodeActivities.can_retry || nodeActivities.retryable;
            errorIgnorable = nodeActivities.error_ignorable;
            autoRetry = nodeActivities.auto_retry;
          }
          const data = {
            code,
            skippable,
            retryable,
            loop: currentNode.loop,
            status: currentNode.state,
            skip: currentNode.skip,
            retry: currentNode.retry,
            error_ignored: currentNode.error_ignored,
            error_ignorable: errorIgnorable,
            auto_retry: autoRetry,
            ready: false,
            task_state: this.state, // 任务状态
          };

          this.setTaskNodeStatus(id, data);
        });
      },
      setTaskNodeStatus(id, data) {
        this.$refs.processCanvas && this.$refs.processCanvas.onUpdateNodeInfo(id, data);
      },

      /**
       * 设置节点详细配置
       * @param {string} id - 当前节点ID
       * @param {boolean} rootNode - 是否根节点
       * @param {object} subflowNode - 当前节点信息
       * @param {string} nodeType - 当前节点类型
       * @param {object} conditionData - 当前节点条件数据
       */
      async setNodeDetailConfig(id, rootNode, subflowNode, nodeType, conditionData) {
        let code; let version; let componentData;

        const allActivities = Object.assign({}, this.pipelineData.activities, this.subActivities);
        const node = allActivities[id];
        // 从pipelineData中获取当前节点信息
        // 如果是ServiceActivity类型节点，提取组件数据和代码
        if (node) {
          componentData = node.type === 'ServiceActivity' ? node.component.data : {};
          if (node.type === 'subprocess') {
            code = 'SubProcess';
          } else {
            code = node.type === 'ServiceActivity' ? node.component.code : '';
          }
          if (node?.component?.code === 'subprocess_plugin') {
            version = node.component.data.subprocess.value.version || 'legacy';
          } else {
            version = (node.type === 'ServiceActivity' ? node.component.version : node.version) || 'legacy';
          }
        }
        const isNodeInSubflow = subflowNode?.parent?.component?.code === 'subprocess_plugin' || (subflowNode?.parent && !!subflowNode?.taskId);

        let instanceIdValue;
        const targetTaskId = subflowNode?.taskId;
        if (isNodeInSubflow) {
          instanceIdValue = targetTaskId; // taskInfo.value ||
        } else {
          instanceIdValue = subflowNode?.parent ? targetTaskId : this.instanceId;
        }
        // isNodeInSubflow ? (taskInfo.value || targetTaskId) : (subflowNode.parent ? targetTaskId  : this.instanceId)

        // 设置节点详细配置对象
        this.nodeDetailConfig = {
          component_code: code,       // 组件代码
          version,
          node_id: id,
          instance_id: instanceIdValue || this.instanceId, // 实例ID
          root_node: rootNode,        // 是否根节点
          subprocess_stack: [], // JSON.stringify(subprocessStack)
          componentData,
          subflowNodeParent: isNodeInSubflow ? subflowNode.parent : undefined, // 如果父节点为子流程才需要添加
          isNodeInSubflow,
          state: subflowNode ? subflowNode.state : undefined,
          isFirstSubUnexecuted: subflowNode ? subflowNode.isFirstSubUnexecuted : false,
        };
        if (nodeType) {
          this.nodeDetailConfig.nodeType = nodeType;
        }
        if (conditionData) {
          this.nodeDetailConfig.conditionData = conditionData;
          if (conditionData.taskId) {
            this.nodeDetailConfig.isNodeInSubflow = true;
          }
        }
      },
      async onRetryClick(id, subflowInfo, isTopSubflow = false) {
        try {
          const h = this.$createElement;
          this.$bkInfo({
            subHeader: h('div', { class: 'custom-header' }, [
              h('div', {
                class: 'custom-header-title',
                directives: [{
                  name: 'bk-overflow-tips',
                }],
              }, [i18n.t('确定重试当前节点？')]),
              h('div', {
                class: 'custom-header-sub-title bk-dialog-header-inner',
                directives: [{
                  name: 'bk-overflow-tips',
                }],
              }, [i18n.t('重新节点将重新执行当前节点（使用最新的参数值）')]),
            ]),
            extCls: 'dialog-custom-header-title',
            maskClose: false,
            confirmLoading: true,
            confirmFn: async () => {
              const resp = await this.instanceNodeOperate({
                instance_id: subflowInfo?.taskId || this.instanceId,
                node_id: id,
                operation: 'retry',
                data: {},
              });
              if (resp.result) {
                this.$bkMessage({
                  message: i18n.t('重试成功'),
                  theme: 'success',
                });
                if (subflowInfo?.taskId || isTopSubflow) {
                  this.updateExecuteInfo();
                }
                // 重新轮询任务状态
                this.isFailedSubproceeNodeInfo = null;
                this.setTaskStatusTimer();
                this.updateNodeActived(id, false);
              }
            },
          });
          // const resp = await this.getInstanceRetryParams({ id: this.instanceId })
          // if (resp.data.enable) {
          //   this.openNodeInfoPanel('retryNode', i18n.t('重试'))
          //   this.setNodeDetailConfig(id)
          //   if (this.nodeDetailConfig.component_code) {
          //     await this.loadNodeInfo(id)
          //   }
          // } else {
          //   this.openNodeInfoPanel('modifyParams', i18n.t('重试'))
          //   this.retryNodeId = id
          // }
        } catch (error) {
          console.warn(error);
        }
      },
      async loadNodeInfo(id = this.retryNodeId) {
        try {
          const nodeInputs = {};
          const { componentData } = this.nodeDetailConfig;
          const nodeInfo = await this.getNodeActInfo(this.nodeDetailConfig);
          if (nodeInfo.result) {
            Object.keys(nodeInfo.data.inputs).forEach((key) => {
              if (this.nodeDetailConfig.component_code === 'subprocess_plugin') { // 新版子流程任务节点输入参数处理
                const value = nodeInfo.data.inputs[key];
                if (key === 'subprocess') {
                  const nodeConfig = this.pipelineData.activities[id];
                  const { subprocess } = nodeConfig.component.data;
                  nodeInfo.data.inputs[key] = subprocess.value;
                  Object.keys(value.constants).forEach((key) => {
                    const data = value.constants[key];
                    nodeInputs[key] = data.value;
                  });
                } else {
                  nodeInputs[key] = value;
                }
              } else if (componentData[key]) {
                const { hook, value } = componentData[key];
                if (hook) {
                  nodeInputs[key] = nodeInfo.data.inputs[key];
                } else {
                  nodeInputs[key] = value;
                }
              }
            });
            this.nodeInputs = nodeInputs;
          }
          this.nodeInfo = nodeInfo;
        } catch (e) {
          console.warn(e);
        }
      },
      async onRetryTask(renderData) {
        const { component_code: componentCode } = this.nodeDetailConfig;
        try {
          let res;
          if (componentCode) {
            res = await this.instanceRetry(renderData);
          } else {
            res = await this.subflowNodeRetry(renderData);
          }
          if (res.result) {
            this.$bkMessage({
              message: i18n.t('重试成功'),
              theme: 'success',
            });
            this.nodeInfo = {};
            this.nodeInputs = {};
            return true;
          }
        } catch (e) {
          console.warn(e);
        }
      },
      onSkipClick(id, subflowInfo, isTopSubflow) {
        this.$bkInfo({
          title: i18n.t('确定跳过当前节点?'),
          subTitle: i18n.t('跳过节点将忽略当前失败节点继续往后执行'),
          maskClose: false,
          confirmLoading: true,
          confirmFn: async () => {
            await this.nodeTaskSkip(id, subflowInfo, isTopSubflow);
          },
        });
      },
      async nodeTaskRetry() {
        try {
          this.pending.retry = true;
          this.setNodeDetailConfig(this.retryNodeId);
          await this.loadNodeInfo();

          const { instance_id, component_code: componentCode, node_id: nodeId } = this.nodeDetailConfig;
          const data = {
            instance_id,
            component_code: componentCode,
            node_id: nodeId,
          };
          if (componentCode) {
            if (componentCode === 'subprocess_plugin') {
              const { inputs } = this.nodeInfo.data;
              data.inputs = inputs;
              // eslint-disable-next-line
              data.inputs._escape_render_keys = ['subprocess']
            } else {
              const inputs = tools.deepClone(this.nodeInputs);
              // 当重试节点引用了变量时，对应的inputs值设置为变量
              const { constants } = this.pipelineData;
              Object.keys(constants).forEach((key) => {
                const values = constants[key];
                if (this.retryNodeId in values.source_info) {
                  values.source_info[this.retryNodeId].forEach((code) => {
                    if (code in inputs) {
                      inputs[code] = values.key;
                    }
                  });
                }
              });
              data.inputs = inputs;
            }
            data.node_id = nodeId;
          }
          await this.onRetryTask(data);
          this.isNodeInfoPanelShow = false;
          this.retryNodeId = undefined;
          // 重新轮询任务状态
          this.isFailedSubproceeNodeInfo = null;
          this.setTaskStatusTimer();
          this.updateNodeActived(this.nodeDetailConfig.id, false);
        } catch (error) {
          console.warn(error);
        } finally {
          this.pending.retry = false;
        }
      },
      onForceFailClick(id, subflowInfo) {
        this.$bkInfo({
          title: i18n.t('确定强制终止当前节点?'),
          subTitle: i18n.t('强制终止将强行修改节点状态为失败，但不会中断已经发送到其它系统的请求'),
          maskClose: false,
          confirmLoading: true,
          confirmFn: async () => {
            await this.nodeForceFail(id, subflowInfo);
          },
        });
      },
      onModifyTimeClick(id, subflowInfo) {
        this.subflowInfo = subflowInfo;
        this.openNodeInfoPanel('modifyTime', i18n.t('修改时间'));
        this.setNodeDetailConfig(id);
      },
      onGatewaySelectionClick(id) {
        const nodeGateway = this.pipelineData.gateways[id];
        const branches = [];
        Object.keys(nodeGateway.conditions).forEach((item) => {
          branches.push({
            id: item,
            node_id: id,
            name: nodeGateway.conditions[item].name || nodeGateway.conditions[item].evaluate,
            converge_gateway_id: nodeGateway.converge_gateway_id || undefined,
          });
        });
        if (nodeGateway.default_condition) {
          branches.unshift({
            id: nodeGateway.default_condition.flow_id,
            node_id: id,
            name: nodeGateway.default_condition.name,
            converge_gateway_id: nodeGateway.converge_gateway_id || undefined,
          });
        }
        this.isCondParallelGw = nodeGateway.type === 'ConditionalParallelGateway';
        this.gatewayBranches = branches;
        this.isGatewaySelectDialogShow = true;
      },
      onTaskNodeResumeClick(id, subflowInfo) {
        this.$bkInfo({
          title: i18n.t('确定继续往后执行?'),
          maskClose: false,
          confirmLoading: true,
          confirmFn: async () => {
            await this.nodeResume(id, subflowInfo);
          },
        });
      },
      onApprovalClick(id, subflowInfo) {
        this.subflowInfo = subflowInfo;
        this.approval.id = id;
        this.approval.dialogShow = true;
      },
      onApprovalConfirm() {
        if (this.approval.pending) {
          return;
        }

        this.$refs.approvalForm.validate().then(async () => {
          try {
            this.approval.pending = true;
            const { id, is_passed, message } = this.approval;
            const params = {
              is_passed,
              message,
              project_id: this.project_id,
              task_id: this.subflowInfo?.taskId || this.instanceId,
              node_id: id,
              space_id: this.spaceId,
            };
            if (!this.isTopTask) {
              let selectedFlowIds = '';
              this.selectedFlowPath.forEach((item) => {
                if (item.type !== 'root') {
                  selectedFlowIds = selectedFlowIds ? `${selectedFlowIds},${item.id}` : item.id;
                }
              });
              params.subprocess_id = selectedFlowIds;
            }
            const res = await this.itsmTransition(params);
            if (res.result) {
              if (this.subflowInfo?.taskId) {
                this.updateExecuteInfo();
              }
              setTimeout(() => {
                  this.setTaskStatusTimer();
                }, 1000);
            }
            this.approval.id = '';
            this.approval.is_passed = true;
            this.approval.message = '';
            this.approval.dialogShow = false;
          } catch (e) {
            console.error(e);
          } finally {
            this.approval.pending = false;
          }
        });
      },
      onApprovalCancel() {
        this.approval.id = '';
        this.approval.is_passed = true;
        this.approval.message = '';
        this.approval.dialogShow = false;
      },
      onSubprocessPauseResumeClick(id, value) {
        if (this.pending.subflowPause) return;
        value === 'pause' ? this.taskPause(true, id) : this.taskResume(true, id);
      },
      // 设置画布数据，更新页面
      setCanvasData() {
        this.$nextTick(() => {
          this.nodeSwitching = false;
          this.$nextTick(() => {
            this.markNodesPhase();
          });
        });
      },
      getOptBtnIsClickable(action) {
        switch (action) {
          case 'execute':
            return this.state === 'CREATED' && this.isTopTask;
          case 'pause':
            return this.state === 'RUNNING';
          case 'resume':
            return this.state === 'SUSPENDED';
          case 'revoke':
            return this.isTopTask && ['RUNNING', 'SUSPENDED', 'NODE_SUSPENDED', 'FAILED'].includes(this.state);
          default:
            break;
        }
      },
      getOrderedTree(data) {
        const startNode = tools.deepClone(data.start_event);
        const endNode = tools.deepClone(data.end_event);
        const fstLine = startNode.outgoing;
        const orderedData = [Object.assign({}, startNode, {
          title: this.$t('开始节点'),
          name: this.$t('开始节点'),
          expanded: false,
        })];
        const endEvent = Object.assign({}, endNode, {
          title: this.$t('结束节点'),
          name: this.$t('结束节点'),
          expanded: false,
        });
        this.retrieveLines(data, fstLine, orderedData);
        orderedData.push(endEvent);
        // 过滤root最上层汇聚网关
        return orderedData;
      },
      /**
       * 根据节点连线遍历任务节点，返回按广度优先排序的节点数据
       * @param {Object} data 画布数据
       * @param {Array} lineId 连线ID
       * @param {Array} ordered 排序后的节点数据
       * @param {Boolean} isLoop 条件网关节点是否有循环
       *
       */
      async retrieveLines(data, lineId, ordered, isLoop = false) {
        const { end_event, activities, gateways, flows } = data;
        const currentNode = flows[lineId].target;
        const endEvent = end_event.id === currentNode ? tools.deepClone(end_event) : undefined;
        const activity = tools.deepClone(activities[currentNode]);
        const gateway = tools.deepClone(gateways[currentNode]);
        const node = endEvent || activity || gateway;
        if (node && ordered.findIndex(item => item.id === node.id) === -1) {
          let outgoing;
          if (Array.isArray(node.outgoing)) {
            outgoing = node.outgoing;
          } else {
            outgoing = node.outgoing ? [node.outgoing] : [];
          }
          // 当前tree是否已存在
          const isAt = !this.nodeIds.includes(node.id);
          if (gateway) { // 网关节点
            const name = NODE_DICT[gateway.type.toLowerCase()];
            gateway.title = name;
            gateway.name = name;
            gateway.expanded = false;
            gateway.children = [];
            if (isAt && (gateway.conditions || gateway.default_condition)) {
              const loopList = []; // 需要打回的node的incoming
              outgoing.forEach((item) => {
                const curNode = activities[flows[item].target] || gateways[flows[item].target];
                if (curNode
                  && (ordered.find(ite => ite.id === curNode.id || this.nodeIds.find(ite => ite === curNode.id)))) {
                  loopList.push(...curNode.incoming);
                }
              });
              const conditions = Object.keys(gateway.conditions).map((item) => {
                // 给需要打回的条件添加节点id
                const callback = loopList.includes(item) ? activities[flows[item].target] : '';
                const { evaluate, tag } = gateway.conditions[item];
                const callbackData = {
                  id: callback.id,
                  name: gateway.conditions[item].name,
                  nodeId: gateway.id,
                  overlayId: `condition${item}`,
                  tag,
                  value: evaluate,
                };
                return {
                  id: `${gateway.conditions[item].name}-${item}`,
                  conditionsId: '',
                  callbackName: callback.name,
                  name: `${gateway.conditions[item].name}-${item}`,
                  title: gateway.conditions[item].name,
                  isGateway: true,
                  conditionType: 'condition', // 条件、条件并行网关
                  expanded: false,
                  outgoing: item,
                  children: [],
                  isLoop: loopList.includes(item),
                  callbackData,
                };
              });
              // 添加条件分支默认节点
              if (gateway.default_condition) {
                const defaultCondition = [
                  {
                    id: `${gateway.default_condition.name}-${gateway.default_condition.flow_id}`,
                    name: `${gateway.default_condition.name}-${gateway.default_condition.flow_id}`,
                    title: gateway.default_condition.name,
                    isGateway: true,
                    conditionType: 'default',
                    expanded: false,
                    outgoing: gateway.default_condition.flow_id,
                    children: [],
                  },
                ];
                conditions.unshift(...defaultCondition);
              }
              conditions.forEach((item) => {
                this.retrieveLines(data, item.outgoing, item.children, item.isLoop);
                if (item.children.length === 0) this.conditionOutgoing.push(item.outgoing);
                item.children.forEach((i) => {
                  if (!this.nodeIds.includes(i.id)) {
                    this.nodeIds.push(i.id);
                  }
                });
              });
              gateway.children.push(...conditions);
              ordered.push(gateway);
              outgoing.forEach((line) => {
                this.retrieveLines(data, line, ordered);
              });
            } else if (isAt && gateway.type === 'ParallelGateway') {
              // 添加并行默认条件
              const defaultCondition = gateway.outgoing.map((item, index) => ({
                name: this.$t('并行') + (index + 1),
                title: this.$t('并行'),
                isGateway: true,
                expanded: false,
                conditionType: 'parallel',
                outgoing: item,
                children: [],
              }));
              gateway.children.push(...defaultCondition);
              defaultCondition.forEach((item) => {
                this.retrieveLines(data, item.outgoing, item.children);
                item.children.forEach((i) => {
                  if (!this.nodeIds.includes(i.id)) {
                    this.nodeIds.push(i.id);
                  }
                });
              });
              ordered.push(gateway);
              outgoing.forEach((line) => {
                this.retrieveLines(data, line, ordered);
              });
            }
            if (gateway.type === 'ConvergeGateway') {
              // 判断ordered中 汇聚网关的incoming是否存在
              const list = [];
              const converList = Object.assign({}, activities, gateways);
              this.nodeIds.forEach((item) => {
                if (converList[item]) {
                  list.push(converList[item]);
                }
              });
              const outgoingList = [];
              list.forEach((item) => {
                if (Array.isArray(item.outgoing)) {
                  item.outgoing.forEach((ite) => {
                    outgoingList.push(ite);
                  });
                } else {
                  outgoingList.push(item.outgoing);
                }
              });

              if (gateway.incoming.every(item => outgoingList.concat(this.conditionOutgoing).includes(item))) {
                // 汇聚网关push在最近的条件网关下
                const prev = ordered[ordered.findLastIndex(order => order.type !== 'ServiceActivity' || order.type !== 'ConvergeGateway')];
                // 独立子流程的children为 subChildren
                if (prev
                  && prev.children
                  && !prev.children.find(item => item.id === gateway.id)
                  && !this.converNodeList.includes(gateway.id)) {
                  this.converNodeList.push(gateway.id);
                  gateway.gatewayType = 'converge';
                  prev.children.push(gateway);
                }
                if (!this.nodeIds.includes(gateway.id)) {
                  this.nodeIds.push(gateway.id);
                }
                outgoing.forEach((line) => {
                  this.retrieveLines(data, line, ordered);
                });
              }
            }
          } else if (activity) { // 任务节点
            if (isLoop) return;
            if (isAt) {
              if (activity.type === 'SubProcess' || activity.component.code === 'subprocess_plugin') {
                // 只递归第一层 子流程的子流程不递归
                // const  recursionDepth = 0;
                if (activity.pipeline) {
                  activity.children = this.getOrderedTree(activity.pipeline);
                } else {
                  if (activity.component?.data && activity.component.data?.subprocess && activity.component.data?.subprocess?.value?.pipeline) {
                    activity.children = this.getOrderedTree(activity.component.data.subprocess.value.pipeline);
                  }
                }
              }
              activity.title = activity.name;
              activity.expanded = !(activity.type === 'SubProcess' || activity.component.code === 'subprocess_plugin');
              // activity.type === 'SubProcess' || activity.component.code === 'subprocess_plugin';
              ordered.push(activity);
            }
            outgoing.forEach((line) => {
              this.retrieveLines(data, line, ordered);
            });
          }
        }
      },
      updateNodeActived(id, isActived) {
        this.$refs.processCanvas.onUpdateNodeInfo(id, { isActived });
      },
      // 查看参数、修改参数 （侧滑面板 标题 点击遮罩关闭）
      onTaskParamsClick(type, name) {
        if (type === 'viewNodeDetails') {
          const { start_event, flows, location } = this.pipelineData;
          const nodeId = flows[start_event.outgoing].target;
          const locInfo = location.find(item => item.id === nodeId);
          const type = locInfo.type === 'subflow' ? 'subflowDetail' : locInfo.type;
          this.onNodeClick(nodeId, type);
          return;
        }
        if (type === 'templateData') {
          const pipelineData = tools.deepClone(this.pipelineData);
          for (const i in pipelineData.activities) {
            if ('pipeline' in pipelineData.activities[i]) {
               delete pipelineData.activities[i].pipeline;
            }
          }
          this.templateData = JSON.stringify(pipelineData, null, 4);
        }
        this.openNodeInfoPanel(type, name);
      },
      // 打开节点参数信息面板
      openNodeInfoPanel(type, name, isCondition = false) {
        this.sideSliderTitle = name;
        this.isNodeInfoPanelShow = true;
        this.nodeInfoType = type;
        this.isCondition = isCondition;
      },
      // 注入全局变量
      onInjectGlobalVariable() {
        this.isInjectVarDialogShow = true;
      },

      onToggleNodeInfoPanel() {
        this.isNodeInfoPanelShow = false;
        this.nodeInfoType = '';
        this.updateNodeActived(this.nodeDetailConfig.node_id, false);
      },
      onOperationClick(action) {
        if (this.pending.task || !this.getOptBtnIsClickable(action)) {
          return;
        }

        if (!this.hasOperatePerm) {
          return;
        }

        if (action === 'revoke') {
          this.$bkInfo({
            title: i18n.t('确定终止当前任务?'),
            subTitle: i18n.t('终止任务将停止执行任务，但执行中节点将运行完成'),
            maskClose: false,
            confirmLoading: true,
            confirmFn: async () => {
              await this.taskRevoke();
            },
          });
          return;
        }
        this.pending.task = true;
        this.activeOperation = action;
        const actionType = `task${action.charAt(0).toUpperCase()}${action.slice(1)}`;
        this[actionType]();
      },
      // type表示第一个节点的类型
      onNodeClick(id, type, conditionData) {
        this.defaultActiveId = id;
        this.setNodeDetailConfig(id, null, null, type, conditionData);
        // 如果存在node_id 当前可能是点击网关条件 node_id此时指向网关节点
        if (this.nodeDetailConfig.node_id) {
          this.updateNodeActived(this.nodeDetailConfig.node_id, false);
        }
        this.updateNodeActived(id, true);
        // 如果为子流程节点则需要重置pipelineData的constants
        this.nodePipelineData = { ...this.pipelineData };
        this.openNodeInfoPanel('executeInfo', i18n.t('节点详情'));
        // }
      },
      // 外层画布点击网关条件
      onOpenConditionEdit(data) {
        if (data) {
          this.onNodeClick(data.nodeId, undefined, data);
          // 生成网关添加id 条件name + 分支条件outgoning
          // 条件1-l290bdc11dad31349270ecae3d37eb85
          this.defaultActiveId = `${data.name}-${data.id}`;
        }
      },
      // nodeTree或者子流程画布点击网关条件
      onOpenConditionInfo(data) {
        if (data) {
          this.onNodeClick(data.nodeId, undefined, data);
          // 生成网关添加id 条件name + 分支条件outgoning
          this.defaultActiveId = `${data.name}-${data.outgoing}`;
          // this.isCondition = true;
          // this.conditionData = { ...data };
        }
        // this.isCondition = isCondition;
      },
      // 获取节点执行记录
      async onNodeExecRecord(nodeId) {
        try {
          this.isExecRecordOpen = true;
          const { template_node_id: tempNodeId } = this.pipelineData.activities[nodeId];
          if (tempNodeId) {
            const resp = await this.getNodeExecutionRecord({ tempNodeId, taskId: this.instanceId });
            const { execution_time: executionTime = [], total = 0 } = resp.data;
            this.nodeExecRecordInfo = {};
            const execTime = executionTime.map(item => this.formatDuring(item.elapsed_time));
            const execNodeConfig = this.instanceStatus.children[nodeId];
            let curTime = this.formatDuring(execNodeConfig.elapsed_time);
            let count = total;
            // 如果节点执行完成，任务未之前完成，需要把当前执行的时间插入到执行历史里面，count + 1
            if (execNodeConfig.state === 'FINISHED') {
              if (this.state !== 'FINISHED') {
                execTime.unshift(curTime);
                count += 1;
              }
              curTime = '';
            }
            this.nodeExecRecordInfo = {
              nodeId,
              curTime,
              execTime,
              state: execNodeConfig.state,
              count,
            };
          } else {
            this.$refs.processCanvas.closeNodeExecRecord();
          }
        } catch (error) {
          console.warn(error);
        }
      },
      formatDuring(time) {
        if (!time && time !== 0) return '--';
        if (time === 0) {
          return `${i18n.tc('小于')} ${i18n.tc('秒', 1)}`;
        }
        const days = Number(time / (60 * 60 * 24));
        const hours = Number((time % (60 * 60 * 24)) / (60 * 60));
        const minutes = Number((time % (60 * 60)) / (60));
        const seconds = (time % (60)).toFixed(0);
        let str = '';
        if (days) {
          str = `${i18n.tc('天', days, { n: days > 99 ? '99+' : days })} `;
        }
        if (hours) {
          str = `${str + hours} ${i18n.t('时')} `;
        }
        if (minutes) {
          str = `${str + minutes} ${i18n.t('分')} `;
        }
        if (seconds) {
          str = `${str + seconds} ${i18n.tc('秒', 0)}`;
        }
        return str;
      },
      onCloseNodeExecRecord() {
        this.isExecRecordOpen = false;
        this.nodeExecRecordInfo = {};
      },
      async onClickTreeNode(selectNodeId, nodeType, node) {
          const nodePath = [{
            id: this.instanceId,
            name: this.instanceName,
            nodeId: this.completePipelineData.id,
          }];

          if (this.nodeDetailConfig.node_id) {
            this.updateNodeActived(this.nodeDetailConfig.node_id, false);
          }
          this.selectedFlowPath = nodePath;
          // 如果为子流程的节点 添加子流程信息
          if (node?.conditionType === 'condition') {
            this.setNodeDetailConfig(selectNodeId, false, node, undefined, node.callbackData);
          } else {
            this.setNodeDetailConfig(selectNodeId, false, node, this.translateNodeType[node.type]);
          }
          // 当前节点激活id
          this.defaultActiveId = selectNodeId;
          // 节点树切换时，如果为子流程节点则需要重置pipelineData的constants
          // this.pipelineData 外部任务的流程树
          this.nodePipelineData = { ...this.pipelineData };
          this.updateNodeActived(selectNodeId, true);
      },
      async onRetrySuccess(data) {
        try {
          this.pending.retry = true;
          await this.onRetryTask(data);
          this.isNodeInfoPanelShow = false;
          this.isFailedSubproceeNodeInfo = null;
          this.setTaskStatusTimer();
          this.updateNodeActived(this.nodeDetailConfig.id, false);
        } catch (error) {
          console.warn(error);
        } finally {
          this.pending.retry = false;
        }
      },
      onRetryCancel(id) {
        this.isNodeInfoPanelShow = false;
        this.retryNodeId = undefined;
        this.updateNodeActived(id, false);
      },
      onModifyTimeSuccess(id) {
        this.isNodeInfoPanelShow = false;
        this.setTaskStatusTimer();
        this.updateNodeActived(id, false);
      },
      onModifyTimeCancel(id) {
        this.isNodeInfoPanelShow = false;
        this.updateNodeActived(id, false);
      },
      onConfirmGatewaySelect(selected) {
        const params = {
          node_id: selected[0].node_id,
          instance_id: this.instanceId,
          operation: this.isCondParallelGw ? 'skip_cpg' : 'skip_exg',
          data: {
            converge_gateway_id: this.isCondParallelGw ? selected[0].converge_gateway_id : undefined,
          },
        };
        if (this.isCondParallelGw) {
          params.data.flow_ids = selected.reduce((arr, cur) => {
            arr.push(cur.id);
            return arr;
          }, []);
        } else {
          params.data.flow_id = selected[0].id;
        }
        this.isGatewaySelectDialogShow = false;
        this.selectGatewayBranch(params);
      },
      onCancelGatewaySelect() {
        this.isGatewaySelectDialogShow = false;
      },
      async onConfirmInjectVar(context) {
        try {
          const params = {
            task_id: this.taskId,
            context,
          };
          const resp = await this.taskFlowUpdateContext(params);
          if (resp.result) {
            this.isInjectVarDialogShow = false;
            this.$bkMessage({
              message: i18n.t('注入全局变量成功'),
              theme: 'success',
            });
          }
        } catch (error) {
          console.warn(error);
        }
      },
      onCancelInjectVar() {
        this.isInjectVarDialogShow = false;
      },
      unclickableOperation(type) {
        // 失败时不允许点击暂停按钮，创建是不允许点击终止按钮，操作执行过程不允许点击
        return (this.state === 'FAILED' && type !== 'revoke') || (this.state === 'CREATED' && type === 'revoke') || this.operateLoading || !this.isTopTask;
      },
      packUp() {
        this.isNodeInfoPanelShow = false;
        this.retryNodeId = undefined;
      },
      onshutDown() {
        this.isNodeInfoPanelShow = false;
        this.templateData = '';
      },
      onBeforeClose() {
        // 除修改参数/修改时间/重试外  其余侧滑没有操作修改功能，支持自动关闭
        if (!['modifyParams', 'modifyTime', 'retryNode'].includes(this.nodeInfoType)) {
          this.isNodeInfoPanelShow = false;
        } else {
          const isEqual = this.$refs[this.nodeInfoType].judgeDataEqual();
          if (isEqual === true) {
            this.isNodeInfoPanelShow = false;
            this.retryNodeId = undefined;
          } else if (isEqual === false) {
            this.$bkInfo({
              ...this.infoBasicConfig,
              confirmFn: () => {
                this.isNodeInfoPanelShow = false;
                this.retryNodeId = undefined;
              },
            });
          }
        }
      },
      onHiddenSideslider() {
        this.nodeInfoType = '';
        const { node_id: nodeId } = this.nodeDetailConfig;
        if (!nodeId) return;
        this.updateNodeActived(nodeId, false);
      },
      // 判断RUNNING的节点是否有暂停节点，若有，则将当前任务状态标记为暂停状态
      setRunningNode(node = {}) {
        this.tabIconState          = Object.keys(node).some(key => (node[key].state === 'RUNNING'
            && this.pipelineData.activities[key]
            && this.pipelineData.activities[key].type === 'ServiceActivity'
            && this.pipelineData.activities[key].component.code === 'pause_node'))
            ? 'SUSPENDED'
            : '';
      },
      // 刷新任务状态
      handleRefreshTaskStatus() {
        const nodeId = this.isFailedSubproceeNodeInfo.id;
        this.isFailedSubproceeNodeInfo = null;
        this.setTaskStatusTimer();
        this.updateNodeActived(nodeId, false);
      },
    },
  };
</script>
<style lang="scss" scoped>
@import '../../../scss/config.scss';
@import '../../../scss/animation/operate.scss';
.task-operation {
    position: relative;
    height: 100%;
    min-height: 500px;
    overflow: hidden;
    background: #f4f7fa;
}

::v-deep .atom-failed {
    font-size: 12px;
}

.subprocess-failed-tips {
    margin-top: -1px;
    color: #63656e;
    ::v-deep .bk-alert-title {
        display: flex;
    }
    ::v-deep .bk-link {
        vertical-align: initial;
        line-height: 16px;
        .bk-link-text {
            font-size: 12px;
        }
    }
}
.task-container {
    position: relative;
    width: 100%;
    height: calc(100vh - 48px);
    background: $whiteDefault;
    overflow: hidden;
    .pipeline-nodes {
        width: 100%;
        height: 100%;
        transition: width 0.5s ease-in-out;
        ::v-deep .pipeline-canvas{
            width: 100%;
            .node-canvas {
                width: 100%;
                height: 100%;
                background: #e1e4e8;
            }
            .tool-wrapper {
                top: 19px;
                left: 40px;
            }
        }
        .task-management-page {
            ::v-deep .canvas-wrapper.jsflow {
                background: #f5f7fa;
                .jtk-endpoint {
                    z-index: 2 !important;
                }
            }
        }
    }
}
::v-deep .bk-sideslider-content {
    height: calc(100% - 60px);
}
.header {
    display: flex;
    .bread-crumbs-wrapper {
        margin-left: 10px;
        font-size: 0;
        .path-item {
            display: inline-block;
            font-size: 14px;
            overflow: hidden;
            &.name-ellipsis {
                max-width: 190px;
                overflow: hidden;
                white-space: nowrap;
                text-overflow: ellipsis;
            }
            .node-name {
                margin: 0 4px;
                font-size: 14px;
                color: #3a84ff;
                cursor: pointer;
            }
            .node-ellipsis {
                margin-right: 4px;
            }
            &:first-child {
                .node-name {
                    margin-left: 0px;
                }
            }
            &:last-child {
                .node-name {
                    &:last-child {
                        color: #313238;
                        cursor: text;
                    }
                }
            }
        }
    }
}
.node-info-panel {
    height: 100%;
    .operation-flow {
        padding: 20px 30px;
    }
}
.approval-dialog-content {
    ::v-deep .bk-form-radio {
        margin-right: 10px;
    }
}
</style>
<style lang="scss">
@import '../../../scss/config.scss';
.task-operation {
    .operation-table {
        width: 100%;
        font-size: 12px;
        border: 1px solid #ebebeb;
        border-collapse: collapse;
        th {
            background: $whiteNodeBg
        }
        th,td {
            padding: 10px;
            color: $greyDefault;
            text-align: left;
            border: 1px solid #ebeef5;
        }
    }
    .bk-flow-canvas .tooltip .tooltip-inner {
        line-height: 1;
        box-sizing: content-box;
    }
}
</style>
