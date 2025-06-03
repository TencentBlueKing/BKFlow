<template>
  <div
    class="stage"
    :class="{ active: activeNode?.type === 'Stage' && activeNode?.id === stage.id }">
    <div
      class="stage-header"
      @click="setActiveItem(stage)">
      <h3>
        <span class="stage-number">{{ index }}</span>
        <div class="header-right">
          <span
            v-if="activeNode && activeNode.type === 'Stage' && activeNode.id === stage.id"
            class="editing-text">编辑中...</span>
          <span
            v-else
            class="word-elliptic node-name">{{ stage.name || '新Stage' }}</span>
          <div class="tools">
            <div
              v-for="item in toolIconArr.filter(item=>!item.disabled||!item.disabled())"
              :key="item.name"
              v-bk-tooltips="{
                content: item.name,
              }"
              :class="`icon-btn ${item.icon}`"
              @click.stop="item.handleClick" />
          </div>
        </div>
      </h3>
      <div

        class="stage-status">
        <div
          v-for="item in transformNodeConfigToRenderItems(stage)"
          :key="item.key"
          class="stage-status-item">
          <ValueRender :render-item="item" />
        </div>
      </div>
    </div>
    <div class="stage-jobs">
      <JobNode
        v-for="(job,jobIndex) in stage.jobs"
        :key="job.id"
        :job="job"
        :jobs="stage.jobs"
        :index="`${index}.${jobIndex + 1}`"
        @deleteNode="deletJobNode(jobIndex)"
        @editNode="editNode"
        @addNewJob="addNewJob(jobIndex)"
        @refreshPPLT="refreshPPLT"
        @copyNode="handleCopyJobNode(job,jobIndex)" />
    </div>
    <div class="add-stage-btn">
      <div
        class="cicrleBtn"
        @click="addNewStage">
        <span>+</span>
      </div>
    </div>
  </div>
</template>
<script>
import JobNode from './JobNode.vue';
import { mapState } from 'vuex';
import ValueRender from './valueRender.vue';
import { getCopyNode, transformNodeConfigToRenderItems } from '../utils';
import { getDefaultNewJob } from '../data';
 export default {
    components: {
      JobNode,
      ValueRender,
    },
    props: {
        stage: {
            type: Object,
            required: true,
        },
        index: {
          type: String,
          default: '',
        },
        stages: {
          type: Array,
          default: () => [],
        },
    },
    data() {
      return {
            toolIconArr: [
              {
                icon: 'commonicon-icon common-icon-double-paper-2',
                name: '复制',
                handleClick: () => {
                  this.$emit('copyNode', this.stage);
                },
              },
              {
                icon: 'commonicon-icon common-icon-bkflow-delete',
                name: '删除',
                handleClick: () => {
                  console.log('StageNode.vue_Line:85', 1);
                  this.$emit('deleteNode',  this.stage);
                },
                disabled: () => this.stages.length <= 1,
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
        setTimeout(() => {
          console.log('index.vue_Line:177', this.activeNode);
        }, 100);
      },
      addNewStage() {
        this.$emit('addNewStage');
      },
      addNewJob(index) {
        const newStage = getDefaultNewJob();
        console.log('StageNode.vue_Line:127', this.jobs);
        this.stage.jobs.splice(index + 1, 0,  newStage);
        this.refreshPPLT();
      },
      deletJobNode(index) {
        console.log('index.vue_Line:45', index);
        console.log('StageNode.vue_Line:127', this.stage);
        this.stage.jobs.splice(index, 1);
        this.refreshPPLT();
      },
      handleCopyJobNode(stage, index) {
        const copyStage =  getCopyNode(stage);
        this.stage.jobs.splice(index + 1, 0,  copyStage);
        this.refreshPPLT();
      },
      editNode(node) {
          this.$emit('editNode', node);
        },
        refreshPPLT() {
          this.$emit('refreshPPLT');
        },
    },

 };
</script>
<style lang="scss" scoped>
.stage {
      // 箭头长短变量，方便统一维护箭头样式
      $arrowWidth:56px;
      margin-right: $arrowWidth + 4px;
      width: 280px; /* 根据设计稿指定宽度 */
      min-width: 280px; /* 确保最小宽度 */
      background-color: #fff;

      border-radius: 2px; /* 根据设计稿更新圆角 */
      display: flex;
      flex-direction: column;
      position: relative;
      border: 1px solid #D4E8FF;
      &.active{
        border: 1px solid #3A83FF; /* 根据设计稿更新边框颜色 */
      }
      /* Arrow connector between stages */
      &:not(:last-child)::after {
          content: '';
          position: absolute;
          right: -$arrowWidth;
          top: 24px;
          width: $arrowWidth;
          height: 2px;
          background-color: #3A83FF; /* 更新为指定蓝色 */
          z-index: 1;
      }
      &:not(:last-child)::before {
          content: '';
          position: absolute;
          right: -$arrowWidth - 4px;
          top: calc(24px - 3px);
          width: 0;
          height: 0;
          border-top: 4px solid transparent;
          border-bottom: 4px solid transparent;
          border-left: 4px solid #3A83FF; /* 更新为指定蓝色 */
          z-index: 1;
      }
      &:hover{
        .cicrleBtn{
          display: flex;
        }
        .tools{
          display: flex;
        }
      }

}
.cicrleBtn{
  display: none;
  $circleRadius:7px;
  width: $circleRadius *2;
  height:  $circleRadius *2;
  border-radius: 50%;
  color: #fff;
  background-color: #4b4d55;
  align-items: center;
  justify-content: center;
  position: absolute;
  right: 0 - $circleRadius;
  top: 24 - $circleRadius;
  z-index: 10;
  line-height: 2 * $circleRadius;
  font-size: 12px;
  span{
    position: relative;
    top: -0.5px;
    cursor: pointer;
  }
}
.stage-header {
    margin-bottom: 0;
    padding: 12px;
    background-color: #E1ECFF; /* 根据设计稿更新背景色 */
    border-bottom: 1px solid #D4E8FF; /* 更新边框颜色 */
    border-radius: 2px 2px 0 0; /* 根据设计稿设置圆角 */
    box-sizing: border-box;
    cursor: pointer; /* 添加鼠标指针样式 */
    transition: background-color 0.2s;
    border: 1px solid #3A83FF00;
}
.stage-header:hover {
    background-color: #D4E8FF; /* 悬停时略微变深 */
}
.stage-header h3 {
    margin: 0 0 10px 0;
    font-size: 18px;
    line-height: 1;
    color: #333;
    font-weight: 500;
    display: flex;
    align-items: center;
}
.header-right{
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 1;
  .node-name{
    max-width: 180px;
  }
}
.stage-header h3 span.stage-number {
    display: inline-block;
    width: 24px;
    height: 24px;
    background-color: #3A83FF;
    color: white;
    border-radius: 50%;
    text-align: center;
    line-height: 24px;
    margin-right: 8px;
    font-size: 14px;
}
.stage-status {
    font-size: 12px;
    color: #666;
    display: flex;
    flex-direction: column;
    gap: 3px;
}
.stage-jobs {
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 0;
    overflow-y: auto;
}

.tools{
  display: none;
  align-items: center;
  font-size: 12px;
  justify-content: center;
  align-items: center;
  .icon-btn{
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }
}
.word-elliptic{
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
