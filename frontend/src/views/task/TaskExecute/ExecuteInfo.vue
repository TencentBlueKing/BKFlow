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
        :data="nodeData"
        :node-nav="nodeNav"
        :node-display-status="nodeDisplayStatus"
        :selected-flow-path="selectedFlowPath"
        :default-active-id="currentDefaultActiveId"
        :is-condition="isCondition"
        :execute-info="executeInfo"
        @onOpenGatewayInfo="onOpenGatewayInfo"
        @onNodeClick="onNodeClick"
        @onSelectNode="onSelectNode" />
      <div
        v-if="location"
        :key="randomKey"
        v-bkloading="{ isLoading: loading, opacity: 1, zIndex: 100 }"
        :class="['execute-info', { 'loading': loading }]">
        <div class="execute-head">
          <span class="node-name">{{ isCondition ? conditionData.name : executeInfo.name }}</span>
          <div class="node-state">
            <span :class="displayStatus" />
            <span class="status-text-messages">{{ nodeState }}</span>
            <div
              v-if="nodeDetailConfig.component_code === 'subprocess_plugin' "
              class="view-subflow">
              <span class="dividing-line" />
              <i class="common-icon-box-top-right-corner icon-link-to-sub" />
              <p>
                <!-- <router-link
                  :to="{
                    name: 'templatePanel',
                    params: {
                      templateId: props.row.id,
                      type: 'view'
                    }
                  }">
                  {{ $t('查看流程') }}
                </router-link> -->
                {{ $t('查看流程') }}
              </p>
            </div>
          </div>
        </div>
        <div style="overflow-y:auto">
          <!-- 子流程画布 -->
          <div
            v-if="nodeDetailConfig.component_code === 'subprocess_plugin' || nodeDetailConfig?.subflowNode?.parent"
            class="sub-process"
            :style="{ height: `${subProcessHeight}px` }">
            <component
              :is="templateComponentName"
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
              v-if="isCondition || (!loading && ['tasknode', 'subflow'].includes(location.type))"
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
                  :node-id="executeInfo.id" />
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
  import VerticalCanvas from '@/components/canvas/VerticalCanvas/index.vue';
  import ProcessCanvas from '@/components/canvas/ProcessCanvas/index.vue';
  import StageCanvas from '@/components/canvas/StageCanvas/index.vue';
  import { graphToJson } from '@/utils/graphJson.js';
  import axios from 'axios';

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
      VerticalCanvas,
      ProcessCanvas,
      StageCanvas,
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
        // currentNodeData: [],
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
        const nodeStateMap = this.nodeDisplayStatus.children || {};
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
        console.log('this.pipelineData', this.pipelineData);
        console.log('subflowNode?.parent', subflowNode?.parent);
        const currentPipelineData  = subflowNode?.parent && !subflowNode?.parent?.isGateway ? subflowNode.parent.pipeline : this.pipelineData;
        return currentPipelineData.location.find((item) => {
          let result = false;
          if (item.id === nodeId || subprocessStack.includes(item.id)) {
            result = true;
          }
          return result;
        });
      },
      pluginCode() {
        console.log('查看插件代码', this.nodeDetailConfig);
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
        const nodeInfo = this.pipelineData.activities[this.nodeDetailConfig.node_id];
        if (!nodeInfo) return '';
        let codeInfo = nodeInfo.component.data;
        codeInfo = codeInfo && codeInfo.plugin_code;
        codeInfo = codeInfo.value;
        return codeInfo;
      },
      nodeActivity() {
        console.log('nodeActivity--', this.nodeDetailConfig);
        if (this.nodeDetailConfig.subflowNode?.parent) {
           const parentPipeline = this.nodeDetailConfig.subflowNode.parent.pipeline;
            return parentPipeline.activities[this.nodeDetailConfig.node_id];
        }
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
      templateComponentName() {
          const canvasModeToComponentMap = {
            horizontal: 'ProcessCanvas',
            vertical: 'VerticalCanvas',
            stage: 'StageCanvas',
          };
          return canvasModeToComponentMap[this.canvasMode] || canvasModeToComponentMap.horizontal;
      },
      // 子流程画布树
      // canvasData() {
      //   const { line, location, activities } = this.subCanvasData;

      //   const locations = location.map((item) => {
      //     const code = item.type === 'tasknode' ? activities[item.id].component.code : '';
      //     const mode = this.hasOperatePerm ? 'execute' : '';
      //     return { ...item, mode, checked: true, code, ready: true };
      //   });
      //   const afterCanvasData = graphToJson({
      //     locations,
      //     lines: line,
      //   });
      //   console.log('子流程画布数据afterCanvasData', afterCanvasData);
      //   this.subprocessLoading = false;
      //   return afterCanvasData;
      // },
    },
    watch: {
      nodeDetailConfig: {
        async handler(val) {
          console.log('nodeDetailConfig--watch--', val);
            if (val.node_id !== undefined) {
              this.loadNodeInfo();
              console.log('nodeDetailConfig--watch--加载节点信息', this.executeInfo);
              // this.executeInfo = {};
            }
            if (val.component_code === 'subprocess_plugin') {
              // console.log('子流程节点信息', val);
              const subTemplateId = val.componentData.subprocess.value.template_id;
              const params = {
                templateId: subTemplateId,
                is_all_nodes: true,
              };
              const res = await this.loadSubflowConfig(params);
              // console.log('子流程pipelinetree', res);
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
              // console.log('子流程画布数据afterCanvasData', this.canvasData);
              // this.canvasData = afterCanvasData;
              this.subprocessLoading = false;
                // const { lines, locations: nodes } = this.subCanvasData;
                // this.subFlowData = {
                //     lines,
                //     nodes,
                // };
            }
        },
        deep: true,
        immediate: true,
      },
    },
    mounted() {
      this.loadNodeInfo();
      // this.$nextTick(() => {
      //     this.setCanvasZoomPosition();
      // });
    },
    methods: {
      ...mapActions('task/', [
        'getNodeActDetail',
        'loadSubflowConfig',
        'getInstanceStatus',
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
          console.log('subprocessTasks---', this.subprocessTasks);
          const taskIds = Object.keys(this.subprocessTasks);
          console.log('taskIds', taskIds);
          if (!taskIds.length) return;
          const data = {
            instance_id: this.taskId,
            project_id: this.project_id,
            cancelToken: source.token,
          };
          const resp = await this.getInstanceStatus(data);
          console.log('获取子流程状态resp', resp);

          // Object.keys(resp.data).forEach((key) => {
          //     this.$set(this.subprocessNodeStatus, key, resp.data[key]);
          // });
          for (const [key, value] of Object.entries(resp.data)) {
              const { root_node, node_id } = this.subprocessTasks[key];
              const nodeInfo = this.getNodeInfo(this.nodeData, root_node, node_id);
              this.nodeAddStatus(nodeInfo.children, value.data.children);
              this.updateNodeInfo(value.data.children);
              if (!['CREATED', 'RUNNING'].includes(value.data.state)) {
                  delete this.subprocessTasks[key];
              }
          }
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
          });
          return nodeInfo;
      },

      async loadNodeInfo() {
        this.loading = true;
        try {
          this.renderConfig = [];
          const respData = await this.getTaskNodeDetail();
          // console.log('获取节点详情信息-loadNodeInfo', respData, !respData);
          if (!respData) {
            this.isReadyStatus = false;
            this.executeInfo = {};
            // 未执行节点执行记录信息
            this.executeRecord = {};
            console.log('respData不存在', this.executeInfo);
            this.theExecuteTime = undefined;
            this.historyInfo = [];
            this.randomKey = new Date().getTime();
            return;
          }
          // console.log('respData是否存在', !respData);
          this.isReadyStatus = ['RUNNING', 'SUSPENDED', 'FINISHED', 'FAILED'].indexOf(respData.state) > -1;

          await this.setFillRecordField(respData);
          if (this.theExecuteTime === undefined) {
            this.loop = respData.loop;
            this.theExecuteTime = respData.loop;
          }
          this.executeInfo = respData;

          // 获取子流程状态
          // if (this.isSubProcessNode) {
          //   console.log('获取子流程状态');
          //     const taskInfo = respData.outputsInfo.find(item => item.key === 'task_id') || {};
          //     const taskId = taskInfo.value; // 子流程的id
          //     const { root_node, node_id } = this.nodeDetailConfig;
          //     this.subprocessLoading = true;
          //     const nodeInfo = this.getNodeInfo(this.nodeData, root_node, node_id);
          //     // console.log('子流程节点信息nodeInfo', nodeInfo, taskId);
          //     if (taskId) { // 子流程任务已执行才可以查详情和状态
          //         // 获取子流程任务详情
          //         // await this.getSubprocessData(taskId, nodeInfo);
          //         this.subprocessTasks[taskId] = {
          //             root_node,
          //             node_id,
          //         };
          //         // 获取独立子流程任务状态
          //         this.loadSubprocessStatus();
          //     } else {
          //         nodeInfo.dynamicLoad = false;
          //         this.subprocessLoading = false;
          //         // 记录子流程展开收起
          //         this.setSubNodeExpanded(nodeInfo);
          //     }
          // } else if (this.subProcessPipeline) {
          //     this.subprocessLoading = false;
          // }

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
          console.log('加载完节点信息-this.executeInfo', this.executeInfo);
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
        console.log('.canvas-material-container', document.querySelector('.canvas-material-container'));
        const canvasDom = document.querySelector('.sub-process .process-canvas-comp .canvas-material-container');
        console.log('canvasDom', canvasDom);
        console.log('canvasDom.querySelector(className)', canvasDom.querySelector(className));
        console.log('document.querySelector(className)', document.querySelector(className));
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
      // dom是否存在当前视图中
      judgeInViewPort(element) {
          if (!element) return false;
          const { width, height, top: canvasTop, left: canvasLeft } = this.$el.querySelector('.sub-flow').getBoundingClientRect();
          const { top, left } = element.getBoundingClientRect();
          return top > canvasTop && top < canvasTop + height && left > canvasLeft && left < canvasLeft + width;
      },
      // 暂时写死便于开发
      // 画布初始化时缩放比偏移
      // setCanvasZoomPosition() {
      //   // 计算子流程画布高度
      //   const dndComponent = this.$refs.subProcessCanvas.$el;
      //   // console.log('this.$refs.subProcessCanvas.$el-height', this.$refs.subProcessCanvas.$el.getBoundingClientRect());
      //   const { top } = dndComponent.getBoundingClientRect();
      //   this.subProcessHeight = (window.innerHeight - top - 320) < 320 ? 320 : window.innerHeight - top - 320 ;
      //   // console.log('subProcessHeight', this.subProcessHeight, window.innerHeight);
      //   // 画布实例

      //   const canvasInstance = this.$refs.subProcessCanvas.graph;
      //   // canvasInstance.centerContent();
      //   canvasInstance.zoom(this.zoom);
      //   // console.log('this.$refs.subProcessCanvas.graph', this.$refs.subProcessCanvas.graph);
      //   // const { width, height } = dndComponent.getBoundingClientRect();
      //   // 指定中心点进行缩放
      //   // canvasInstance.zoom(this.zoom, {
      //   //     x: width / 2,
      //   //     y: height / 2,
      //   // });

      //   // 判断dom是否存在当前视图中
      //   const startNode = this.canvasData.find(item => item.data.type === 'start');
      //   // console.log('startNode', startNode);
      //   // 将节点移动到画布中间
      //   const nodeEl = document.querySelector(`g[data-cell-id="${startNode.id}"] .custom-node`);
      //   // this.$refs.subProcessCanvas.setCanvasPosition(startNode.id, 'top-left');
      //   // const nodeEl = this.getNodeElement(`g[data-cell-id="${startNode.id}"]`);
      //   // console.log('nodeEl', nodeEl);
      //   // if (!nodeEl) return;
      //   // const isInViewPort = this.judgeInViewPort(nodeEl);
      //   // console.log('isInViewPort--', isInViewPort);
      //   // if (!isInViewPort) {
      //   //     // 获取画布视图信息
      //   //     const viewport = canvasInstance.getViewport();
      //   //     // 计算目标位置，将起始节点放在画布可见区域的上方偏左位置
      //   //     const targetX = (viewport.width / 4 - startNode.x) * this.zoom;
      //   //     const targetY = (viewport.height / 3 - startNode.y) * this.zoom;
      //   //     // 添加边界检查，防止画布偏移过大
      //   //     const maxOffsetX = 500;
      //   //     const maxOffsetY = 500;
      //   //     const limitedX = Math.max(-maxOffsetX, Math.min(maxOffsetX, targetX));
      //   //     const limitedY = Math.max(-maxOffsetY, Math.min(maxOffsetY, targetY));
      //   //     // 设置画布位置
      //   //     canvasInstance.translate(limitedX, limitedY, {
      //   //         animation: {
      //   //             duration: 300,  // 动画持续时间（毫秒）
      //   //             easing: 'ease-out',
      //   //         },
      //   //     });
      //   // }
      // },
      onNodeClick(id, type) {
        console.log('节点详情-节点点击-id-type', id, type);
        this.$emit('onNodeClick', id, type);
      },
      // 点击子流程节点
      onSubflowNodeClick(id, type) {
        console.log('点击子流程节点-id-type', id, type);
        // nodetree做相应的激活
        this.currentDefaultActiveId = id;
        // this.$emit('onNodeClick', id, type, true, this.subCanvasData);
      },
      // 点击网关条件
      onOpenConditionEdit(data) {
        console.log('节点详情-点击网关条件', data);
        // this.$emit('onConditionClick', data);
      },
      onOpenGatewayInfo(data, isCondition) {
        this.$emit('onOpenGatewayInfo', data, isCondition);
      },
      close() {
        this.$emit('close');
      },
      // 补充记录缺少的字段
      async setFillRecordField(record) {
        // console.log('setFillRecordField-record', record);
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
        // console.log('this.nodeActivity', this.nodeActivity);
        // const islegacySubProcess = !this.isSubProcessNode && this.nodeActivity && this.nodeActivity.type === 'SubProcess';
        // 添加插件输出表单所需上下文
        $.context.input_form.inputs = inputs;
        $.context.output_form.outputs = outputs;
        $.context.output_form.state = state;
        // console.log('this.componentValue.pipeline', this.componentValue.pipeline);
        // console.log('this.pipelineData', this.pipelineData);
        // console.log('componentCode', componentCode);
        // 获取子流程配置详情
        if (componentCode === 'subprocess_plugin') {
          const { constants } =  this.pipelineData;
          this.renderConfig = await this.getSubflowInputsConfig(constants);
        } else if (componentCode) { // 任务节点需要加载标准插件
          const pluginVersion = componentData.plugin_version?.value;
          console.log('加载第三方插件componentCode', componentCode);
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
        // console.log('补充字段后record', record);
      },
      async getTaskNodeDetail() {
        try {
          console.log('getTaskNodeDetail--', this.nodeDetailConfig);
          // 未执行的时候不展示任何信息
          if (this.nodeDetailConfig.root_node || (this.nodeDetailConfig?.subflowNode?.parent && this.nodeDetailConfig.subflowNode?.state === 'WAIT')) return;
          const query = Object.assign({}, this.nodeDetailConfig, { loop: this.theExecuteTime });

          // 非任务节点请求参数不传 component_code
          if (!this.nodeDetailConfig.component_code) {
            delete query.component_code;
          }

          const res = await this.getNodeActDetail(query);
          if (res.result) {
            console.log('获取任务节点详情-res.data--', res.data);
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
        console.log('获取执行记录详情historyInfo', this.historyInfo, time);
        const record = this.historyInfo[time - 1];
        if (record) {
          if (!('isExpand' in record)) {
            console.log('isExpand--', record);
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
      onSelectNode(nodeHeirarchy, selectNodeId, nodeType, node) {
        this.curActiveTab = 'record';
        this.loading = true;
        console.log('--------------------------------------------------------');
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
