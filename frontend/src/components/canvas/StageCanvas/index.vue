
<template>
  <div class="flowchart-container">
    <StageNode
      v-for="(stage,index) in stageData"
      :key="stage.id"
      :stage="stage"
      :stages="stageData"
      :index="(index+1).toString()"
      @deleteNode="deletNode(index)"
      @addNewStage="addNewStage(index)"
      @copyNode="handleCopyNode(stage,index)" />
  </div>
</template>
<script lang="js">

import StageNode from './components/StageNode.vue';

import {  getDefaultNewStage, stage } from './data';
import { getCopyNode } from './utils';

 export default {
  name: 'StageCanvas',
  components: {

    StageNode,
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

      };
    },
  methods: {
    addNewStage(index) {
      const newStage = getDefaultNewStage();
      this.stageData.splice(index + 1, 0,  newStage);
    },
    deletNode(index) {
      console.log('index.vue_Line:45', index);
      this.stageData.splice(index, 1);
    },
    handleCopyNode(stage, index) {
      const copyStage =  getCopyNode(stage);
      this.stageData.splice(index + 1, 0,  copyStage);
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
    height: 100%;
    align-items: start;

}

</style>
<style>
*{
  --primary-color:#3A83FF
}
.wordElliptic{
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

</style>
