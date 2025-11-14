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
        :data="currentNodeData"
        :node-nav="nodeNav"
        :node-display-status="processNodeDisplayStatus"
        :selected-flow-path="selectedFlowPath"
        :default-active-id="currentDefaultActiveId"
        :is-condition="isCondition"
        :execute-info="executeInfo"
        @onOpenGatewayInfo="onOpenGatewayInfo"
        @onSelectNode="onSelectNode" />
      <div
        v-if="location"
        :key="randomKey"
        :class="['execute-info', { 'loading': loading }]">
        <div class="execute-head">
          <span class="node-name">{{ isCondition ? conditionData.name : executeInfo.name }}</span>
          <div class="node-state">
            <span :class="displayStatus" />
            <span class="status-text-messages">{{ nodeState }}</span>
            <div
              v-if="isSubflowExecuted"
              class="view-subflow">
              <span class="dividing-line" />
              <i class="common-icon-box-top-right-corner icon-link-to-sub" />
              <p @click="onViewSubProcessExecute">
                {{ $t('查看流程') }}
              </p>
            </div>
          </div>
        </div>
        <div class="execute-body">
          <!-- 子流程画布 -->
          <div
            v-if="isShowSubflowCanvas"
            class="sub-process"
            :style="{ height: `${subProcessHeight}px` }">
            <component
              :is="SubflowCanvas"
              ref="subProcessCanvas"
              :is-subflow-graph="true"
              class="sub-flow"
              :editable="false"
              :show-palette="false"
              :canvas-data="canvasData"
              @onNodeClick="onSubflowNodeClick"
              @onConditionClick="onOpenConditionEdit" />
            <div class="flow-option">
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
          <bk-tab
            :active.sync="curActiveTab"
            type="unborder-card"
            ext-cls="execute-info-tab"
            @tab-change="onTabChange">
            <bk-tab-panel
              v-if="!isCondition"
              name="record"
              :label="$t('执行记录')" />
            <bk-tab-panel
              v-if="isCondition || (!loading && ['tasknode', 'subflow', 'ServiceActivity', 'SubProcess'].includes(location.type))"
              name="config"
              :label="$t('配置快照')" />
            <bk-tab-panel
              v-if="!isCondition"
              name="history"
              :label="$t('操作历史')" />
            <bk-tab-panel
              v-if="!isCondition"
              name="log"
              :label="$t('调用日志')" />
          </bk-tab>
          <!-- 当前节点详细信息 -->
          <div class="scroll-area">
            <task-condition
              v-if="isCondition"
              ref="conditionEdit"
              :is-readonly="true"
              :is-show.sync="isShow"
              :gateways="gateways"
              :condition-data="conditionData"
              @close="close" />
            <template v-else>
              <section
                v-if="isExecuteTimeShow"
                class="execute-time-section">
                <div
                  v-if="loop > 1"
                  class="cycle-wrap">
                  <span>{{ $t('第') }}</span>
                  <bk-select
                    :clearable="false"
                    :value="theExecuteTime"
                    @selected="onSelectExecuteTime">
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
                    @selected="onSelectExecuteRecord">
                    <bk-option
                      v-for="index in historyInfo.length"
                      :id="index"
                      :key="index"
                      :name="index" />
                  </bk-select>
                  <span>{{ $t('次执行') }}</span>
                </div>
              </section>
              <ExecuteRecord
                v-if="curActiveTab === 'record'"
                :admin-view="adminView"
                :loading="loading"
                :location="location"
                :is-ready-status="isReadyStatus"
                :node-activity="nodeActivity"
                :execute-info="executeRecord"
                :node-detail-config="nodeDetailConfig"
                :plugin-code="pluginCode"
                :space-id="spaceId"
                :template-id="templateId"
                :is-sub-process-node="isSubProcessNode"
                :constants="pipelineData.constants"
                @updateOutputs="updateOutputs" />
              <ExecuteInfoForm
                v-else-if="curActiveTab === 'config'"
                :node-activity="nodeActivity"
                :execute-info="executeInfo"
                :node-detail-config="nodeDetailConfig"
                :constants="pipelineData.constants"
                :is-third-party-node="isThirdPartyNode"
                :third-party-node-code="thirdPartyNodeCode"
                :space-id="spaceId"
                :plugin-code="pluginCode"
                :template-id="templateId"
                :task_id="taskId"
                :scope-info="scopeInfo"
                :is-sub-process-node="isSubProcessNode" />
              <section
                v-else-if="curActiveTab === 'history'"
                class="info-section"
                data-test-id="taskExcute_form_operatFlow">
                <NodeOperationFlow
                  :locations="pipelineData.location"
                  :node-id="executeInfo.id"
                  :sub-process-task-id="subProcessTaskId" />
              </section>
              <NodeLog
                v-else-if="curActiveTab === 'log'"
                ref="nodeLog"
                :admin-view="adminView"
                :node-detail-config="nodeDetailConfig"
                :execute-info="executeRecord"
                :third-party-node-code="thirdPartyNodeCode" />
            </template>
          </div>
        </div>
        <!-- 底部操作按钮 -->
        <div
          v-if="isShowActionWrap"
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
              @click="$emit('onApprovalClick', nodeDetailConfig.node_id)">
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
  import { mapState, mapActions } from 'vuex';
  import tools from '@/utils/tools.js';
  import atomFilter from '@/utils/atomFilter.js';
  import { TASK_STATE_DICT, NODE_DICT } from '@/constants/index.js';
  import NodeTree from './NodeTree';
  import NodeOperationFlow from './ExecuteInfo/NodeOperationFlow.vue';
  import ExecuteRecord from './ExecuteInfo/ExecuteRecord.vue';
  import NodeLog from './ExecuteInfo/NodeLog.vue';
  import ExecuteInfoForm from './ExecuteInfo/ExecuteInfoForm.vue';
  import taskCondition from './taskCondition.vue';
  import jsonFormSchema from '@/utils/jsonFormSchema.js';
  import { checkDataType, getDefaultValueFormat } from '@/utils/checkDataType.js';
  import permission from '@/mixins/permission.js';
  import { graphToJson } from '@/utils/graphJson.js';
  import axios from 'axios';
  import SubflowCanvas from '../../../components/canvas/ProcessCanvas/SubflowCanvas.vue';

  const { CancelToken } = axios;
  let source = CancelToken.source();

  export default {
    name: 'ExecuteInfo',
    components: {
      NodeTree,
      NodeOperationFlow,
      ExecuteRecord,
      NodeLog,
      ExecuteInfoForm,
      taskCondition,
      SubflowCanvas,
    },
    mixins: [permission],
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
      pipelineData: {
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
      gateways: {
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
    },
    data() {
      return {
        randomKey: '',
        loading: true,
        isRenderOutputForm: false,
        executeInfo: {},
        pluginOutputs: [],
        historyInfo: [],
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
        loop: 1,
        theExecuteTime: undefined,
        isReadyStatus: true,
        isShowSkipBtn: false,
        isShowRetryBtn: false,
        curActiveTab: 'record',
        theExecuteRecord: 0,
        executeRecord: {},
        zoom: 0.75, // 画布缩放
        subProcessHeight: 320,
        subprocessLoading: true,
        subCanvasData: {},
        canvasData: [],
        currentDefaultActiveId: tools.deepClone(this.defaultActiveId),
        currentSubflowTaskId: '',
        currentNodeData: tools.deepClone(this.nodeData),
        subflowNodeStatus: {},
        subflowTaskId: '',
        canvasRandomKey: '',
        subflowState: '',
        currentNodeDisplayStatus: tools.deepClone(this.nodeDisplayStatus),
        currentIndependentSubFlowId: '',
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
      location() {
        const { node_id: nodeId, subprocess_stack: subprocessStack = [], subflowNode } = this.nodeDetailConfig;
        const currentPipelineData  = subflowNode?.parent && !subflowNode?.parent?.isGateway ? subflowNode.parent.children : this.pipelineData.location;
        return currentPipelineData.find((item) => {
          let result = false;
          if (item.id === nodeId || subprocessStack.includes(item.id)) {
            result = true;
          }
          return result;
        });
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
        // let codeInfo = {};
        // if (this.nodeDetailConfig.subflowNode?.parent) {
        //   codeInfo = this.nodeDetailConfig.componentData.plugin_code;
        // } else {
        const nodeInfo = this.pipelineData.activities[this.nodeDetailConfig.node_id];
        if (!nodeInfo) return '';
        let codeInfo = nodeInfo.component.data;
        codeInfo = codeInfo && codeInfo.plugin_code;
        // }
        codeInfo = codeInfo.value;
        return codeInfo;
      },
      nodeActivity() {
        // if (this.nodeDetailConfig.subflowNode?.parent) {
        //    const parentPipeline = this.nodeDetailConfig.subflowNode.parent.children;
        //    let nodeActivityData = {};
        //    parentPipeline.map((item) => {
        //     if (item.id === this.nodeDetailConfig.node_id) {
        //       nodeActivityData = item;
        //     }
        //    });
        //    return nodeActivityData;
        // }
        return this.pipelineData.activities[this.nodeDetailConfig.node_id];
      },
      componentValue() {
        return this.isSubProcessNode ? this.nodeActivity.component.data.subprocess.value : {};
      },
      isExecuteTimeShow() {
        return ['record', 'log'].includes(this.curActiveTab) && (this.loop > 1 || this.historyInfo.length > 1);
      },
      isShowActionWrap() {
        // 任务终止时禁止节点操作
        if (this.state === 'REVOKED' || !this.instanceActions.includes('OPERATE')) {
          return false;
        }
        return (this.realTimeState.state === 'RUNNING' && !this.isSubProcessNode) || this.isShowRetryBtn || this.isShowSkipBtn;
      },
            isShowSubflowCanvas() {
        const subflowParent = this.nodeDetailConfig?.subflowNode?.parent;
        const isSubChildren = subflowParent !== null && subflowParent?.component?.code === 'subprocess_plugin';
        const isSubprocessNode = this.nodeDetailConfig.component_code === 'subprocess_plugin';
        return isSubprocessNode || isSubChildren;
      },
      // 加入子流程节点后的nodeDisplayStatus
      processNodeDisplayStatus() {
        this.currentNodeDisplayStatus.children = Object.assign({}, this.currentNodeDisplayStatus.children, this.subflowNodeStatus);
        return this.currentNodeDisplayStatus;
      },
      isSubflowExecuted() {
        // this.nodeDetailConfig.component_code === 'subprocess_plugin'
       return this.currentSubflowTaskId !== '' && this.isSubProcessNode;
      },
      subProcessTaskId() { // 独立子流程节点的任务id
        return this.nodeDetailConfig.instance_id;
      },
    },
    watch: {
      nodeDetailConfig: {
        async handler(val) {
          // 获取子流程画布
          if (val.component_code === 'subprocess_plugin' && !val?.isNodeInSubflow) {
              const subTemplateId = val.componentData.subprocess.value.template_id;
              const params = {
                templateId: subTemplateId,
                is_all_nodes: true,
              };
              const res = await this.loadSubflowConfig(params);
              this.subCanvasData = res.data.pipeline_tree;
              const { line, location, activities } = this.subCanvasData;
              const locations = location.map((item) => {
                const code = item.type === 'tasknode' ? activities[item.id].component.code : '';
                const mode = 'execute';
                return { ...item, mode, checked: true, code, ready: true };
              });
              this.canvasData = graphToJson({
                locations,
                lines: line,
              });
              this.subprocessLoading = false;
          }
          if (val.node_id !== undefined) {
            this.loadNodeInfo();
          }
        },
        deep: true,
        immediate: true,
      },
    },
    mounted() {
      this.loadNodeInfo();
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
      ...mapActions('template/', [
        'loadUniformApiMeta',
      ]),
      ...mapActions('atomForm/', [
        'loadAtomConfig',
        'loadPluginServiceDetail',
        'loadPluginServiceAppDetail',
      ]),
      async loadSubprocessStatus() {
        try {
          if (source) {
              source.cancel('cancelled'); // 取消定时器里已经执行的请求
              this.timer = null;
          }
          source = CancelToken.source();
          const taskIds = Object.keys(this.subprocessTasks);
          if (!taskIds.length) return;
          const data = {
            instance_id: this.subflowTaskId || '',
            project_id: this.project_id,
            cancelToken: source.token,
          };
          const resp = await this.getInstanceStatus(data);
          this.subflowState = resp.data.state;
          this.subflowNodeStatus = resp.data.children || {};
          // }

          if (Object.keys(this.subprocessTasks).length) {
              this.setTaskStatusTimer();
          }
        } catch (error) {
            console.warn(error);
        } finally {
            source = null;
            this.subprocessLoading = false;
        }
      },
      setTaskStatusTimer(time = 3000) {
          this.cancelTaskStatusTimer();
          this.timer = setTimeout(() => {
              this.loadSubprocessStatus();
          }, time);
      },
      cancelTaskStatusTimer() {
          if (this.timer) {
              clearTimeout(this.timer);
              this.timer = null;
          }
      },
      // 根据节点ID递归查找节点信息
      // @param {Array} data - 节点数据数组
      // @param {String} rootId - 根节点ID（可选），格式为'id1-id2-id3'，表示从指定父节点开始查找
      // @param {String} nodeId - 目标节点ID
      // @return {Object|null} - 返回找到的节点信息，未找到则返回null
      getNodeInfo(data, rootId, nodeId) {
          let nodes = data;
          // 如果指定了rootId，则从指定的父节点开始查找
          if (rootId) {
              const parentId = rootId.split('-') || [];
              parentId.forEach((id) => {
                  nodes.some((item) => {
                      if (item.id === id) {
                          nodes = item.children;
                          return true;
                      }
                      return false;
                  });
              });
          }
          let nodeInfo;
          // 递归查找目标节点
          nodes.some((item) => {
              const { id, children } = item;
              if (id === nodeId) {
                  nodeInfo = item;
                  return true;
              } if (children && children.length) {
                  nodeInfo = this.getNodeInfo(item.children, '', nodeId);
                  return !!nodeInfo;
              }
              return false;
          });
          return nodeInfo;
      },
      // 获取节点配置
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
      // 获取独立子流程节点详情
      async getSubprocessData(taskId, nodeInfo) {
          try {
              const parentId = nodeInfo.parent?.id?.split('-') || [];
                  const resp = await this.getTaskInstanceData(taskId);
                  const pipelineTree = resp.pipeline_tree;
                  // 获取子流程画布
                  if (!this.nodeDetailConfig.isNodeInSubflow) {
                    this.subCanvasData = resp.pipeline_tree;
                    const { line, location, activities } = this.subCanvasData;
                    const locations = location.map((item) => {
                      const code = item.type === 'tasknode' ? activities[item.id].component.code : '';
                      const mode = 'execute';
                      return { ...item, mode, checked: true, code, ready: true };
                    });
                    this.canvasData = graphToJson({
                      locations,
                      lines: line,
                    });
                  }
                  const parentInstance = this.$parent.$parent;
                  parentInstance.nodeIds[pipelineTree.id] = [];
                  nodeInfo.children = parentInstance.getOrderedTree(pipelineTree);
                  nodeInfo.dynamicLoad = false;
                  nodeInfo.expanded = true;
                  let { pipelineData } = parentInstance;
                  if (parentId) {
                      parentId.forEach((item) => {
                          const nodeData = pipelineData.activities[item];
                          if (nodeData.pipeline) {
                              pipelineData = nodeData.pipeline;
                          } else {
                              let { data: componentData } = nodeData.component;
                              componentData = componentData && componentData.subprocess;
                              componentData = componentData && componentData.value;
                              componentData = componentData && componentData.pipeline;
                              pipelineData = componentData || pipelineData;
                          }
                      });
                  }
                  const nodeActivity = pipelineData.activities[nodeInfo.id];
                  this.$set(nodeActivity, 'pipeline', { ...pipelineTree, taskId });
              // }
          } catch (error) {
              console.warn(error);
              this.subprocessLoading = false;
          }
      },
      // 只点击子流程展开/收起
      async handleDynamicLoad(node) {
          try {
            if (node.id.includes('条件')) {
              return;
            }
            const { id } = node;
            const { instanceId } = this.$route.query;
            const nodeDetailConfig = this.getNodeDetailConfig(node, node.taskId || instanceId);
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
                await this.getSubprocessData(taskId, node);
                this.subprocessTasks[taskId] = {
                    root_node: nodeConfig.parent_id,
                    node_id: id,
                };
                this.subflowTaskId = taskId;
                this.loadSubprocessStatus();
            }
            // 判断子流程是否展开
            this.currentNodeData.forEach((item) => {
                if (item.id === node.id) {
                  item.expanded = node.expanded;
                }
            });
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
      async loadNodeInfo() {
        this.loading = true;
        try {
          this.renderConfig = [];
          const respData = await this.getTaskNodeDetail();
          if (!respData) {
            this.isReadyStatus = false;
            this.executeInfo = {};
            this.theExecuteTime = undefined;
            this.historyInfo = [];
            return;
          }
          this.isReadyStatus = ['RUNNING', 'SUSPENDED', 'FINISHED', 'FAILED'].indexOf(respData.state) > -1;

          await this.setFillRecordField(respData);
          if (this.theExecuteTime === undefined) {
            this.loop = respData.loop;
            this.theExecuteTime = respData.loop;
          }
          this.executeInfo = respData;
          this.historyInfo = respData.skip ? [] : [respData];
          if (respData.histories) {
            this.historyInfo.unshift(...respData.histories);
          }
          // 记录当前循环下，总共执行的次数
          this.theExecuteRecord = this.historyInfo.length;
          // 获取记录详情
          await this.onSelectExecuteRecord(this.theExecuteRecord);
          this.executeInfo.name = this.location.name || NODE_DICT[this.location.type];
          const { component_code: componentCode, version } = this.nodeDetailConfig;
          this.executeInfo.plugin_version = this.isThirdPartyNode ? respData.inputs.plugin_version : version;
          if (this.isThirdPartyNode) {
            const resp = await this.loadPluginServiceAppDetail({ plugin_code: this.thirdPartyNodeCode });
            this.executeInfo.plugin_name = resp.data.name;
          } else if (atomFilter.isConfigExists(componentCode, version, this.atomFormInfo)) {
            const pluginInfo = this.atomFormInfo[componentCode][version];
            this.executeInfo.plugin_name = `${pluginInfo.group_name}-${pluginInfo.name}`;
          }
          // 获取执行失败节点是否允许跳过，重试状态
          if (this.realTimeState.state === 'FAILED') {
            const activity = this.pipelineData.activities[this.nodeDetailConfig.node_id];
            this.isShowSkipBtn = this.location.type === 'tasknode' && activity.skippable;
            this.isShowRetryBtn = this.location.type === 'tasknode' ? activity.retryable : false;
          } else {
            this.isShowSkipBtn = false;
            this.isShowRetryBtn = false;
          }
        } catch (e) {
          this.theExecuteTime = undefined;
          this.executeInfo = {};
          this.historyInfo = [];
          console.log(e);
        } finally {
          this.randomKey = new Date().getTime();
          this.loading = false;
        }
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
      // 点击子流程画布中的节点
      onSubflowNodeClick(id) {
        this.currentDefaultActiveId = id;
        // this.isClickSubCanvasNode = true;
        // this.$emit('onNodeClick', id, type, true, this.subCanvasData);
      },
      // 点击网关条件
      onOpenConditionEdit(data) {
        this.$emit('onConditionClick', data);
      },
      onOpenGatewayInfo(data, isCondition) {
        this.$emit('onOpenGatewayInfo', data, isCondition);
      },
      close() {
        this.$emit('close');
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
        window.open(href, '_blank');
      },
      // 补充记录缺少的字段
      async setFillRecordField(record) {
        const { version, component_code: componentCode, componentData = {} } = this.nodeDetailConfig;
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
        const constants = {};
        let inputsInfo = inputs;
        let failInfo = '';
        // 判断是否为旧版子流程
        // const islegacySubProcess = !this.isSubProcessNode && this.nodeActivity && this.nodeActivity.type === 'SubProcess';
        // 添加插件输出表单所需上下文
        $.context.input_form.inputs = inputs;
        $.context.output_form.outputs = outputs;
        $.context.output_form.state = state;
        // 获取子流程配置详情
        if (componentCode === 'subprocess_plugin') {
          const { constants } =  this.pipelineData;
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
      },
      async getTaskNodeDetail() {
        try {
          if (this.nodeDetailConfig.root_node) return;
          const query = Object.assign({}, this.nodeDetailConfig, { loop: this.theExecuteTime });

          // 非任务节点请求参数不传 component_code
          if (!this.nodeDetailConfig.component_code) {
            delete query.component_code;
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
          formItemConfig.tag_code = key;
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
      onSelectExecuteTime(time) {
        this.theExecuteTime = time;
        this.loadNodeInfo();
        this.randomKey = new Date().getTime();
      },
      async onSelectExecuteRecord(time) {
        this.theExecuteRecord = time;
        const record = this.historyInfo[time - 1];
        if (record) {
          if (!('isExpand' in record)) {
            await this.setFillRecordField(record);
          }
          this.executeRecord = record;
        } else {
          this.executeRecord = {};
        }
        this.randomKey = new Date().getTime();
      },
      onTabChange(name) {
        this.curActiveTab = name;
        if (['record', 'log'].includes(name)) {
          this.onSelectExecuteRecord(this.theExecuteRecord);
        }
      },
      async onSelectNode(nodeHeirarchy, selectNodeId, nodeType, node) {
        this.curActiveTab = 'record';
        this.loading = true;
        this.$emit('onClickTreeNode', nodeHeirarchy, selectNodeId, nodeType, node);
      },
      onRetryClick() {
        this.$emit('onRetryClick', this.nodeDetailConfig.node_id);
      },
      onSkipClick() {
        this.$emit('onSkipClick', this.nodeDetailConfig.node_id);
      },
      onResumeClick() {
        this.$emit('onTaskNodeResumeClick', this.nodeDetailConfig.node_id);
      },
      onModifyTimeClick() {
        this.$emit('onModifyTimeClick', this.nodeDetailConfig.node_id);
      },
      mandatoryFailure() {
        this.$emit('onForceFail', this.nodeDetailConfig.node_id);
      },
      updateOutputs(outputs) {
        this.executeRecord.outputsInfo = this.executeRecord.outputsInfo.reduce((acc, cur) => {
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
              }
            }
        }
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
