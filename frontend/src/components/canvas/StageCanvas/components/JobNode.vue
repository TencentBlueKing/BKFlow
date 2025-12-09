<template>
  <div
    class="job"
    :class="{ active: activeNode?.id === job.id, isPreview:!editable , isExecute,[ETaskStatusTypeMap[status].class]:true}">
    <div class="job-header">
      <div class="job-id">
        <span
          v-if="editable"
          class="job-move-icon commonicon-icon common-icon-drawable" />
        <span v-if="!isExecute||(status===ETaskStatusType.PENDING)">{{ index }}</span>
        <span
          v-else
          style="display: inline-block;">
          <i :class="`${ETaskStatusIconMap[status]}`" />
        </span>
      </div>
      <div
        class="job-title"
        :class="{ active: activeNode?.id === job.id }"
        @click="setActiveItem(job)">
        <div class="header-right">
          <span
            v-if=" activeNode?.id === job.id && editable"
            class="editing-text">编辑中...</span>
          <span
            v-else
            v-bk-tooltips="{
              disabled:!job.name,
              content: job.name,
            }"
            class="node-name word-elliptic">{{ job.name || '新Job' }}</span>
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
      </div>
    </div>
    <div class="job-content">
      <div
        v-if="job.config.length"
        class="job-status">
        <div
          v-for="item in transformNodeConfigToRenderItems(job,constants)"
          :key="item.key"
          class="job-status-item">
          <ValueRender :render-item="item" />
        </div>
      </div>
      <div
        ref="nodeContainer"
        class="job-nodes">
        <StepNode
          v-for="(node,nodeIndex) in job.nodes"
          :key="node.id"
          :node="node"
          :nodes="job.nodes"
          :plugins-detail="pluginsDetail"
          :editable="editable"
          :show-not-allow-move="notAllowMoveIndex === nodeIndex"
          :is-execute="isExecute"
          :activities="activities"
          :if-show-step-tool="ifShowStepTool"
          @deleteNode="deletStepNode(nodeIndex)"
          @handleNode="handleNode"
          @addNewStep="(type)=>addNewStep(nodeIndex,type)"
          @handleOperateNode="handleOperateNode"
          @copyNode="handleCopyStepNode(node,nodeIndex)" />
      </div>
    </div>
    <div class="add-job-btn">
      <div
        class="cicrle-btn"
        @click="addJob">
        <span>+</span>
      </div>
    </div>
    <div
      v-if="showNotAllowMove"
      class="no-allow-move">
      <bk-exception
        class="exception-wrap-item exception-part"
        type="500"
        scene="part">
        <span class="info-text">仅有一个Job时，不可移动</span>
      </bk-exception>
    </div>
  </div>
</template>
<script>
import { copyStepNode, transformNodeConfigToRenderItems } from '../utils';
import ValueRender from './valueRender.vue';
import StepNode from './StepNode.vue';
import { getDefaultNewStep, ETaskStatusType, ETaskStatusTypeMap } from '../data';
import Sortable from 'sortablejs';
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
        showNotAllowMove: {
          type: Boolean,
          default: false,
        },
        pluginsDetail: {
          type: Object,
          default: () => ({}),
        },
        activities: {
          type: Object,
          default: () => ({}),
        },
        activeNode: {
          type: Object,
          default: null,
        },
        ifShowStepTool: {
          type: Boolean,
          default: true,
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
                  this.$emit('deleteNode', this.job);
                },
                disabled: () => this.jobs.length <= 1,
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
          notAllowMoveIndex: null,
        };
      },
    computed: {
      status() {
        return this.job.state || ETaskStatusType.PENDING;
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
      this.$refs.nodeContainer.nodes = this.job.nodes;
    },
    methods: {
        transformNodeConfigToRenderItems,
        setActiveItem(node) {
          this.$emit('setActiveNode', node);
        },
        addJob() {
          this.$emit('addNewJob');
        },
        addNewStep(index, type = 'Node') {
          const newStage = getDefaultNewStep(type);
          this.job.nodes.splice(index + 1, 0,  newStage);
          this.refreshPPLT();
        },
        deletStepNode(index) {
          this.job.nodes.splice(index, 1);
          this.refreshPPLT();
        },
        handleCopyStepNode(step, index) {
          const copyStage =  copyStepNode(step);
          this.job.nodes.splice(index + 1, 0,  copyStage);
          this.refreshPPLT();
        },
        handleNode(node) {
          this.$emit('handleNode', node);
        },
        refreshPPLT() {
          this.$emit('refreshPPLT');
        },
        handleOperateNode(type, node) {
          this.$emit('handleOperateNode', type, node);
        },
        initSortable() {
          this.sortableInstance = new Sortable(this.$refs.nodeContainer, {
            animation: 150,
            disabled: !this.editable,
            group: 'nodes',
            handle: '.node-move-icon',
            onStart: (evt) => {
              if (this.job.nodes.length <= 1) {
                this.notAllowMoveIndex = evt.oldIndex;
              }
            },
            onEnd: (evt) => {
              this.notAllowMoveIndex = null;
              const { oldIndex, newIndex, to, from } = evt;
              if (from.nodes.length > 1) {
                to.nodes.splice(newIndex, 0, ...from.nodes.splice(oldIndex, 1));
                this.refreshPPLT();
              }
              this.$nextTick(() => {
                this.$forceUpdate();
              });
            },
            onMove: () => {
              if (this.job.nodes.length <= 1) {
                return false;
              }
            },
          });
        },
    },
};
</script>
<style lang="scss" scoped>
.job {
    background-color: transparent; /* 移除整体背景色 */
    border: 1px solid transparent;
    border-radius: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    box-shadow: none;
    margin-bottom: 12px;
    position: relative;
    border-radius: 2px;
    &:hover{
      .tools{
        display: flex;
      }
      .cicrle-btn{
        display: flex;
      }
      .job-move-icon{
        display: inline-block;
      }
    }
    &.active {
      border: 1px solid #2050d2; /* 添加左侧边框标记 */
    }
    &:last-child {
      margin-bottom: 0;
    }
    .job-move-icon{
      margin-left: -4px;
      font-size: 18px;
      margin-right: 4px;
      cursor: move;
      display: none;
    }
    .no-allow-move{
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      border: 2px dashed #F8B4B4;
      border-spacing: 5px;
      background: #FDF0F0;
      display: flex;
      align-items: center;
      .info-text{
        color: #EA3636;
      }
    }
    &:deep(.bk-exception){
      height: 100%;
    }
    &:deep(.bk-exception-img.part-img .exception-image){
      height: 64px;
    }
}

.job-header {
    display: flex;
    width: 100%;
    font-size: 14px;
    .job-id {
      background-color: #2050d2;
      color: white;
      font-weight: 500;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0 12px;
     }
    .job-title {
      flex: 1;
      background-color: #191929;
      color: white;
      font-weight: 500;
      display: flex;
      align-items: center;
      padding: 0 12px;
      height: 42px;
      cursor: pointer; /* 添加鼠标指针样式 */
      transition: background-color 0.2s;
      .header-right{
        display: flex;
        flex: 1;
        justify-content: space-between;
        font-size: 16px;
        .node-name{
          max-width: 110px;
        }
      }
      &:hover {
          background-color: #22222f; /* 悬停效果 */
      }
    }
}

.job-content {

    position: relative;
    background-color: #e8eefa; /* 内容区域使用浅灰色背景 */
    .job-status {
        font-size: 12px;
        padding: 16px 12px 8px;
        background-color: #eff5ff; /* 稍深的背景色 */
        .job-status-item {
            margin-bottom: 8px;
            line-height: 1.5;
        }
    }
    .job-nodes {
        padding: 12px;
        display: flex;
        flex-direction: column;
        gap: 10px; /* Space between nodes */
        padding-bottom: 24px;
    }
}
.isExecute{
  .job-content{
    .job-nodes{
      padding-bottom: 16px;
    }
  }
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
.add-job-btn{
  .cicrle-btn{
    display: none;
    $circleRadius:7px;
    width: $circleRadius *2;
    height:  $circleRadius *2;
    border-radius: 50%;
    color: #fff;
    background-color: #3A83FF;
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
.word-elliptic{
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
.isPreview{
  .add-job-btn{
    display: none;
  }
  .job-header{
    .tools{
      display: none;
    }
  }
}
.isExecute{
    &.job{
      &.error{
        .job-header{
          .job-id{
            background-color: #eb517b;
          }
          .job-title{
            background-color: #eb517b;
          }
          .iconCirle{
            color: #eb517b;
          }
        }
        .job-content{
        .job-status{
          background-color: #fff9f9;
        }
        }
    }
    &.success{
      .job-header{
        .job-id{
          background-color: #2050d2;
        }
        .job-title{
          background-color: #2050d2;
        }
        .iconCirle{
          color: #2050d2;
        }
      }
      .job-content{
        .job-status{
          background-color: #e8eefa;
        }
      }
    }
    &.running{
      .job-header{
        .job-id{
          background-color: #459bd0;
        }
        .job-title{
          background-color: #459bd0;
        }
        }
        .job-content{
        .job-status{
          background-color: #eff5ff;
        }
      }
    }
    &.pending{
      .job-header{
          .job-id{
            background-color: #828992;
          }
          .job-title{
            background-color: #828992;
          }
        }
        .job-content{
          .job-status{
            background-color: #e8eefa;
          }
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
  background-color: #fff;
}
.rotateAnimate{
  font-size: 14px;
  transform-origin: center;
  color: #fff;
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
