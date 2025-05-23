<template>
  <div class="job">
    <div class="job-header">
      <div class="job-id">
        {{ index }}
      </div>
      <div
        class="job-title"
        :class="{ active: activeNode && activeNode.type === 'job' && activeNode.id === job.id }"
        @click="setActiveItem(job)">
        <div class="headerRight">
          <span
            v-if="activeNode && activeNode.type === 'job' && activeNode.id === job.id"
            class="editing-text">编辑中...</span>
          <span
            v-else
            class="nodeName wordElliptic">{{ job.name || '新Job' }}</span>
          <div class="tools">
            <div
              v-for="item in toolIconArr.filter(item=>!item.disabled||!item.disabled())"
              :key="item.name"
              v-bk-tooltips="{
                content: item.name,
              }"
              :class="`iconBtn ${item.icon}`"
              @click.stop="item.handleClick" />
          </div>
        </div>
      </div>
    </div>
    <div class="job-content">
      <div class="job-status">
        <div
          v-for="item in transformNodeConfigToRenderItems(job)"
          :key="item.key"
          class="job-status-item">
          <ValueRender :render-item="item" />
        </div>
      </div>
      <div class="job-nodes">
        <template>
          <StepNode
            v-for="(node,nodeIndex) in job.nodes"
            :key="node.id"
            :node="node"
            :nodes="job.nodes"
            @deleteNode="deletStepNode(nodeIndex)"
            @addNewStep="addNewStep(nodeIndex)"
            @copyNode="handleCopyStepNode(node,nodeIndex)" />
        </template>
      </div>
    </div>
    <div class="addJobBtn">
      <div
        class="cicrleBtn"
        @click="addJob">
        <span>+</span>
      </div>
    </div>
  </div>
</template>
<script>
import { mapState } from 'vuex';
import { getCopyNode, transformNodeConfigToRenderItems } from '../utils';
import ValueRender from './valueRender.vue';
import StepNode from './StepNode.vue';
import { getDefaultNewStep } from '../data';
export default {
    components: {
        ValueRender,
        StepNode,
    },
    props: {
        job: {
            type: Object,
            required: true,
        },
        index: {
          type: String,
          default: '',
        },
        jobs: {
          type: Array,
          default: () => ([]),
        },

    },
    data() {
        return {
          toolIconArr: [
              {
                icon: 'commonicon-icon common-icon-double-paper-2',
                name: '复制',
                handleClick: () => {
                  this.$emit('copyNode', this.job);
                },
              },
              {
                icon: 'commonicon-icon common-icon-bkflow-delete',
                name: '删除',
                handleClick: () => {
                  console.log('StageNode.vue_Line:85', 1);
                  this.$emit('deleteNode', this.job);
                },
                disabled: () => this.jobs.length <= 1,
              },
            ],
        };
      },
    computed: {
      ...mapState({
        activeNode: state => state.stageCanvas.activeNode,
      }),
    },
    methods: {
        transformNodeConfigToRenderItems,
        setActiveItem(node) {
          this.$store.commit('stageCanvas/setActiveNode', node);
        },
        addJob() {
          this.$emit('addNewJob');
        },
        addNewStep(index) {
          const newStage = getDefaultNewStep();

          this.job.nodes.splice(index + 1, 0,  newStage);
        },
        deletStepNode(index) {
          this.job.nodes.splice(index, 1);
        },
        handleCopyStepNode(step, index) {
          const copyStage =  getCopyNode(step);
          this.job.nodes.splice(index + 1, 0,  copyStage);
        },
    },
};
</script>
<style lang="scss" scoped>
.job {
    background-color: transparent; /* 移除整体背景色 */
    border-bottom: 1px solid #D4E8FF;
    border-radius: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    box-shadow: none;
    margin-bottom: 12px;
    position: relative;
    &:hover{
      .tools{
        display: flex;
      }
      .cicrleBtn{
        display: flex;
      }
    }

}
.job:last-child {
    border-bottom: none;
    margin-bottom: 0;
}
.job-header {
    display: flex;
    width: 100%;

}
.job-header .job-id {
    width: 60px;
    background-color: #4A90E2; /* u84ddu8272u80ccu666f */
    color: white;
    font-weight: 500;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.1em;
    height: 42px; /* u6dfbu52a0u56fau5b9au9ad8u5ea6 */
}
.job-header .job-title {
    flex: 1;
    background-color: #191929; /* u6df1u8272u80ccu666f */
    color: white;
    font-weight: 500;
    display: flex;
    align-items: center;
    padding: 0 12px;
    font-size: 1em;
    height: 42px; /* u6dfbu52a0u56fau5b9au9ad8u5ea6 */
    cursor: pointer; /* 添加鼠标指针样式 */
    transition: background-color 0.2s;
}
.job-header .job-title:hover {
    background-color: #22222f; /* 悬停效果 */
}
.job-header .job-title.active {
    background-color: #323248; /* 激活状态 */
    border-left: 2px solid #4A90E2; /* 添加左侧边框标记 */
}
.job-content {
    padding: 16px 12px;
    position: relative;
    background-color: #F5F7FA; /* 内容区域使用浅灰色背景 */
}
.job-status {
    font-size: 0.9em;
    color: #666;
    margin-bottom: 12px;
    padding: 12px;
    background-color: #EDF2F7; /* 稍深的背景色 */
    margin: -12px -12px 12px -12px; /* 抵消父元素的内边距 */
    border-bottom: 1px solid #E4EBF5; /* 添加分隔线 */
}
.job-status-item {
    margin-bottom: 8px;
    line-height: 1.5;
}
.job-nodes {
    display: flex;
    flex-direction: column;
    gap: 10px; /* Space between nodes */
    margin-top: 5px;
}
.headerRight{
  display: flex;
  flex: 1;
  justify-content: space-between;
  .nodeName{
    max-width: 110px;
  }
}
.tools{
  display: none;
  align-items: center;
  font-size: 12px;
  justify-content: center;
  align-items: center;
  .iconBtn{
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }
}
.addJobBtn{
  .cicrleBtn{
    display: none;
    $circleRadius:7px;
    width: $circleRadius *2;
    height:  $circleRadius *2;
    border-radius: 50%;
    color: #fff;
    background-color: var(--primary-color);
    align-items: center;
    justify-content: center;
    position: absolute;
    bottom: 0 - $circleRadius;
    left: 50%;
    transform: translateX(-$circleRadius);
    z-index: 10;
    line-height: 2 * $circleRadius;
    font-size: 12px;
    span{
      position: relative;
      top: -0.5px;
      cursor: pointer;
    }
  }
}
</style>
