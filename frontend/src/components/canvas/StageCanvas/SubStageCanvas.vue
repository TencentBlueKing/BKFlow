<template>
  <stageCanvas
    v-if="templateId||instanceId"
    ref="subProcessCanvas"
    :editable="editable"
    :is-execute="isStageCanvasTaskExecute"
    :template-id="templateId"
    :instance-id="instanceId"
    :space-id="spaceId"
    :overall-state="overallState"
    :active-node="activeNode"
    :stage-canvas-data="stageCanvasData"
    :activities="activities"
    :plugins-detail="pluginsDetail"
    :get-pipeline-tree="pipelineTree"
    :if-show-step-tool="false"
    @updatePipelineTree="updatePipelineTree"
    @updateStageCanvasData="updateStageCanvasData"
    @setPluginsDetail="setPluginsDetail"
    @setActiveItem="setActiveItem"
    @handleNode="handleNode"
    @handleOperateNode="handleOperateNode" />
</template>
  <script lang="js">
  import stageCanvas from './index.vue';
  import axios from 'axios';
   export default {
    name: 'SubStageCanvas',
    components: {
      stageCanvas,
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
      pipelineTree: {
        type: Object,
        default: () => ({}),
      },
      isStageCanvasTaskExecute: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        activeNode: null,
        loadedTemplate: false,
        pluginsDetail: { component: {}, uniform_api: {}, blueking: {} },
      };
    },
    computed: {
      stageCanvasData() {
        return this.pipelineTree.stage_canvas_data || [];
      },
      activities() {
        return this.pipelineTree.activities || {};
      },
    },
    watch: {
       async templateId() {
        if (!this.instanceId) {
          const res = await this.getTemplateDetail();
          this.updatePipelineTree(res.data.data.pipeline_tree);
          this.loadedTemplate = true;
          this.$refs.subProcessCanvas.refresh();
        } else {
          this.$refs.subProcessCanvas.refreshPluginIcon();
        }
      },
      async instanceId() {
        if (this.instanceId) {
          this?.setRefreshTaskStageCanvasData();
        }
      },
    },
    methods: {
      updatePipelineTree(val) {
        Object.assign(this.pipelineTree, val);
      },
      updateStageCanvasData(val) {
        this.stageCanvasData = val;
      },
      setPluginsDetail(value) {
        Object.assign(this.pluginsDetail, value);
      },
      openStepNodeEdit(id) {
        this.$emit('onShowNodeConfig', id);
      },
      onUpdateNodeInfo() {
        // 外部依赖不能删
      },
      setActiveItem(node) {
        this.activeNode = node;
      },
      cancelJobAndStageEidtSld() {
        this.setActiveItem(null);
      },
      hadEditedJobAndStage() {
        this.refresh();
      },
      handleNode() {
        // this.$emit('onShowNodeConfig', node.id);
      },
      handleOperateNode(type, node) {
        this.$emit('onSubflowNodeClick', node.id);
      },
      setRefreshTaskStageCanvasData() {
        this.$refs.subProcessCanvas?.setRefreshTaskStageCanvasData();
      },
      async getTemplateDetail() {
        return await axios.get(`/api/template/${this.templateId}/`);
      },
    },
   };
  </script>
  <style lang="scss" scoped>
  </style>
