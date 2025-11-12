
<template>
  <div
    class="flowchart-container "
    :class="{
      isPreview:!editable,
      isExecute
    }">
    <JobAndStageEidtSld
      :is-show.sync="isShowJobAndStageEdit"
      :init-data="activeNode"
      :editable="editable"
      @confirm="hadEditedJobAndStage"
      @cancel="cancelJobAndStageEidtSld" />
    <div
      ref="stageContainer"
      class="stage-container">
      <StageNode
        v-for="(stage,index) in stageCanvasData"
        :key="stage.id"
        :stage="stage"
        :stages="stageCanvasData"
        :index="(index+1).toString()"
        :editable="editable"
        :constants="constants"
        :is-execute="isExecute"
        @deleteNode="deletNode(index)"
        @handleOperateNode="handleOperateNode"
        @addNewStage="addNewStage(index)"
        @refreshPPLT="refresh"
        @handleNode="handleNode"
        @copyNode="handleCopyNode(stage,index)" />
    </div>
  </div>
</template>
<script lang="js">

import StageNode from './components/StageNode.vue';

import {  ETaskStatusType, getDefaultNewStage, stage } from './data';
import { gatherStageCanvasConstans, generatePplTreeByCurrentStageCanvasData, getCopyNode } from './utils';
import JobAndStageEidtSld from './components/JobAndStageEditSld/index.vue';
import { mapGetters, mapMutations, mapState } from 'vuex';
import axios from 'axios';
import { cloneDeepWith } from 'lodash';
import Sortable from 'sortablejs';

 export default {
  name: 'StageCanvas',
  components: {
    StageNode,
    JobAndStageEidtSld,
  },
  props: {
    editable: {
      type: Boolean,
      default: false,
    },
    isExecute: {
      type: Boolean,
      default: false,
    },
    templateId: {
        type: [Number, String],
        default: '',
      },
    instanceId: {
        type: [Number, String],
        default: '',
      },
    spaceId: {
      type: [Number, String],
      default: '',
    },
    overallState: {
      type: String,
      default: '',
    },
  },

  data() {
    return {
        stageData: [...stage],
        activeItem: null,
        isShowJobAndStageEdit: false,
        constants: [],
        timer: null,
        isPolling: false,
        debounceTimer: null,
        sortableInstance: null,
        stageCanvasConstansSet: null,
        taskNodeIdMap: null,
      };
    },
  computed: {
    ...mapState({
        activeNode: state => state.stageCanvas.activeNode,
        stageCanvasData: state => state.template.stage_canvas_data,
        activities: state => state.template.activities,
      }),
      ...mapGetters('template/', [
        'getPipelineTree',
      ]),
      plugins() {
        return Object.values(this.activities).reduce((res, item) => {
          if (item.component && item.component.code) {
            if (item.component.code === 'uniform_api') {
              res.uniform_api.push({
                plugin_code: item.component.data.plugin_code.value,
              });
            } else if (item.component.code === 'remote_plugin') {
              res.blueking.push({
                plugin_code: item.component.data.plugin_code.value,
              });
            } else {
              res.component.push({
                plugin_code: item.component.code,
              });
            }
          }
          return res;
        }, { component: [], uniform_api: [], blueking: [] });
      },

  },
  watch: {
    activeNode: {
      handler(value) {
        if (value) {
          this.isShowJobAndStageEdit = true;
        }
      },
    },
    plugins: {
      handler() {
        this.debounceTimer && clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => {
          this.refreshPluginIcon();
          this.debounceTimer = null;
        }, 1000);
      },
    },
    editable: {
      handler(value) {
        this.sortableInstance.option('disabled', !value);
      },
    },
    overallState: {
      handler(value) {
        console.log('index.vue_Line:149', 'overallState', value);
        if (window.parent) {
          window.parent.postMessage({ eventName: 'bk-flow-task-state-change', state: value }, '*');
        }
      },
    },
  },
  async mounted() {
    if (!this.isExecute) {
      this.refresh();
      this.initSortable();
    } else {
      await this.getTaskStageCanvasData();
    }
    this.refreshPluginIcon();
},
  methods: {
    ...mapMutations('template/', [
        'updatePipelineTree',
        'updateStageCanvasData',
      ]),
      ...mapMutations('stageCanvas/', [
        'setPluginsDetail',
      ]),
    addNewStage(index) {
      const newStage = getDefaultNewStage();
      this.stageCanvasData.splice(index + 1, 0,  newStage);
      this.refresh();
    },
    onUpdateNodeInfo() {
      // 外部依赖不能删
    },
    deletNode(index) {
      this.stageCanvasData.splice(index, 1);
      this.refresh();
    },
    handleCopyNode(stage, index) {
      const copyStage =  getCopyNode(stage);
      this.stageCanvasData.splice(index + 1, 0,  copyStage);
      this.refresh();
    },
    setActiveItem(node) {
      this.$store.commit('stageCanvas/setActiveNode', node);
    },
    cancelJobAndStageEidtSld() {
      this.setActiveItem(null);
    },
    hadEditedJobAndStage() {
      this.refresh();
    },
    handleNode(node) {
      this.$emit('onShowNodeConfig', node.id);
    },
    refresh() {
      const res = generatePplTreeByCurrentStageCanvasData(this.getPipelineTree);
      this.updatePipelineTree(res);
      this.$forceUpdate();
    },
    handleOperateNode(type, node) {
      this.$emit(type, node.id, node.type);
    },
    setRefreshTaskStageCanvasData(time = 2000) {
      this.isPolling = true;
      this.timer = setTimeout(async () => {
        await this.getTaskStageCanvasData();
      }, time);
    },
    cancelPoll() {
      this.isPolling = false;
      this.timer && clearTimeout(this.timer);
      this.timer = null;
    },

    getRunningNodeIds(stages) {
      return stages.reduce((res, stage) => {
        stage.jobs.forEach((job) => {
          res.push(...(job?.nodes.filter(node => node.state === ETaskStatusType.RUNNING || node.state === ETaskStatusType.ERROR) || []).map(node => this.taskNodeIdMap[node.id].id));
        });
        return res;
      }, []);
    },
    generateTaskNodeTemplateIdMap() {
      this.taskNodeIdMap = Object.values(this.activities).reduce((res, node) => {
        res[node.template_node_id] = node;
        return res;
      }, {});
    },
    async getTaskStageCanvasData() {
      const res = await this.getStageCanvasDataDetail().then(res => res.data);

      // 初始化任务节点映射map
      if (!this.taskNodeIdMap) this.generateTaskNodeTemplateIdMap();
      if (res) {
        this.updatePipelineTree({ stage_canvas_data: [...res] });
        const runningNodesIds = this.getRunningNodeIds(this.stageCanvasData);
        // 初始化变量收集
        if (!this.stageCanvasConstansSet) this.stageCanvasConstansSet = gatherStageCanvasConstans(this.stageCanvasData);
        const params = {
          to_render_constants: this.stageCanvasConstansSet,
          node_ids: runningNodesIds,
        };
        const constants = await this.getStageCanvasConstants(params).then(res => res.data.data);
        this.constants = [...constants];
      }
    },
    async refreshPluginIcon() {
      const plugins = cloneDeepWith(this.plugins);
      if (!plugins.uniform_api.length) delete plugins.uniform_api;
      if (!plugins.component.length) delete plugins.component;
      if (!plugins.blueking.length) delete plugins.blueking;
      if (plugins.uniform_api || plugins.component || plugins.blueking) {
        const params = {
          space_id: this.spaceId,
          template_id: this.templateId,
          ...plugins,
          target_fields: ['code', 'name', 'logo_url'],
        };
        const res = await this.getPluginDetail(params).then(res => res.data.data);
        this.setPluginsDetail(res);
      }
    },
    async getPluginDetail(params) {
      return await axios.post('/api/plugin/uniform_plugin_query/get_plugin_detail/', params);
    },
    async getStageCanvasDataDetail() {
      return await axios.get(`/task/get_stage_job_states/${this.instanceId}/?space_id=${this.spaceId}`);
    },
    async getStageCanvasConstants(params) {
      return await axios.post(`/task/rendered_stage_constants/${this.instanceId}/?space_id=${this.spaceId}`, params);
    },
    initSortable() {
      this.sortableInstance = new Sortable(this.$refs.stageContainer, {
          animation: 150,
          disabled: !this.editable,
          handle: '.stage-move-icon',
          onEnd: (evt) => {
            const { oldIndex, newIndex } = evt;
            this.stageCanvasData.splice(newIndex, 0, ...this.stageCanvasData.splice(oldIndex, 1));
            this.refresh();
          },
        });
    },
  },
 };
</script>
<style lang="scss" scoped>
.flowchart-container {
    height: calc(100% - 48px);
    min-width: 1000px; /* Ensure container has enough width */
    padding: 20px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    border-radius: 8px;
    background-color: #fff;
    .stage-container{
      display: flex;
      overflow-x: auto; /* Allow horizontal scrolling if needed */
      align-items: start;
      width: 100%;
      height: 100%;
    }
}
.isExecute{
  &.flowchart-container{
    height: 100%;
  }
}
</style>
