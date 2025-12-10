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
  <div class="parameter-details">
    <div class="details-wrapper">
      <NodeTree
        class="nodeTree"
        :data="curNodeData"
        :node-nav="nodeNav"
        :node-display-status="processNodeDisplayStatus"
        :selected-flow-path="selectedFlowPath"
        :default-active-id="currentDefaultActiveId"
        :is-condition="isCondition"
        :sub-canvas-active-id="subCanvasActiveId"
        :execute-info="executeInfo"
        @onOpenGatewayInfo="onNodeTreeConditionClick"
        @dynamicLoad="handleDynamicLoad"
        @onSelectNode="onSelectNode" />
      <div
        v-if="location"
        v-bkloading="{ isLoading: loading, opacity: 1, zIndex: 100 }"
        :class="['execute-info', { 'loading': loading }]">
        <div class="execute-head">
          <bk-breadcrumb
            v-if="isShowSubflowExceutedCount"
            v-bkloading="{ isLoading: isBreadCurmbLoading, opacity: 1, zIndex: 100 }"
            class="node-name">
            <bk-breadcrumb-item
              v-for="(item,index) in breadcrumbData"
              :key="index">
              <span>{{ item.name }}</span>
              <bk-popover :content="$t('当前执行次数')">
                <bk-select
                  v-if=" nodeDetailActivityPanel === 'record' && item.totalCount > 1"
                  :clearable="false"
                  :value="item.curSelectCount"
                  @selected="selectBreadcrumExecuteCount($event, item)">
                  <bk-option
                    v-for="count in item.totalCount"
                    :id="count"
                    :key="count"
                    :name="count" />
                </bk-select>
              </bk-popover>
              <span
                v-if="breadcrumbData.length > 1 && index !== breadcrumbData.length - 1"
                class="separator">/</span>
            </bk-breadcrumb-item>
          </bk-breadcrumb>
          <span
            v-else
            class="node-name">
            {{ nodeDetailConfig?.conditionData ? nodeDetailConfig.conditionData.name : executeInfo.name || location.name }}
          </span>
          <div class="node-state">
            <span :class="displayStatus" />
            <span class="status-text-messages">{{ nodeState }}</span>

            <JumpLinkBKFlowOrExternal
              v-if="isSubflowExecuted"
              :query="{ id: currentSubflowTaskId, type:'task' }"
              :get-target-url="onViewSubProcessExecute">
              <div
                class="view-subflow">
                <span class="dividing-line" />
                <i class="common-icon-box-top-right-corner icon-link-to-sub" />
                <p class="text-link-to-sub">
                  {{ $t('查看子流程') }}
                </p>
              </div>
            </JumpLinkBKFlowOrExternal>
          </div>
        </div>
        <div class="execute-body">
          <!-- 子流程画布 -->
          <div
            v-if="isShowSubflowCanvas"
            v-bkloading="{ isLoading: isSubprocessLoading, opacity: 1, zIndex: 100 }"
            class="sub-process"
            :style="{ height: `${subProcessHeight}px` }">
            <component
              :is="templateComponentName"
              :key="templateComponentName==='SubStageCanvas'? 'SubStageCanvas' : canvasDataChangeKey"
              ref="subProcessCanvas"
              :is-subflow-graph="true"
              class="sub-flow"
              :editable="false"
              :show-palette="false"
              :is-execute="true"
              :is-stage-canvas-task-execute="!!currentSubflowTaskId"
              :space-id="spaceId"
              :gateways="processGateway"
              :instance-id="currentSubflowTaskId"
              :pipeline-tree="subCanvasData"
              :template-id="subTemplateId"
              :canvas-data="canvasData"
              @onSubflowNodeClick="onSubflowNodeClick"
              @onConditionClick="onSubConditionClick" />
            <div
              v-if="templateComponentName!=='SubStageCanvas'"
              class="flow-option">
              <i
                v-bk-tooltips.top="$t('缩小')"
                class="bk-icon icon-narrow-line"
                :class="{ 'disabled': zoom < 0.25 }"
                @click="onZoomOut" />
              <i
                v-bk-tooltips.top="$t('放大')"
                class="bk-icon icon-enlarge-line"
                :class="{ 'disabled': zoom > 1.5 }"
                @click="onZoomIn" />
            </div>
          </div>
          <!-- 选项面板 -->
          <OptionsPanel
            :node-detail-config="nodeDetailConfig"
            :node-activity="nodeActivity"
            :location="location"
            :space-id="spaceId"
            :template-id="templateId"
            :pipeline-data="pipelineData"
            :admin-view="adminView"
            :history-info="historyInfo"
            :execute-record="executeRecord"
            :is-ready-status="isReadyStatus"
            :the-execute-time="theExecuteTime"
            :loop="loop"
            :execute-info="executeInfo"
            :task-id="taskId"
            :scope-info="scopeInfo"
            :gateways="processGateway"
            :condition-data="nodeDetailConfig.conditionData || {}"
            :third-party-node-code="thirdPartyNodeCode"
            :is-show-subflow-exceuted-count="isShowSubflowExceutedCount"
            @selectExecuteRecord="onSelectExecuteRecord"
            @selectExecuteLoop="onSelectExecuteLoop" />
        </div>
        <!-- 底部操作按钮 -->
        <div
          v-if="isShowActionWrap && isInLatestExecuteNum"
          class="action-wrapper">
          <template v-if="realTimeState.state === 'RUNNING' && !isSubProcessNode">
            <bk-button
              v-if="nodeDetailConfig.component_code === 'pause_node'"
              theme="primary"
              data-test-id="taskExcute_form_resumeBtn"
              @click="onResumeClick">
              {{ $t('继续执行') }}
            </bk-button>
            <bk-button
              v-else-if="nodeDetailConfig.component_code === 'bk_approve'"
              theme="primary"
              data-test-id="taskExcute_form_approvalBtn"
              @click="onApprovalClick">
              {{ $t('审批') }}
            </bk-button>
            <bk-button
              v-else
              data-test-id="taskExcute_form_mandatoryFailBtn"
              @click="mandatoryFailure">
              {{ $t('强制终止') }}
            </bk-button>
          </template>
          <template v-if="isShowRetryBtn || isShowSkipBtn">
            <bk-button
              v-if="isShowRetryBtn"
              theme="primary"
              data-test-id="taskExcute_form_retryBtn"
              @click="onRetryClick">
              {{ $t('重试') }}
            </bk-button>
            <bk-button
              v-if="isShowSkipBtn"
              theme="default"
              data-test-id="taskExcute_form_skipBtn"
              @click="onSkipClick">
              {{ $t('跳过') }}
            </bk-button>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>
<script>
  import i18n from '@/config/i18n/index.js';
  import { mapState, mapActions, mapMutations } from 'vuex';
  import tools from '@/utils/tools.js';
  import atomFilter from '@/utils/atomFilter.js';
  import { TASK_STATE_DICT, NODE_DICT } from '@/constants/index.js';
  import NodeTree from './NodeTree';
  import jsonFormSchema from '@/utils/jsonFormSchema.js';
  import { checkDataType, getDefaultValueFormat } from '@/utils/checkDataType.js';
  import { graphToJson } from '@/utils/graphJson.js';
  import axios from 'axios';
  import SubflowCanvas from '@/components/canvas/ProcessCanvas/SubflowCanvas.vue';
  import OptionsPanel from './ExecuteInfoCompoment/OptionsPanel.vue';
  import getOrderNodeToNodeTree from '@/utils/orderCanvasNodeToNodeTree.js';
  import JumpLinkBKFlowOrExternal from '@/components/common/JumpLinkBKFlowOrExternal.vue';
  import SubStageCanvas from '../../../components/canvas/StageCanvas/SubStageCanvas.vue';
  const { CancelToken } = axios;
  let source = CancelToken.source();

  export default {
    name: 'ExecuteInfo',
    components: {
      NodeTree,
      SubflowCanvas,
      OptionsPanel,
      JumpLinkBKFlowOrExternal,
      SubStageCanvas,
    },
    props: {
      adminView: {
        type: Boolean,
        default: false,
      },
      nodeDetailConfig: {
        type: Object,
        required: true,
      },
      nodeData: {
        type: Array,
        default() {
          return [];
        },
      },
      selectedFlowPath: {
        type: Array,
        default() {
          return [];
        },
      },
      nodeNav: {
        type: Array,
        default() {
          return [];
        },
      },
      defaultActiveId: {
        type: String,
        default: '',
      },
      isCondition: {
        type: Boolean,
        default: false,
      },
      pipelineData: { // 外层任务实例树
        type: Object,
        default() {
          return {};
        },
      },
      state: { // 总任务状态
        type: String,
        default: '',
      },
      nodeDisplayStatus: {
        type: Object,
        required: true,
      },
      isShow: Boolean,
      constants: {
        type: Object,
        default() {
          return {};
        },
      },
      gateways: { // 外层画布的网关节点
        type: Object,
        default() {
          return {};
        },
      },
      backToVariablePanel: Boolean,
      isReadonly: {
        type: Boolean,
        default: false,
      },
      spaceId: {
        type: Number,
        default: 0,
      },
      scopeInfo: {
        type: Object,
        default() {
          return {};
        },
      },
      templateId: {
        type: [Number, String],
        default: '',
      },
      instanceId: {
        type: String,
        default: '',
      },
      taskId: {
        type: [String, Number],
        default: '',
      },
      instanceActions: {
        type: Array,
        default() {
          return [];
        },
      },
      canvasMode: {
        type: String,
        default: '',
      },
    },
    data() {
      return {
        loading: true,
        isRenderOutputForm: false,
        executeInfo: {},
        executeRecord: {},
        historyInfo: [],
        theExecuteTime: undefined, // 第几次循环
        pluginOutputs: [],
        renderConfig: [],
        outputRenderData: {},
        outputRenderConfig: [],
        outputRenderOption: {
          showGroup: false,
          showLabel: true,
          showHook: false,
          formEdit: true,
          formMode: true,
        },
        subprocessTasks: {},
        loop: 1, // 循环次数
        isReadyStatus: true,
        isShowSkipBtn: false,
        isShowRetryBtn: false,
        curActiveTab: 'record',
        zoom: 0.75, // 画布缩放
        subProcessHeight: 500,
        isSubprocessLoading: true,
        subCanvasData: {},
        subCanvsLocationCollection: [],
        subCanvsActivityCollection: [],
        canvasData: [],
        canvasDataChangeKey: '',
        currentDefaultActiveId: this.defaultActiveId,
        currentSubflowTaskId: '',
        subflowNodeStatus: {},
        subflowTaskId: '',
        subTemplateId: '',
        canvasRandomKey: '',
        subflowState: '',
        currentNodeDisplayStatus: tools.deepClone(this.nodeDisplayStatus),
        currentIndependentSubFlowId: '',
        curNodeData: tools.deepClone(this.nodeData),
        subCanvasActiveId: '',
        curNodeIds: [],
        conditionOutgoing: [],
        converNodeList: [],
        translateLocationName: {
          endpoint: i18n.t('结束节点'),
          startpoint: i18n.t('开始节点'),
          convergegateway: i18n.t('汇聚网关'),
          branchgateway: i18n.t('分支网关'),
          conditionalparallelgateway: i18n.t('条件并行网关'),
        },
        breadcrumbData: [],
        isBreadCurmbLoading: false,
        curSubExecutedTaskId: null, // 当前选择的子流程执行次数的taskId
        isInLatestExecuteNum: true,
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
      ...mapState('task', {
        nodeDetailActivityPanel: state => state.nodeDetailActivityPanel,
      }),
      // 节点实时状态
      realTimeState() {
        const nodeStateMap = this.processNodeDisplayStatus.children || {};
        return nodeStateMap[this.nodeDetailConfig.node_id] || { state: 'READY' };
      },
      displayStatus() {
        let state = '';
        if (this.realTimeState.state === 'RUNNING') {
          state = 'common-icon-dark-circle-ellipsis';
        } else if (this.realTimeState.state === 'SUSPENDED') {
          state = 'common-icon-dark-circle-pause';
        } else if (this.realTimeState.state === 'FINISHED') {
          const { skip, error_ignored: errorIgnored } = this.realTimeState;
          state = skip || errorIgnored ? 'common-icon-fail-skip' : 'bk-icon icon-check-circle-shape';
        } else if (this.realTimeState.state === 'FAILED') {
          state = 'common-icon-dark-circle-close';
        } else if (this.realTimeState.state === 'CREATED') {
          state = 'common-icon-waitting';
        } else if (this.realTimeState.state === 'READY') {
          state = 'common-icon-waitting';
        }
        return state;
      },
      nodeState() {
        // 如果整体任务未执行的话不展示描述
        if (this.state === 'CREATED') return i18n.t('未执行');
        // 如果整体任务执行完毕但有的节点没执行的话不展示描述
        if (['FAILED', 'FINISHED'].includes(this.state) && this.realTimeState.state === 'READY') return i18n.t('未执行');
        const { state, skip, error_ignored: errorIgnored } = this.realTimeState;
        return skip || errorIgnored ? i18n.t('失败后跳过') : state && TASK_STATE_DICT[state];
      },
      // 节点位置
      location() {
        const { node_id: nodeId } = this.nodeDetailConfig;
        // const currentPipelineData  = subflowNodeParent ? subflowNodeParent.children : this.pipelineData.location;
        const locationData = this.pipelineData?.location || [];
        const currentPipelineData = [...locationData, ...this.subCanvsLocationCollection];
        const curLocation = currentPipelineData.find((item) => {
          let result = false;
          if (item.id === nodeId) {
            result = true;
          }
          return result;
        });
        if (!curLocation?.name) {
          curLocation.name = this.translateLocationName[curLocation.type];
        }
        return curLocation;
      },
      pluginCode() {
        return this.nodeDetailConfig.component_code;
      },
      isThirdPartyNode() {
        return this.pluginCode === 'remote_plugin';
      },
      isSubProcessNode() {
        return this.pluginCode === 'subprocess_plugin';
      },
      thirdPartyNodeCode() {
        if (!this.isThirdPartyNode) return '';
        let codeInfo = {};
        if (this.nodeDetailConfig.subflowNodeParent) {
          codeInfo = this.nodeDetailConfig.componentData.plugin_code;
        } else {
          const nodeInfo = this.pipelineData.activities[this.nodeDetailConfig.node_id];
          if (!nodeInfo) return '';
          codeInfo = nodeInfo.component.data;
          codeInfo = codeInfo && codeInfo.plugin_code;
        }
        codeInfo = codeInfo.value;
        return codeInfo;
      },
      nodeActivity() {
        const activity = Object.assign({}, this.subCanvsActivityCollection, this.pipelineData.activities);
        return activity[this.nodeDetailConfig.node_id];
        // return this.pipelineData.activities[this.nodeDetailConfig.node_id];
      },
      componentValue() {
        return this.isSubProcessNode ? this.nodeActivity.component.data.subprocess.value : {};
      },
      isShowActionWrap() {
        // 任务终止时禁止节点操作
        if (this.state === 'REVOKED' || !this.instanceActions.includes('OPERATE')) {
          return false;
        }
        return (this.realTimeState.state === 'RUNNING' && !this.isSubProcessNode) || this.isShowRetryBtn || this.isShowSkipBtn;
      },
      isShowSubflowCanvas() {
        const subflowParent = this.nodeDetailConfig?.subflowNodeParent;
        const isSubChildren = subflowParent !== null && subflowParent?.component?.code === 'subprocess_plugin';
        const isSubprocessNode = this.nodeDetailConfig.component_code === 'subprocess_plugin';
        // const isUnExecutedNode = this.nodeDetailConfig.state && this.nodeDetailConfig.state !== 'gateway';
        return isSubprocessNode || isSubChildren || this.nodeDetailConfig.isNodeInSubflow || this.isExistInSubCanvas(this.nodeDetailConfig.node_id);
      },
      isShowSubflowExceutedCount() {
        const { node_id: nodeId, component_code: componentCode } = this.nodeDetailConfig;
        return this.isExistInSubCanvas(nodeId) || (this.isFirstSubFlow(nodeId) && componentCode === 'subprocess_plugin');
      },
      isShowUnexecutedSubflow() {
        return this.historyInfo.length < 1 && this.isExistInSubCanvas(this.nodeDetailConfig.node_id);
      },
      // 加入子流程节点后的nodeDisplayStatus
      processNodeDisplayStatus() {
        this.currentNodeDisplayStatus.children = Object.assign({}, this.currentNodeDisplayStatus.children, this.subflowNodeStatus);
        return this.currentNodeDisplayStatus;
      },
      processGateway() {
        return Object.assign({}, this.gateways, this.subCanvasData.gateways);
      },
      isSubflowExecuted() {
        // this.nodeDetailConfig.component_code === 'subprocess_plugin'
       return this.currentSubflowTaskId !== '' && this.isSubProcessNode;
      },
      subProcessTaskId() { // 独立子流程节点的任务id
        return this.nodeDetailConfig.instance_id;
      },
      getEmitParams() {
        if (this.isExistInSubCanvas(this.nodeDetailConfig.node_id)) {
          return {
            taskId: this.nodeDetailConfig.instance_id,
            subflowRootId: this.subCanvasData.id,
          };
        }
        return null;
      },
      templateComponentName() {
          const canvasModeToComponentMap = {
            horizontal: 'SubflowCanvas',
            vertical: 'SubflowCanvas',
            stage: 'SubStageCanvas',
          };
          return canvasModeToComponentMap[this.canvasMode] || canvasModeToComponentMap.horizontal;
      },
    },
    watch: {
      nodeDetailConfig: {
        async handler(val, oldVal) {
          if (val.node_id !== undefined && !tools.isDataEqual(val, oldVal)) {
            if (oldVal !== undefined && val.node_id !== oldVal.node_id) {
              this.setNodeDetailActivityPanel('record');
            }
            this.loadNodeInfo();
          }
        },
        deep: true,
        immediate: true,
      },
      defaultActiveId: {
        handler(val) {
          this.currentDefaultActiveId = val;
          this.subCanvasActiveId = '';
        },
        deep: true,
        immediate: true,
      },
      nodeData: {
        handler(val) {
          this.curNodeData = tools.deepClone(val);
        },
        deep: true,
      },
      nodeDisplayStatus: {
        handler(val) {
          this.currentNodeDisplayStatus = tools.deepClone(val);
        },
        immediate: true,
      },
    },
    beforeDestroy() {
      if (source) {
          source.cancel('cancelled');
      }
      this.cancelTaskStatusTimer();
    },
    methods: {
      ...mapActions('task/', [
        'getNodeActDetail',
        'loadSubflowConfig',
        'getInstanceStatus',
        'getTaskInstanceData',
      ]),
      ...mapMutations('task/', [
        'setSubActivities',
        'setNodeDetailActivityPanel',
      ]),
      ...mapActions('template/', [
        'loadUniformApiMeta',
      ]),
      ...mapActions('atomForm/', [
        'loadAtomConfig',
        'loadPluginServiceDetail',
        'loadPluginServiceAppDetail',
      ]),
      async selectBreadcrumExecuteCount(value, item) {
        this.isBreadCurmbLoading = true;
        let taskId = '';
        const { outputs } = item.allExecutedInfo[value - 1];
        if (outputs.task_id) {
          taskId = outputs.task_id;
        } else if (Array.isArray(outputs)) {
          const taskInfo = outputs.find(item => item.key === 'task_id') || {};
          if (taskInfo) {
            taskId = taskInfo.value;
          } else {
            const targetIndex = this.breadcrumbData.findIndex(bread => bread.id === this.nodeDetailConfig.node_id);
            let prevItem = null;
            if (targetIndex > 0) {
              prevItem = this.breadcrumbData[targetIndex - 1];
            }
            const curRootInfo = prevItem.allExecutedInfo[prevItem.curSelectCount - 1];
            if (curRootInfo.outputs.task_id) {
              taskId = curRootInfo.outputs.task_id;
            } else if (Array.isArray(outputs)) {
              taskId = curRootInfo.outputs.find(item => item.key === 'task_id').value || '';
            }
          }
        }
        this.curSubExecutedTaskId = taskId;
        if (item.id === this.nodeDetailConfig.node_id) {
          this.onSelectExecuteRecord(value, this.historyInfo);
          item.curSelectCount = value;
          item.taskId = taskId;
        } else {
          const targetIndex = this.breadcrumbData.findIndex(bread => bread.id === item.id);
          this.breadcrumbData[targetIndex].curSelectCount = value;
          if (!['task', 'subflow', 'ServiceActivity'].includes(this.nodeDetailConfig.nodeType)) {
            this.isBreadCurmbLoading = false;
            return;
          }
          // 获取当前节点的id
          const resp = await this.getTaskInstanceData(taskId);
          const { activities } = resp.pipeline_tree;
          const activitiesArray = Object.values(activities);
          const { template_node_id: templateNodeId } = this.subCanvsActivityCollection[this.nodeDetailConfig.node_id];
          const curNewNodeId = activitiesArray.find(item => item.template_node_id === templateNodeId).id;
          const query = {
            space_id: this.spaceId,
            instance_id: taskId,
            node_id: curNewNodeId,
            component_code: this.nodeDetailConfig.component_code,
          };
          const res = await this.getNodeActDetail(query);
           this.breadcrumbData.forEach(async (item) => {
            if (item.id === this.nodeDetailConfig.node_id) {
              item.allExecutedInfo = res.data.skip ? [] : [res.data];
              if (res.data.histories) {
                item.allExecutedInfo.unshift(...res.data.histories);
                item.curSelectCount = res.data.skip ? res.data.histories.length : res.data.histories.length + 1;
                item.totalCount = res.data.skip ? res.data.histories.length : res.data.histories.length + 1;
              } else {
                item.curSelectCount = item.allExecutedInfo.length;
                item.totalCount = item.allExecutedInfo.length;
              }
              this.historyInfo = item.allExecutedInfo;
              this.onSelectExecuteRecord(item.totalCount, item.allExecutedInfo);
            }
           });
        }
        this.isBreadCurmbLoading = false;
      },
      // 递归查找目标节点并收集路径
      findNodePath(nodes, targetId, currentPath = []) {
        for (const node of nodes) {
          const { instanceId } = this.$route.query;
          const tempPath = [...currentPath, {
            id: node.id,
            name: node.name,
            taskId: this.isFirstSubFlow(node.id) ? instanceId : node.taskId,
            component_code: node?.component?.code || '',
            type: node.type,
          }];
          // 找到目标节点，返回完整路径
          if (node.id === targetId) {
            return tempPath;
          }
          // 若当前节点有子节点，递归查找
          if (node.children && node.children.length > 0) {
            const result = this.findNodePath(node.children, targetId, tempPath);
            if (result) {
              return result;
            }
          }
        }
        return null;
      },
      async loadSubprocessStatus() {
        try {
            if (source) {
                source.cancel('cancelled'); // 取消定时器里已经执行的请求
                this.timer = null;
            }
            source = CancelToken.source();
            const data = {
              instance_id: this.subflowTaskId || '',
              project_id: this.project_id,
              cancelToken: source.token,
            };
            const resp = await this.getInstanceStatus(data);
            if (!resp.result) return;
            // 当前请求结果与节点状态不一致重新获取当前节点信息
            const targetNode =  resp.data.children[this.executeInfo.id];
            if (targetNode) {
              if (this.executeInfo.state === 'RUNNING' && targetNode.state !== this.executeInfo.state) {
                this.loadNodeInfo();
              }
            }
            this.subflowState = resp.data.state;
            this.subflowNodeStatus = resp.data.children || {};
            if (['FINISHED', 'REVOKED', 'FAILED'].includes(resp.data.state)) {
               this.cancelTaskStatusTimer();
            } else {
              this.setTaskStatusTimer();
            }
        } catch (error) {
            console.warn(error);
        } finally {
            source = null;
            this.isSubprocessLoading = false;
        }
      },
      setTaskStatusTimer(time = 3000) {
          this.cancelTaskStatusTimer();
          this.timer = setTimeout(() => {
            this.loadSubprocessStatus();
            this.updateSubflowCanvasNodeInfo();
            this.templateComponentName === 'SubStageCanvas' && this.$refs.subProcessCanvas.setRefreshTaskStageCanvasData();
          }, time);
      },
      cancelTaskStatusTimer() {
          if (this.timer) {
              clearTimeout(this.timer);
              this.timer = null;
          }
      },
      isExistInSubCanvas(id) {
        let isExist = false;
        if (this.subCanvasData.location) {
          this.subCanvasData.location.forEach((item) => {
            if (item.id === id) {
              isExist = true;
            }
          });
        }
        return isExist;
      },
      // 画布初始化时缩放比偏移
      // setCanvasZoomPosition() {
      //   // 计算子流程画布高度
      //   const dndComponent = this.$refs.subProcessCanvas.$el;
      //   const { top } = dndComponent.getBoundingClientRect();
      //   this.subProcessHeight = (window.innerHeight - top - 320) < 320 ? 320 : window.innerHeight - top - 320 ;
      //   const canvasInstance = this.$refs.subProcessCanvas.graph;
      //   canvasInstance?.zoom(this.zoom);
      // },
      // 获取外层画布节点配置
      getNodeDetailConfig(node, instanceId) {
          const { id, parent } = node;
          const { pipelineData } = this;
          let code; let version; let componentData;
          const nodeInfo = pipelineData.activities[id];
          if (nodeInfo) {
              componentData = nodeInfo.component.data;
              code = nodeInfo.component.code;
              version = nodeInfo.component.version || 'legacy';
          }
          return {
              component_code: code,
              version,
              node_id: id,
              instance_id: instanceId,
              root_node: parent?.id || '',
              subprocess_stack: [],
              componentData,
          };
      },
      addTaskId(node, taskId) {
        node.forEach((item) => {
            item.taskId = taskId;
            item.isFirstSubUnexecuted = false; // 顶层子流程是否未执行
            if (item.children) {
              this.addTaskId(item.children, taskId);
            }
          });
      },
      // 获取独立子流程节点详情
      async getSubprocessData(taskId, nodeInfo, isOnlyExpand = false) {
        try {
            const resp = await this.getTaskInstanceData(taskId);
            this.subTemplateId = resp.template_id;
            this.subCanvsLocationCollection = [...resp.pipeline_tree.location, ...this.subCanvsLocationCollection];
            this.subCanvsActivityCollection = Object.assign({}, resp.pipeline_tree.activities);
            this.setSubActivities(this.subCanvsActivityCollection);
            const pipelineTree = resp.pipeline_tree;
            if (!this.nodeDetailConfig.isNodeInSubflow && !isOnlyExpand) {
              this.updateCanvasData(resp.pipeline_tree);
            }
            const curNodeInfo = tools.deepClone(nodeInfo);
            curNodeInfo.children = getOrderNodeToNodeTree(pipelineTree);
            curNodeInfo.dynamicLoad = false;
            curNodeInfo.expanded = true;
            curNodeInfo.taskId = taskId;
            if (curNodeInfo.children.length > 0) {
              this.addTaskId(curNodeInfo.children, taskId);
            }
            this.updateTreeNode(this.curNodeData[0].children, curNodeInfo);
        } catch (error) {
            console.warn(error);
        }
      },
      updateTreeNode(data, node) {
        data.forEach((item, index) => {
          if (item.id === node.id) {
            data.splice(index, 1, node);
            return;
          }
          if (item.children) {
            this.updateTreeNode(item.children, node);
          }
        });
      },
      // 只点击子流程展开/收起
      async handleDynamicLoad(node, expanded) {
          try {
            if (expanded) {
              const { instanceId } = this.$route.query;
              const nodeDetailConfig = this.getNodeDetailConfig(node, instanceId);
              const query = Object.assign({}, nodeDetailConfig, { loop: this.theExecuteTime });
              const res = await this.getNodeActDetail(query);
              let nodeConfig = {};
              if (res.result) {
                nodeConfig = res.data;
              }
              if (!nodeConfig) return;
              // 获取子流程任务id
              const taskInfo = nodeConfig.outputs.find(item => item.key === 'task_id') || {};
              const taskId = taskInfo.value;
              if (taskId) { // 子流程任务已执行才可以查详情和状态
                  await this.getSubprocessData(taskId, node, true);
                  this.subflowTaskId = taskId;
                  this.loadSubprocessStatus();
              }
            }
            // 判断子流程是否展开
            // this.setIsExpanded(this.curNodeData[0].children, node.id, expanded);
          } catch (error) {
              console.warn(error);
          }
      },
      // 更新子流程画布节点状态
      updateSubflowCanvasNodeInfo() {
        const nodes = this.subflowNodeStatus;
        nodes && Object.keys(nodes).forEach((id) => {
          let code; let skippable; let retryable; let errorIgnorable; let autoRetry;
          const currentNode = nodes[id];
          const nodeActivities = this.subCanvasData.activities[id];

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
            task_state: this.subflowState, // 任务状态
          };
          this.setSubflowTaskNodeStatus(id, data);
        });
      },
      setSubflowTaskNodeStatus(id, data) {
        this.$refs.subProcessCanvas && this.$refs.subProcessCanvas.onUpdateNodeInfo(id, data, true);
      },

      // 获取画布中节点元素
      getNodeElement(className) {
        const canvasDom = document.querySelector('.sub-process .process-canvas-comp .canvas-material-container');
        if (!className) return canvasDom;
        return canvasDom.querySelector(className) || document.querySelector(className);
      },
      onZoomIn() {
        if (this.zoom > 1.5) {
          return;
        }
        const canvasInstance = this.$refs.subProcessCanvas.graph;
        canvasInstance.zoom(0.1);
        this.zoom = this.zoom + 0.1;
      },
      onZoomOut() {
        if (this.zoom < 0.25) {
          return;
        }
        const canvasInstance = this.$refs.subProcessCanvas.graph;
        canvasInstance.zoom(-0.1);
        this.zoom = this.zoom - 0.1;
      },
      // 移动点击节点位置
      onMoveClickNode(id) {
        if (this.isExistInSubCanvas(id)) {
            this.$refs.subProcessCanvas?.setCanvasPosition?.(id);
            this.$refs.subProcessCanvas?.onUpdateNodeInfo?.(id, { isActive: true });
        }
      },
      // 点击子流程画布中的节点
      onSubflowNodeClick(id) {
        this.subCanvasActiveId = id;
        // this.$emit('onClickSubCanvasNode', id, type, this.subCanvasData);
      },
      // 子流程画布点击网关条件
      onSubConditionClick(data) {
        this.$emit('onOpenConditionInfo', data);
      },
      onNodeTreeConditionClick(data, isCondition) {
        this.$emit('onOpenConditionInfo', data, isCondition);
      },
      onViewSubProcessExecute() {
        const { href } = this.$router.resolve({
            name: 'taskExecute',
            params: {
              spaceId: this.spaceId,
            },
            query: {
              instanceId: this.currentSubflowTaskId,
            },
        });
        return href;
      },
      // 补充记录缺少的字段
      async setFillRecordField(record) {
         const { version, component_code: componentCode, componentData = {}, node_id: nodeId } = this.nodeDetailConfig;
        const { inputs, state } = record;
        let { outputs } = record;
        // 执行记录的outputs可能为Object格式，需要转为Array格式
        if (!this.adminView && !Array.isArray(outputs)) {
          const executeOutputs = this.executeInfo.outputs;
          outputs = Object.keys(outputs).reduce((acc, key) => {
            const outputInfo = executeOutputs.find(item => item.key === key);
            if (outputInfo) {
              acc.push({ ...outputInfo, value: outputs[key] });
            } else if (key !== 'ex_data') {
              acc.push({
                key,
                name: key,
                value: outputs[key],
                preset: true,
              });
            }
            return acc;
          }, []);
        }
        let outputsInfo = [];
        const renderData = {};
        const activity = Object.assign({}, this.subCanvsActivityCollection, this.pipelineData.activities);
        let { constants } = this.pipelineData;
        let inputsInfo = inputs;
        let failInfo = '';
        // 添加插件输出表单所需上下文
        $.context.input_form.inputs = inputs;
        $.context.output_form.outputs = outputs;
        $.context.output_form.state = state;
        // 获取子流程配置详情
        if (componentCode === 'subprocess_plugin') {
          constants = activity[nodeId].component.data.subprocess.value.constants;
          this.renderConfig = await this.getSubflowInputsConfig(constants);
        } else if (componentCode) { // 任务节点需要加载标准插件
          const pluginVersion = componentData.plugin_version?.value;
          await this.getNodeConfig(componentCode, version, pluginVersion);
        }
        inputsInfo = Object.keys(inputs).reduce((acc, cur) => {
          const scheme = Array.isArray(this.renderConfig)
            ? this.renderConfig.find(item => item.tag_code === cur)
            : null;
          if (scheme) {
            const defaultValueFormat = getDefaultValueFormat(scheme);
            const valueType = checkDataType(inputs[cur]);
            const isTypeValid = Array.isArray(defaultValueFormat.type)
              ? defaultValueFormat.type.indexOf(valueType) > -1
              : defaultValueFormat.type === valueType;
            // 标记数据类型不同的表单项并原样展示数据
            if (!isTypeValid) {
              if ('attrs' in scheme) {
                scheme.attrs.usedValue = true;
              } else {
                scheme.attrs = { usedValue: true };
              }
            }
          }
          acc[cur] = inputs[cur];
          return acc;
        }, {});
        Object.keys(inputsInfo).forEach((key) => {
          renderData[key] = inputsInfo[key];
        });

        // 兼容 JOB 执行作业输出参数
        // 输出参数 preset 为 true 或者 preset 为 false 但在输出参数的全局变量中存在时，才展示
        const has = Object.prototype.hasOwnProperty;
        if (componentCode === 'job_execute_task' && has.call(inputs, 'job_global_var')) {
          outputsInfo = outputs.filter((output) => {
            const outputIndex = inputs.job_global_var.findIndex(prop => prop.name === output.key);
            if (!output.preset && outputIndex === -1) {
              return false;
            }
            return true;
          });
        } else {
          if (this.pluginCode === 'dmn_plugin') {
            outputsInfo.push(...outputs);
          } else if (this.isThirdPartyNode) {
            outputs.forEach((param) => {
              // 判断preset是否为true
              if (param.preset) {
                outputsInfo.push(param);
              } else {
                // 判断key是否与插件配置项对应
                const output = this.pluginOutputs.find(output => output.key === param.key);
                if (output) {
                  outputsInfo.push(param);
                } else {
                  // 判断key是否变量
                  const varKey = `\${${param.key}}`;
                  const varInfo = this.constants[varKey];
                  let isHooked = false;
                  if (varInfo && varInfo.source_type === 'component_outputs') {
                    isHooked = this.nodeActivity.id in varInfo.source_info;
                  }
                  if (isHooked) {
                    outputsInfo.push(param);
                  }
                }
              }
            });
          } else if (this.adminView) {
            outputsInfo = outputs;
          } else { // 普通插件展示 preset 为 true 的输出参数
            outputsInfo = outputs.filter(output => output.preset);
          }
        }
        if (record.ex_data && record.ex_data.show_ip_log) {
          failInfo = this.transformFailInfo(record.ex_data.exception_msg);
        } else {
          failInfo = this.transformFailInfo(record.ex_data);
        }
        this.$set(record, 'renderData', renderData);
        this.$set(record, 'renderConfig', this.renderConfig);
        this.$set(record, 'constants', constants);
        this.$set(record, 'outputsInfo', outputsInfo);
        this.$set(record, 'outputs', outputs);
        this.$set(record, 'inputs', inputsInfo);
        this.$set(record, 'failInfo', failInfo);
        this.$set(record, 'last_time', tools.timeTransform(record.elapsed_time));
        this.$set(record, 'isExpand', true);
        return record;
      },
      async getTaskNodeDetail(isChangeExecuteLoop) {
        try {
          // 未执行的时候不展示任何信息
          const { state, subflowNodeParent, node_id } = this.nodeDetailConfig;
          // const isUnexecutedSubprocess = componentCode === 'SubProcess' && ['READY', 'WAIT'].includes(state);
          const isUnexecutedSubprocess = this.isExistInSubCanvas(node_id) && ['READY', 'WAIT'].includes(state);
          const isExceted = subflowNodeParent && ['READY', 'WAIT'].includes(subflowNodeParent.state);
          if (this.nodeDetailConfig.root_node || isExceted || this.nodeDetailConfig?.conditionData || isUnexecutedSubprocess) return;
          const query = { ...this.nodeDetailConfig };
          if (isChangeExecuteLoop) {
            query.loop = this.theExecuteTime;
          }
          // 非任务节点请求参数不传 component_code
          if (!this.nodeDetailConfig.component_code) {
            delete query.component_code;
          }
          if (this.isFirstSubFlow(node_id)) {
            query.instance_id = this.$route.query.instanceId;
          }
          const res = await this.getNodeActDetail(query);
          if (res.result) {
            return res.data;
          }
        } catch (e) {
          console.log(e);
        }
      },
      async getNodeConfig(type, version, pluginVersion) {
        if (
          atomFilter.isConfigExists(type, version, this.atomFormConfig)
          && atomFilter.isConfigExists(type, version, this.atomOutputConfig)
        ) {
          this.renderConfig = this.atomFormConfig[type][version];
          this.outputRenderConfig = this.atomOutputConfig[type][version];
          this.isRenderOutputForm = true;
        } else {
          try {
            const res = await this.loadAtomConfig({ atom: type, version, space_id: this.spaceId });
            // api插件输入输出
            if (this.pluginCode === 'uniform_api') {
              const { api_meta: apiMeta } = this.nodeActivity.component || {};
              if (!apiMeta) return;
              // api插件配置
              const resp = await this.loadUniformApiMeta({
                taskId: this.taskId,
                spaceId: this.spaceId,
                meta_url: apiMeta.meta_url,
                ...this.scopeInfo,
              });
              if (!resp.result) return;
              // 输出参数
              const storeOutputs = this.pluginOutput.uniform_api[version];
              const outputs = resp.data.outputs || [];
              this.outputs = [...storeOutputs, ...outputs];
              this.renderConfig = jsonFormSchema(resp.data, { disabled: this.isViewMode });
              return;
            }
            // 第三方插件节点拼接输出参数
            if (this.isThirdPartyNode) {
              const resp = await this.loadPluginServiceDetail({
                plugin_code: this.thirdPartyNodeCode,
                plugin_version: pluginVersion,
                with_app_detail: true,
              });
              if (!resp.result) return;
              const { outputs: respsOutputs, forms, inputs } = resp.data;
              // 输出参数
              const storeOutputs = this.pluginOutput.remote_plugin['1.0.0'];
              const outputs = [];
              for (const [key, val] of Object.entries(respsOutputs.properties)) {
                outputs.push({
                  name: val.title,
                  key,
                  type: val.type,
                  schema: { description: val.description || '--' },
                });
              }
              this.pluginOutputs = outputs;
              this.outputRenderConfig = [...storeOutputs, ...outputs];
              if (forms.renderform) {
                // 设置host
                const { origin } = window.location;
                const hostUrl = `${origin + window.SITE_URL}plugin_service/data_api/${this.thirdPartyNodeCode}/`;
                $.context.bk_plugin_api_host[this.thirdPartyNodeCode] = hostUrl;
                // 输入参数
                const renderFrom = forms.renderform;
                /* eslint-disable-next-line */
                                eval(renderFrom)
                const config = $.atoms[this.thirdPartyNodeCode];
                this.renderConfig = config || [];
              } else {
                $.atoms[this.thirdPartyNodeCode] = inputs;
                this.renderConfig = inputs || {};
                this.outputs = []; // jsonschema form输出参数
              }
              return;
            }
            this.renderConfig = this.atomFormConfig[type] && this.atomFormConfig[type][version];
            if (res.isRenderOutputForm && this.atomOutputConfig[type]) {
              this.outputRenderConfig = this.atomOutputConfig[type][version];
            }
            this.isRenderOutputForm = res.isRenderOutputForm;
          } catch (e) {
            this.$bkMessage({
              message: e,
              theme: 'error',
              delay: 10000,
            });
          }
        }
      },
      /**
       * 加载子流程输入参数表单配置项
       * 遍历每个非隐藏的全局变量，由 source_tag、coustom_type 字段确定需要加载的标准插件
       * 同时根据 source_tag 信息获取全局变量对应标准插件的某一个表单配置项
       *
       * @return {Array} 每个非隐藏全局变量对应表单配置项组成的数组
       */
      async getSubflowInputsConfig(subflowForms) {
        const inputs = [];
        const variables = Object.keys(subflowForms)
          .map(key => subflowForms[key])
          .filter(item => item.show_type === 'show')
          .sort((a, b) => a.index - b.index);

        await Promise.all(variables.map(async (item) => {
          const variable = { ...item };
          const { key } = variable;
          const { name, atom, tagCode, classify } = atomFilter.getVariableArgs(variable);
          const version = variable.version || 'legacy';
          const isThird = Boolean(variable.plugin_code);
          const atomConfig = await this.getAtomConfig({ plugin: atom, version, classify, name, isThird });
          let formItemConfig = tools.deepClone(atomFilter.formFilter(tagCode, atomConfig));
          if (variable.is_meta || formItemConfig.meta_transform) {
            formItemConfig = formItemConfig.meta_transform(variable.meta || variable);
            if (!variable.meta) {
              variable.meta = tools.deepClone(variable);
              variable.value = formItemConfig.attrs.value;
            }
          }
          // 特殊处理逻辑，针对子流程节点，如果为自定义类型的下拉框变量，默认开始支持用户创建不存在的选项配置项
          if (variable.custom_type === 'select') {
            formItemConfig.attrs.allowCreate = true;
          }
          formItemConfig.tag_code = key.substring(2, key.length - 1);
          formItemConfig.attrs.name = variable.name;
          // 自定义输入框变量正则校验添加到插件配置项
          if (['input', 'textarea'].includes(variable.custom_type) && variable.validation !== '') {
            formItemConfig.attrs.validation.push({
              type: 'regex',
              args: variable.validation,
              error_message: i18n.t('默认值不符合正则规则：') + variable.validation,
            });
          }
          // 参数填写时为保证每个表单 tag_code 唯一，原表单 tag_code 会被替换为变量 key，导致事件监听不生效
          const has = Object.prototype.hasOwnProperty;
          if (has.call(formItemConfig, 'events')) {
            formItemConfig.events.forEach((e) => {
              if (e.source === tagCode) {
                e.source = `\${${e.source}}`;
              }
            });
          }
          inputs.push(formItemConfig);
        }));
        return inputs;
      },
      /**
       * 加载标准插件表单配置项文件
       * 优先取 store 里的缓存
       */
      async getAtomConfig(config) {
        const { plugin, version, classify, name } = config;
        try {
          // 先取标准节点缓存的数据
          const pluginGroup = this.atomFormConfig[plugin];
          if (pluginGroup && pluginGroup[version]) {
            return pluginGroup[version];
          }
          await this.loadAtomConfig({ atom: plugin, version, classify, name, space_id: this.spaceId });
          const config = $.atoms[plugin];
          return config;
        } catch (e) {
          console.log(e);
        }
      },
      transformFailInfo(data) {
        if (!data) {
          return '';
        }
        if (typeof data === 'string') {
          // 只渲染a标签，不过滤换行
          let info = data.replace(/\n/g, '<br>');
          info = this.filterXSS(info, {
            whiteList: {
              br: [],
            },
          });
          return info;
        }
        return data;
      },
      // 根据节点ID递归查找节点信息
      // @param {Array} data - 节点数据数组
      // @param {String} nodeId - 目标节点ID
      // @return {Object|null} - 返回找到的节点信息，未找到则返回null
      getNodeInfo(data, nodeId) {
          let nodeInfo;
          // 递归查找目标节点
          data.some((item) => {
              const { id, children } = item;
              if (id === nodeId) {
                  nodeInfo = item;
                  return true;
              } if (children && children.length) {
                  nodeInfo = this.getNodeInfo(item.children, nodeId);
                  return !!nodeInfo;
              }
              return false;
          });
          return nodeInfo;
      },
      // 获取子流程未执行情况下的模板画布
      async getUnexcutedSubflowTemplateCanvas(query) {
        const { subTemplateId, version } = query;
          const params = {
              templateId: subTemplateId,
              is_all_nodes: true,
              version,
          };
          const res = await this.loadSubflowConfig(params);
          this.subCanvsLocationCollection = [...res.data.pipeline_tree.location, ...this.subCanvsLocationCollection];
          this.subCanvsActivityCollection = Object.assign({}, res.data.pipeline_tree.activities);
          this.setSubActivities(this.subCanvsActivityCollection);
          this.updateCanvasData(res.data.pipeline_tree);
      },
      // 更新画布数据
      updateCanvasData(canvasData) {
        this.subCanvasData = canvasData;
        const { line, location, activities } = canvasData;
        const locations = location.map((item) => {
          const code = item.type === 'tasknode' ? activities[item.id].component.code : '';
          const mode = 'execute';
          return { ...item, mode, checked: true, code, ready: true, isSubflowCanvas: true };
        });
        this.canvasData = graphToJson({
          locations,
          lines: line,
        });
        this.canvasDataChangeKey = new Date().getTime();
      },
      isFirstSubFlow(nodeId) {
        return this.pipelineData.location.some(item => item.id === nodeId);
      },
      async getFirstSubTaskInstance(nodeId, componentCode, componentData, version) {
        if (this.isSubProcessNode) {
          this.isSubprocessLoading = true;
          this.currentIndependentSubFlowId = nodeId;
          const taskId = this.currentSubflowTaskId; // 子流程的任务id
          // nodeData 用于渲染流程树的数据
          const nodeInfo = this.getNodeInfo(this.curNodeData, nodeId);
          if (taskId) { // 子流程任务已执行才可以查详情和状态
              await this.getSubprocessData(taskId, nodeInfo);
              this.subflowTaskId = taskId;
              await this.loadSubprocessStatus(); // 获取独立子流程任务状态
              this.updateSubflowCanvasNodeInfo(); // 更新画布节点状态
              this.templateComponentName === 'SubStageCanvas' && this.$refs.subProcessCanvas.setRefreshTaskStageCanvasData();
          } else { // 未执行情况下获取模板树
          // componentCode === 'subprocess_plugin' && !isNodeInSubflow
          if (componentCode === 'subprocess_plugin') {
                const query = {
                    subTemplateId: componentData.subprocess.value.template_id,
                    version,
                };
                this.subTemplateId = componentData.subprocess.value.template_id;
                this.getUnexcutedSubflowTemplateCanvas(query);
            }
          }
        }
      },
      async loadBreadCrumbData() {
        if (this.isShowSubflowExceutedCount) {
          this.isBreadCurmbLoading = true;
          this.breadcrumbData = this.findNodePath(this.curNodeData[0].children, this.nodeDetailConfig.node_id);
          this.breadcrumbData = this.breadcrumbData.filter(item => !!item.id);
          this.breadcrumbData.forEach(async (item) => {
          if (item.id) {
            const query = {
              space_id: this.spaceId,
              instance_id: item.taskId,
              node_id: item.id,
              component_code: item.component_code,
            };
            const resp = await this.getNodeActDetail(query);
            item.allExecutedInfo = resp.data.skip ? [] : [resp.data];
            if (resp.data.histories) {
              item.allExecutedInfo.unshift(...resp.data.histories);
              item.curSelectCount = resp.data.skip ? resp.data.histories.length : resp.data.histories.length + 1;
              item.totalCount = resp.data.skip ? resp.data.histories.length : resp.data.histories.length + 1;
            } else {
              item.curSelectCount = item.allExecutedInfo.length;
              item.totalCount = item.allExecutedInfo.length;
            }
          }
          });
        }
        this.isBreadCurmbLoading = false;
      },
      async loadNodeInfo(isChangeExecuteLoop = false) {
        this.loading = true;
        this.breadcrumbData = this.findNodePath(this.curNodeData[0].children, this.nodeDetailConfig.node_id);
        this.breadcrumbData = this.breadcrumbData.filter(item => !!item.id);
        try {
          this.renderConfig = [];
          let respData = await this.getTaskNodeDetail(isChangeExecuteLoop);
          if (!respData) {
            this.isReadyStatus = false;
            this.executeInfo = {};
            this.theExecuteTime = undefined;
            this.historyInfo = [];
            this.onMoveClickNode(this.nodeDetailConfig.node_id);
            return;
          }
          this.isReadyStatus = ['RUNNING', 'SUSPENDED', 'FINISHED', 'FAILED'].indexOf(respData.state) > -1;

          respData = await this.setFillRecordField(respData);
          if (!isChangeExecuteLoop){
            this.loop = respData.loop;
            this.theExecuteTime = respData.loop;
          }
          this.executeInfo = respData;
          // 执行历史信息
          this.historyInfo = respData.skip ? [] : [respData];
          if (respData.histories) {
            this.historyInfo.unshift(...respData.histories);
          }
          // 获取记录详情
          await this.onSelectExecuteRecord(this.historyInfo.length, this.historyInfo);
          await this.loadBreadCrumbData();
          this.executeInfo.name = this.location.name || NODE_DICT[this.location.type];
          const taskInfo = respData.outputsInfo.find(item => item.key === 'task_id') || {};
          this.currentSubflowTaskId = taskInfo.value || ''; // 子流程的任务id
          // isNodeInSubflow
          const { version, node_id: nodeId, componentData, component_code: componentCode, subflowNodeParent } = this.nodeDetailConfig;
          this.executeInfo.plugin_version = this.isThirdPartyNode ? respData.inputs.plugin_version : version;
          // 获取第一层独立子流程实例数据-只要外层pipeLineTree包含该节点就是子流程第一层
          // this.isSubProcessNode && !this.nodeDetailConfig.isNodeInSubflow
          if (this.isFirstSubFlow(nodeId) && componentCode === 'subprocess_plugin') {
            this.getFirstSubTaskInstance(nodeId, componentCode, componentData, version);
          } else {
            // 顶层子流程执行后subflowNodeParent存在taskId
            if (!this.isFirstSubFlow(nodeId)) {
              this.isSubprocessLoading = true;
              // if (!this.isExistInSubCanvas(nodeId)) {
              if (subflowNodeParent && subflowNodeParent.taskId) { // 已经执行
                const resp = await this.getTaskInstanceData(subflowNodeParent.taskId);
                this.currentSubflowTaskId = subflowNodeParent.taskId;
                console.log('SideDrawerExecuteInfo.vue1413', this.currentSubflowTaskId, this.subCanvasData);
                this.subCanvsLocationCollection = [...resp.pipeline_tree.location, ...this.subCanvsLocationCollection];
                this.subCanvsActivityCollection = Object.assign({}, resp.pipeline_tree.activities);
                this.setSubActivities(this.subCanvsActivityCollection);
                this.updateCanvasData(resp.pipeline_tree);
                await this.loadSubprocessStatus();
                this.updateSubflowCanvasNodeInfo();
              } else { // 未执行
                  const { template_id: templateId } = subflowNodeParent?.component?.data?.subprocess.value || {};
                  const query = {
                    subTemplateId: templateId ?? '',
                    version: this.nodeDetailConfig.version,
                  };
                this.getUnexcutedSubflowTemplateCanvas(query);
              }
              // }
            }
          }

          // 获取执行失败节点是否允许跳过，重试状态
          if (this.realTimeState.state === 'FAILED') {
            const activityCollection = Object.assign({}, this.subCanvsActivityCollection, this.pipelineData.activities);
            const activity = activityCollection[nodeId];
            this.isShowSkipBtn = this.location.type === 'tasknode' && activity.skippable;
            this.isShowRetryBtn = this.location.type === 'tasknode' ? activity.retryable : false;
          } else {
            this.isShowSkipBtn = false;
            this.isShowRetryBtn = false;
          }

          this.isSubprocessLoading = false;
          // 激活子流程画布节点
          this.$nextTick(() => {
            this.onMoveClickNode(nodeId);
          });
        } catch (e) {
          this.theExecuteTime = undefined;
          this.executeInfo = {};
          this.historyInfo = [];
          console.log(e);
        } finally {
          this.loading = false;
        }
      },

      // 切换循环次数
      onSelectExecuteLoop(time) {
        this.theExecuteTime = time;
        this.loadNodeInfo(true);
      },
      // 切换执行次数
      async onSelectExecuteRecord(time, historyInfo) {
        const record = historyInfo[time - 1];
        if (record) {
          if (!('isExpand' in record)) {
            this.executeInfo = await this.setFillRecordField(record);
            this.executeInfo.id = this.nodeDetailConfig.node_id;
            this.executeInfo.name = this.location.name || NODE_DICT[this.location.type];
          }
          this.executeRecord = record;
        } else {
          this.executeRecord = {};
        }
      },
      async onSelectNode(selectNodeId, nodeType, node) {
        this.$emit('onClickTreeNode', selectNodeId, nodeType, node);
      },
      onRetryClick() {
        if (this.isExistInSubCanvas(this.nodeDetailConfig.node_id)) {
          this.$emit('onRetryClick', this.nodeDetailConfig.node_id, this.getEmitParams);
        } else {
          const isTopSubflow = this.isFirstSubFlow(this.nodeDetailConfig.node_id) && this.nodeDetailConfig.component_code === 'subprocess_plugin';
          this.$emit('onRetryClick', this.nodeDetailConfig.node_id, null, isTopSubflow);
        }
      },
      onSkipClick() {
         if (this.isExistInSubCanvas(this.nodeDetailConfig.node_id)) {
          this.$emit('onSkipClick', this.nodeDetailConfig.node_id, this.getEmitParams);
        } else {
          const isTopSubflow = this.isFirstSubFlow(this.nodeDetailConfig.node_id) && this.nodeDetailConfig.component_code === 'subprocess_plugin';
          this.$emit('onSkipClick', this.nodeDetailConfig.node_id, null, isTopSubflow);
        }
      },
      onResumeClick() {
        if (this.isExistInSubCanvas(this.nodeDetailConfig.node_id)) {
          this.$emit('onTaskNodeResumeClick', this.nodeDetailConfig.node_id, this.getEmitParams);
        } else {
          this.$emit('onTaskNodeResumeClick', this.nodeDetailConfig.node_id, null);
        }
      },
      onApprovalClick() {
        if (this.isExistInSubCanvas(this.nodeDetailConfig.node_id)) {
          this.$emit('onApprovalClick', this.nodeDetailConfig.node_id, this.getEmitParams);
        } else {
          this.$emit('onApprovalClick', this.nodeDetailConfig.node_id, null);
        }
      },
      onModifyTimeClick() {
        if (this.isExistInSubCanvas(this.nodeDetailConfig.node_id)) {
          this.$emit('onModifyTimeClick', this.nodeDetailConfig.node_id, this.getEmitParams);
        } else {
          this.$emit('onModifyTimeClick', this.nodeDetailConfig.node_id, null);
        }
      },
      mandatoryFailure() {
        if (this.isExistInSubCanvas(this.nodeDetailConfig.node_id)) {
          this.$emit('onForceFail', this.nodeDetailConfig.node_id, this.getEmitParams);
        } else {
          this.$emit('onForceFail', this.nodeDetailConfig.node_id, null);
        }
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
@import '../../../scss/mixins/scrollbar.scss';
@import '../../../scss/config.scss';
.parameter-details{
    height: 100%;
    display: flex;
    flex-direction: column;
    .nodeTree{
        border-right: 1px solid #DCDEE5;
    }
    .details-wrapper {
        display: flex;
        flex: 1;
        height: calc(100% - 48px);
        border-bottom: 1px solid $commonBorderColor;
    }
    .action-wrapper {
        // position: absolute;
        // bottom: 0;
        // width: 100%;
        padding-left: 20px;
        height: 48px;
        line-height: 48px;
        background: #fafbfd;
        box-shadow: 0 -1px 0 0 #dcdee5;
        z-index: 2;
        .bk-button {
            min-width: 88px;
            margin-right: 5px;
        }
    }
}
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
    .execute-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        line-height: 20px;
        font-size: 14px;
        padding: 15px 16px 16px;
        .node-name {
            font-weight: 600;
            word-break: break-all;
        }
        .node-state {
            display: flex;
            align-items: center;
            :first-child {
                margin: 2px 5px 0;
            }
            .view-subflow{
              display: flex;
              align-items: center;
              .dividing-line{
                margin: 0 13px;
                border-right: 1px solid #DCDEE5;
                height: 14px;
              }
              .icon-link-to-sub{
                font-size: 12px !important;
                margin-right: 6px;
                margin-top: 2px;
                cursor: pointer;
              }
              .text-link-to-sub{
                cursor: pointer;
              }
            }
        }
    }
    ::v-deep .bk-breadcrumb{
      display: flex;
      flex-wrap: wrap;
      .bk-breadcrumb-item{
        display: flex;
        align-items: center;
        .bk-select{
          height: 22px;
          line-height: 22px !important;
          margin: 0 8px;
          background: #F0F1F5;
          width: 42px;
          font-size: 12px;
          border: none;
          .bk-select-name{
            height: 22px;
            color: #63656E !important;
            font-weight: normal;
          }
          .bk-select-angle{
            top:0
          }
        }
        .bk-breadcrumb-separator {
           display: none !important;
        }
        .separator{
          margin: 0px;
          color: #313238;
        }
      }
      .bk-breadcrumb-item-inner{
        display: flex;
        align-items: center;
        color: #313238;
      }
      .bk-breadcrumb-separator{
        margin:0px;
        color: #313238;
      }
    }
    .execute-body{
      overflow-y: auto;
      @include scrollbar;
      height: 100%;
    }
    ::v-deep .execute-info-tab .bk-tab-section{
        padding: 0;
    }
    // .scroll-area {
    //     flex: 1;
    //     display: flex;
    //     flex-direction: column;
    //     overflow-y: auto;
    //     padding: 16px 24px 16px 16px;
    //     @include scrollbar;
    // }
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
