
<template>
  <div
    class="flowchart-container "
    :class="{
      isPreview:!editable
    }">
    <JobAndStageEidtSld
      :is-show.sync="isShowJobAndStageEdit"
      :init-data="activeNode"
      :editable="editable"
      @cancel="cancelJobAndStageEidtSld" />
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
</template>
<script lang="js">

import StageNode from './components/StageNode.vue';

import {  getDefaultNewStage, stage } from './data';
import { generatePplTreeByCurrentStageCanvasData, getCopyNode } from './utils';
import JobAndStageEidtSld from './components/JobAndStageEditSld/index.vue';
import { mapGetters, mapMutations, mapState } from 'vuex';
import axios from 'axios';
import { cloneDeepWith } from 'lodash';

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
  },

  data() {
    return {
        stageData: [...stage],
        activeItem: null,
        isShowJobAndStageEdit: false,
        constants: [
          {
            key: '${value}',
            value: 10,
          },
        ],
        timer: null,
        isPolling: false,
        debounceTimer: null,
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
  },
  mounted() {
    if (!this.isExecute) {
      this.refresh();
    } else {
      this.getTaskStageCanvasData();
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
    handleNode(node) {
      this.$emit('onShowNodeConfig', node.id);
    },
    onUpdateNodeInfo() {

    },
    refresh() {
      const res = generatePplTreeByCurrentStageCanvasData(this.getPipelineTree);
      this.updatePipelineTree(res);
      this.$forceUpdate();
    },
    handleOperateNode(type, node) {
      this.$emit(type, node.id);
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
    async getTaskStageCanvasData() {
      const res = await this.getStageCanvasDataDetail().then(res => res.data);
      if (res.pipeline_tree) {
        this.updateStageCanvasData(res.pipeline_tree.stage_canvas_data);
        this.constants = res.pipeline_tree.current_constants || [];
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
  },
 };
</script>
<style lang="scss" scoped>
.flowchart-container {
    display: flex;
    overflow-x: auto; /* Allow horizontal scrolling if needed */
    padding: 20px;
    background-color: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    min-width: 1000px; /* Ensure container has enough width */
    height: calc(100% - 48px);
    align-items: start;
}
</style>
