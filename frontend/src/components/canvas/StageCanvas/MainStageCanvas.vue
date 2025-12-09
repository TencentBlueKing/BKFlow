
<template>
  <div style="width: 100%;height: 100%;">
    <JobAndStageEidtSld
      :is-show.sync="isShowJobAndStageEdit"
      :init-data="activeNode"
      :editable="editable"
      @confirm="hadEditedJobAndStage"
      @cancel="cancelJobAndStageEidtSld" />
    <stageCanvas
      ref="processCanvas"
      :editable="editable"
      :is-execute="isExecute"
      :template-id="templateId"
      :instance-id="instanceId"
      :space-id="spaceId"
      :overall-state="overallState"
      :active-node="activeNode"
      :stage-canvas-data="stageCanvasData"
      :activities="activities"
      :get-pipeline-tree="getPipelineTree"
      :plugins-detail="pluginsDetail"
      @updatePipelineTree="updatePipelineTree"
      @updateStageCanvasData="updateStageCanvasData"
      @setPluginsDetail="setPluginsDetail"
      @setActiveNode="setActiveNode"
      @handleNode="handleNode"
      @handleOperateNode="handleOperateNode" />
  </div>
</template>
  <script lang="js">

  import { mapGetters, mapMutations, mapState } from 'vuex';
  import stageCanvas from './index.vue';
  import JobAndStageEidtSld from './components/JobAndStageEditSld/index.vue';
   export default {
    name: 'MainStageCanvas',
    components: {
      stageCanvas,
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
        isShowJobAndStageEdit: false,
      };
    },
    computed: {
      ...mapState({
          activeNode: state => state.stageCanvas.activeNode,
          stageCanvasData: state => state.template.stage_canvas_data,
          activities: state => state.template.activities,
          pluginsDetail: state => state.stageCanvas.pluginsDetail,
        }),
        ...mapGetters('template/', [
          'getPipelineTree',
        ]),
    },
    watch: {
      overallState: {
        handler(value) {
          if (window.parent) {
            window.parent.postMessage({ eventName: 'bk-flow-task-state-change', state: value }, '*');
          }
        },
      },
      activeNode: {
        handler(value) {
          if (value) {
            this.isShowJobAndStageEdit = true;
          }
        },
      },
    },
    methods: {
      ...mapMutations('template/', [
        'updatePipelineTree',
        'updateStageCanvasData',
      ]),
      ...mapMutations('stageCanvas/', [
        'setPluginsDetail',
      ]),
      openStepNodeEdit(id) {
        this.$emit('onShowNodeConfig', id);
      },
      onUpdateNodeInfo() {
        // 外部依赖不能删
      },
      setActiveNode(node) {
        this.$store.commit('stageCanvas/setActiveNode', node);
      },
      cancelJobAndStageEidtSld() {
        this.isShowJobAndStageEdit = false;
        this.setActiveNode(null);
      },
      hadEditedJobAndStage() {
        this.refresh();
      },
      handleNode(node) {
        this.$emit('onShowNodeConfig', node.id);
      },
      handleOperateNode(type, node) {
        this.$emit(type, node.id, node.type);
      },
      refresh() {
        this.$refs.processCanvas.refresh();
      },
      setRefreshTaskStageCanvasData() {
        this.$refs.processCanvas.setRefreshTaskStageCanvasData();
      },
    },
   };
  </script>
  <style lang="scss" scoped>

  </style>
