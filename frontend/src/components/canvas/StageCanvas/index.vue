
<template>
  <div class="flowchart-container ">
    <JobAndStageEidtSld
      :is-show.sync="isShowJobAndStageEdit"
      :init-data="activeNode"
      @cancel="cancelJobAndStageEidtSld" />
    <StageNode
      v-for="(stage,index) in stageCanvasData"
      :key="stage.id"
      :stage="stage"
      :stages="stageCanvasData"
      :index="(index+1).toString()"
      @deleteNode="deletNode(index)"
      @addNewStage="addNewStage(index)"
      @refreshPPLT="refresh"
      @editNode="editNode"
      @copyNode="handleCopyNode(stage,index)" />
  </div>
</template>
<script lang="js">

import StageNode from './components/StageNode.vue';

import {  getDefaultNewStage, stage } from './data';
import { generatePplTreeByCurrentStageCanvasData, getCopyNode } from './utils';
import JobAndStageEidtSld from './components/JobAndStageEditSld/index.vue';
import { mapGetters, mapMutations, mapState } from 'vuex';

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
  },

  data() {
    return {
        stageData: [...stage],
        activeItem: null,
        isShowJobAndStageEdit: false,
      };
    },
  computed: {
    ...mapState({
        activeNode: state => state.stageCanvas.activeNode,
        stageCanvasData: state => state.template.stage_canvas_data,

      }),
      ...mapGetters('template/', [
        'getPipelineTree',
      ]),
  },
  watch: {
    activeNode: {
      handler(value) {
        if (value) {
          console.log('index.vue_Line:54', value);
          this.isShowJobAndStageEdit = true;
        }
      },
    },
  },
  mounted() {
    console.log('index.vue_Line:87', this.getPipelineTree);
    this.refresh();
},
  methods: {
    ...mapMutations('template/', [
        'updatePipelineTree',
      ]),
    addNewStage(index) {
      const newStage = getDefaultNewStage();
      this.stageCanvasData.splice(index + 1, 0,  newStage);
    },
    deletNode(index) {
      console.log('index.vue_Line:45', index);
      this.stageCanvasData.splice(index, 1);
    },
    handleCopyNode(stage, index) {
      const copyStage =  getCopyNode(stage);
      this.stageCanvasData.splice(index + 1, 0,  copyStage);
    },
    setActiveItem(node) {
      this.$store.commit('stageCanvas/setActiveNode', node);
    },
    cancelJobAndStageEidtSld() {
      this.setActiveItem(null);
    },
    editNode(node) {
      this.$emit('onShowNodeConfig', node.id);
    },
    onUpdateNodeInfo() {

    },
    refresh() {
      const res = generatePplTreeByCurrentStageCanvasData(this.getPipelineTree);
      this.updatePipelineTree(res);
      console.log('index.vue_Line:71', res);
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
