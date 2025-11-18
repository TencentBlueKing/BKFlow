<template>
  <div
    class="stage"
    :class="{ active: activeNode?.id === stage.id ,
              isPreview:!editable,
              isExecute,[ETaskStatusTypeMap[status].class]:true} ">
    <div
      class="stage-header"
      @click="setActiveItem(stage)">
      <h3>
        <span
          v-if="editable"
          class="stage-move-icon commonicon-icon common-icon-drawable" />
        <span
          v-if="!isExecute||(status === ETaskStatusType.PENDING)"
          class="stage-number">
          <span>{{ index }}.</span>
        </span>
        <span v-else>
          <i :class="`${ETaskStatusIconMap[status]}`" />
        </span>
        <div class="header-right">
          <span
            v-if="activeNode?.id === stage.id&&editable"
            class="editing-text">编辑中...</span>
          <span
            v-else
            v-bk-tooltips="{
              disabled:!stage.name,
              content: stage.name,
            }"
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
          v-for="item in transformNodeConfigToRenderItems(stage,constants)"
          :key="item.key"
          class="stage-status-item">
          <ValueRender :render-item="item" />
        </div>
      </div>
    </div>
    <div
      ref="jobContainer"
      class="stage-jobs">
      <JobNode
        v-for="(job,jobIndex) in stage.jobs"
        :key="job.id"
        :job="job"
        :jobs="stage.jobs"
        :is-execute="isExecute"
        :constants="constants"
        :index="`${index}.${jobIndex + 1}`"
        :editable="editable"
        :show-not-allow-move="notAllowMoveIndex === jobIndex"
        @deleteNode="deletJobNode(jobIndex)"
        @handleNode="handleNode"
        @addNewJob="addNewJob(jobIndex)"
        @handleOperateNode="handleOperateNode"
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
import { getDefaultNewJob, ETaskStatusType, ETaskStatusTypeMap } from '../data';
import Sortable from 'sortablejs';

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
        editable: {
          type: Boolean,
          default: false,
        },
        isExecute: {
          type: Boolean,
          default: false,
        },
        constants: {
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
                  this.$emit('copyNode', this.stage);
                },
              },
              {
                icon: 'commonicon-icon common-icon-bkflow-delete',
                name: '删除',
                handleClick: () => {
                  this.$emit('deleteNode',  this.stage);
                },
                disabled: () => this.stages.length <= 1,
              },
            ],
            ETaskStatusType,
            ETaskStatusTypeMap,
            ETaskStatusIconMap: {
              [ETaskStatusType.ERROR]: 'iconCirle commonicon-icon common-icon-close',
              [ETaskStatusType.SUCCESS]: 'iconCirle commonicon-icon common-icon-done-thin',
              [ETaskStatusType.RUNNING]: 'rotateAnimate commonicon-icon common-icon-loading-ring',
              [ETaskStatusType.PENDING]: '',
            },
            sortableInstance: null,
            notAllowMoveIndex: null,
          };
      },
    computed: {
      ...mapState({
        activeNode: state => state.stageCanvas.activeNode,
      }),
      status() {
        return this.stage.state || ETaskStatusType.PENDING;
      },
    },
    watch: {
      editable: {
        handler(value) {
          this.sortableInstance.option('disabled', !value);
        },
      },
    },
    mounted() {
      if (!this.isExecute) {
        this.initSortable();
      }
      this.$refs.jobContainer.jobs = this.stage.jobs;
    },
    methods: {
      transformNodeConfigToRenderItems,
      setActiveItem(node) {
        this.$store.commit('stageCanvas/setActiveNode', node);
      },
      addNewStage() {
        this.$emit('addNewStage');
      },
      addNewJob(index) {
        const newStage = getDefaultNewJob();
        this.stage.jobs.splice(index + 1, 0,  newStage);
        this.$set(this.stage, 'jobs', this.stage.jobs);
        this.refreshPPLT();
      },
      deletJobNode(index) {
        this.stage.jobs.splice(index, 1);
        this.refreshPPLT();
      },
      handleCopyJobNode(stage, index) {
        const copyStage =  getCopyNode(stage);
        this.stage.jobs.splice(index + 1, 0,  copyStage);
        this.refreshPPLT();
      },
      handleNode(node) {
          this.$emit('handleNode', node);
        },
        refreshPPLT() {
          this.$emit('refreshPPLT');
          this.$forceUpdate();
        },
      handleOperateNode(type, node) {
        this.$emit('handleOperateNode', type, node);
      },
      initSortable() {
        this.sortableInstance = new Sortable(this.$refs.jobContainer, {
            animation: 150,
            disabled: !this.editable,
            group: 'jobs',
            handle: '.job-move-icon',
            onStart: (evt) => {
              if (this.stage.jobs.length <= 1) {
                this.notAllowMoveIndex = evt.oldIndex;
              }
            },
            onEnd: (evt) => {
              this.notAllowMoveIndex = null;
              const { oldIndex, newIndex, to, from } = evt;
              if (from.jobs.length > 1) {
                to.jobs.splice(newIndex, 0, ...from.jobs.splice(oldIndex, 1));
                this.refreshPPLT();
              }
              this.$nextTick(() => {
                this.$forceUpdate();
              });
            },
            onMove: () => {
              if (this.stage.jobs.length <= 1) {
                return false;
              }
            },
          });
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
      border: 1px solid #0052d933;
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
        .stage-move-icon{
          display: inline-block;
        }
      }
      .stage-header {
          margin-bottom: 0;
          padding: 12px 18px;
          background-color: #e8eefa; /* 根据设计稿更新背景色 */
          border-bottom: 1px solid #D4E8FF; /* 更新边框颜色 */
          border-radius: 2px 2px 0 0; /* 根据设计稿设置圆角 */
          box-sizing: border-box;
          cursor: pointer; /* 添加鼠标指针样式 */
          transition: background-color 0.2s;
          border: 1px solid #3A83FF00;
          font-weight: 700;
          color: #313238;
          &:hover {
              background-color: #D4E8FF; /* 悬停时略微变深 */
          }
          h3 {
              margin: 0 0 10px 0;
              font-size: 16px;
              line-height: 1;
              display: flex;
              align-items: center;
              span.stage-number {
                  display: inline-block;
                  color: #313238;
              }
          }
          .header-right{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex: 1;
            font-size: 16px;
            .node-name{
              max-width: 180px;
              line-height: 1.5;
            }
            .editing-text{
              line-height: 1.5;
            }
          }
      }
      .stage-move-icon{
        display: none;
        margin-left: -8px;
        font-size: 18px;
        color: #4D4F56;
        cursor: move;
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


.stage-status {
    font-size: 12px;
    color: #666;
    display: flex;
    flex-direction: column;
    gap: 3px;
    .stage-status-item{
      padding-right: 2px;
    }
}
.stage-jobs {
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 0;
    overflow-y: none;
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

.isPreview{
  .add-stage-btn{
    display: none;
  }
  .stage-header{
    .tools{
      display: none;
    }
  }
}
.isExecute{
  &.stage{
    &.error{
      border: 1px solid #FFD4D4;
      .stage-header{
        background-color: #fceef1;
      }
    }
    &.success{
      border: 1px solid #D4E8FF;
      .stage-header{
        background-color: #e8eefa;
      }
    }
    &.running{
      border: 1px solid #D4E8FF;
      .stage-header{
        background-color: #e8eefa;
      }
    }
    &.pending{
      border: 1px solid #E4E7EB;
      .stage-header{
        background-color: #eef3f8;
      }
    }
  }
}
.iconCirle{
  font-size: 6px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  color: #fff;
  margin-right: 8px;
}
.success{
  .iconCirle{
    background-color: #2050d2;
  }
}
.error{
  .iconCirle{
    background-color: #eb517b;
  }
}
.rotateAnimate{
  font-size: 14px;
  margin-right: 8px;
  transform-origin: center;
  color: #459bd0;
  animation: roate 1s linear infinite;
  transform: scale(2);
  display: flex;
  align-content: center;
  justify-content: center;
}
@keyframes roate {
  0%{
    transform: rotate(0) scale(2);
  }
  50%{
    transform: rotate(180deg) scale(2);
  }
  100%{
    transform: rotate(360deg) scale(2);
  }
}
</style>
