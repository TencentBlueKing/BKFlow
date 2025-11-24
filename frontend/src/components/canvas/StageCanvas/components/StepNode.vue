<template>
  <div
    class="node"
    :class="{ active:activeNode?.id === node.id,isPreview:!editable,isExecute,[ETaskStatusTypeMap[status].class]:true, isSkip }"
    @click="handleNode(currentNode)">
    <div class="node-icon">
      <span
        v-if="editable"
        class="node-move-icon commonicon-icon common-icon-drawable" />
      <template v-if="!isExecute||(status === ETaskStatusType.PENDING)">
        <template v-if="nodeType==='Node'">
          <i
            v-if="pluginType === 'component'"
            :class="`logo-icon ${getIconCls(currentNode.component?.code)}`" />
          <img
            v-else-if="pluginType==='blueking'||pluginType==='uniform_api'"
            :src="getLogoByPluginsDetail()"
            alt="">
          <img
            v-else
            :src="defaultLogo"
            alt="网格图标">
        </template>

        <template v-else-if="nodeType==='SubProcess'">
          <i class="logo-icon commonicon-icon common-icon-sub-process" />
        </template>
      </template>
      <span
        v-else
        style="display: inline-block;">
        <i :class="`${isSkip?ETaskStatusIconMap[ETaskStatusType.ERROR]:ETaskStatusIconMap[status]}`" />
      </span>
    </div>
    <div class="node-title">
      <span
        v-if="activeNode?.id === node.id"
        class="editing-text">编辑中...</span>

      <div
        v-else
        class="step-name">
        <span
          class="word-elliptic name"><span
            v-bk-tooltips="{
              disabled:!currentNode?.name,
              content: currentNode?.name,
            }">
            {{ currentNode?.name || '新节点' }}
          </span>
        </span>
        <span
          v-if="isExecute"
          class="toolAndTime">
          <div class="tool">
            <bk-button
              v-if="status === ETaskStatusType.RUNNING"
              theme="danger"
              size="small"
              text
              @click.stop="handleOperateNode('onForceFail')">强制终止</bk-button>
            <bk-button
              v-if="status === ETaskStatusType.ERROR"
              theme="primary"
              size="small"
              text
              @click.stop="handleOperateNode('onRetryClick')">重试</bk-button>
            <bk-button
              v-if="status === ETaskStatusType.ERROR"
              theme="primary"
              size="small"
              text
              @click.stop="handleOperateNode('onSkipClick')">跳过</bk-button>
          </div>
          <div
            v-if="node.state!==ETaskStatusType.PENDING"
            class="time">{{ durationTime }}</div>
        </span>
      </div>
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
      <div class="add-step-btn">
        <div
          class="cicrle-btn"
          @click.stop="()=>{}">
          <bk-dropdown-menu
            ref="dropdown"
            trigger="click"
            @show="dropdownShow"
            @hide="dropdownHide">
            <div
              slot="dropdown-trigger"
              class="dropdown-trigger-text">
              <span><span class="plus">+</span> 节点 <i class="commonicon-icon common-icon-next-triangle-shape triangleIcon" /></span>
            </div>
            <ul
              slot="dropdown-content"
              class="bk-dropdown-list">
              <li>
                <a
                  href="javascript:;"
                  @click="addStep('Node')">节点</a>
              </li>
              <li>
                <a
                  href="javascript:;"
                  @click="addStep('SubProcess')">子流程</a>
              </li>
            </ul>
          </bk-dropdown-menu>
        </div>
      </div>
    </div>
    <div class="info-icon">
      <span
        v-if="isSkip"
        class="info-icon-item commonicon-icon common-icon-arrow-left iconCirle skip-icon" />
      <span
        v-else-if="isRty"
        class="info-icon-item iconCirle rty-num">
        {{ node.retry }}
      </span>
    </div>
    <div
      v-if="showNotAllowMove"
      class="no-allow-move">
      <span>仅有一个节点时，不可移动</span>
    </div>
  </div>
</template>
<script>
import { mapState } from 'vuex';
import { ETaskStatusType, ETaskStatusTypeMap } from '../data';
import { SYSTEM_GROUP_ICON } from '@/constants/index.js';
import { getDurationTime } from '../utils';
export default {
    props: {
        node: {
            type: Object,
            required: true,
        },
        nodes: {
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
        showNotAllowMove: {
          type: Boolean,
          default: false,
        },
    },
    data() {
        return {
            toolIconArr: [
              {
                icon: 'commonicon-icon common-icon-double-paper-2',
                name: '复制',
                handleClick: () => {
                  this.$emit('copyNode', this.node);
                },
              },
              {
                icon: 'commonicon-icon common-icon-bkflow-delete',
                name: '删除',
                handleClick: () => {
                  this.$emit('deleteNode',  this.node);
                },
                disabled: () => this.nodes.length <= 1,
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
            codeMapToType: {
              remote_plugin: 'blueking',
              uniform_api: 'uniform_api',
            },
            isTextDropdownShow: false,
            defaultLogo: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjIiIGhlaWdodD0iMjIiIHZpZXdCb3g9IjAgMCAyMiAyMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB4PSIxIiB5PSIxIiB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHJ4PSIyIiBzdHJva2U9IiNENEU4RkYiIHN0cm9rZS13aWR0aD0iMSIvPjxwYXRoIGQ9Ik02IDYgTDE2IDE2IE02IDE2IEwxNiA2IiBzdHJva2U9IiNENEU4RkYiIHN0cm9rZS13aWR0aD0iMSIvPjwvc3ZnPg==',
        };
    },
    computed: {
      ...mapState({
        activeNode: state => state.stageCanvas.activeNode,
        activities: state => state.template.activities,
        pluginsDetail: state => state.stageCanvas.pluginsDetail,
      }),
      status() {
        return this.node.state || ETaskStatusType.PENDING;
      },
      isSkip() {
        return this.node.skip;
      },
      isRty() {
        return this.node.retry ;
      },
      currentNode() {
        if (!this.isExecute) {
          return this.activities[this.node.id];
        }
          return Object.values(this.activities).find(item => item.template_node_id === this.node.id);
      },
      nodeType() {
        return this.node.option?.nodeType || 'Node';
      },
      pluginType() {
        if (this.currentNode?.component && this.currentNode.component.code) {
          const type = (this.currentNode.component.code === 'uniform_api' || this.currentNode.component.code === 'remote_plugin') ? this.codeMapToType[this.currentNode.component.code]  : 'component';
          return type;
        }
        return null;
      },
      durationTime() {
        return getDurationTime(
            this.node.start_time,
            this.node.state === ETaskStatusType.RUNNING ? new Date().toString() : this.node.finish_time,
          );
      },
    },
    methods: {
        handleNode(node) {
          if (this.isExecute) {
            this.$emit('handleOperateNode', 'onNodeClick', this.currentNode);
          } else {
            this.$emit('handleNode', node);
          }
        },
        addStep(value) {
          console.log('StepNode.vue_Line:238', value);
          this.$emit('addNewStep', value);
          this.triggerHandler();
        },
        handleOperateNode(type) {
          this.$emit('handleOperateNode', type, this.currentNode);
        },
        getIconCls(type) {
          const systemType = SYSTEM_GROUP_ICON.find(item => new RegExp(item).test(type.toUpperCase()));
          if (systemType) {
            return `common-icon-sys-${systemType.toLowerCase()}`;
          }
          return 'common-icon-sys-default';
        },
        getLogoByPluginsDetail() {
          // eslint-disable-next-line camelcase
          return this.pluginsDetail[this.pluginType]?.[this.currentNode.component.data.plugin_code.value]?.logo_url || this.defaultLogo;
        },
        dropdownShow() {
          this.isTextDropdownShow = true;
        },
        dropdownHide() {
          this.isTextDropdownShow = false;
        },
        triggerHandler() {
          this.$refs.dropdown.hide();
        },
    },
};
</script>
<style lang="scss" scoped>
.node {
    background-color: #ffffff; /* 更浅的背景色 */
    border: 1px solid #C3CDD7;
    border-radius: 2px;
    padding: 10px 12px;
    display: flex;
    align-items: center;
    font-size: 12px;
    width: 100%;
    max-width: 240px;
    height: 42px;
    box-sizing: border-box;
    margin: 0 auto;
    cursor: pointer; /* 添加鼠标指针样式 */
    position: relative;
    .logo-icon{
      font-size: 16px;
      color: #3A83FF;
    }
    &:hover{
      border-color: #3A83FF;
      background-color: #EDF2F7;
        .tools{
            display: flex;
        }
        .add-step-btn .cicrle-btn{
            display: flex;
            z-index: 1000;
        }
        .node-icon{
          .node-move-icon{
            font-size: 18px;
            cursor: move;
            margin-left: -4px;
            display: inline-block;
          }
        }
    }
    &.active {
        border: 1px solid #3A83FF;
        background-color: rgba(58, 131, 255, 0.05);
    }
    .info-icon{
        .info-icon-item{
        position: absolute;
        top: 0;
        right: 0;
        margin-right: 0;
        transform: translate(50%,-50%);
        &.iconCirle.skip-icon{
          transform: translate(50%,-50%) rotate(180deg);
          background-color: #ff9d4d;
        }
        &.iconCirle.rty-num{
          color: #fff;
          font-size: 10px;
          background-color: #ff9d4d;
        }
      }
    }
    .no-allow-move{
      position: absolute;
      top: -1px;
      left: -1px;
      width: calc(100% + 2px);
      height: calc(100% + 2px);
      border: 2px dashed #F8B4B4;
      border-spacing: 5px;
      background: #FDF0F0;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #EA3636;
    }
}

.node-icon {
    height: 22px;
    background-color: transparent; /* 移除背景色 */
    display: flex;
    justify-content: center;
    align-items: center;
    margin-right: 10px;
    img {
        width: 100%;
        height: 100%;
        object-fit: contain;
    }
    .node-move-icon{
      font-size: 18px;
      cursor: move;
      margin-left: -4px;
      display: none;
    }
}

.node-title {
    flex: 1;
    font-size: 12px;
    display: flex;
    height: 16px;
    align-items: center;
    justify-content: space-between;
    width: 0;
    .step-name{
        flex: 1;
        display: flex;
        align-items: center;
        width: 0;
        .toolAndTime{
          display: flex;
          align-items: center;
          .bk-button-text.bk-button-small{
            padding: 0;
            margin-right: 4px;
          }
        }
        .name{
          flex: 1;
        }
    }
    .editing-text {
        color: #3A83FF;
        font-style: italic;
        flex: 1;
    }

}


.node-status {
    display: flex;
    flex-direction: column;
    gap: 3px;
}
.tools{
  display: none;
  align-items: center;
  font-size: 12px;
  justify-content: center;
  align-items: center;
  .iconBtn{
    width: 16px;
    height: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }
}
.add-step-btn{
  .cicrle-btn{
    display: none;
    $circleRadius:10px;
    width: 64px;
    height:  $circleRadius *2;
    border-radius: $circleRadius  ;
    color: #3A83FF;
    background-color: #fff;
    border: 1px solid #3A83FF;
    align-items: center;
    justify-content: center;
    position: absolute;
    bottom: 0 - $circleRadius;
    left: 50%;
    transform: translateX(-32px);
    z-index: 10;
    line-height: 2 * $circleRadius;
    font-size: 12px;
    span{
      position: relative;
      top: -0.5px;
      cursor: pointer;
    }
    .triangleIcon{
      font-size: 12px;
      transform: rotateZ(90deg);
      display: inline-block;
      position: relative;
      top: -1px;
    }
    .plus{
      font-weight: 700;
    }
  }
}
.word-elliptic{
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

.isPreview{
  .add-step-btn{
    display: none;
  }
  .node-title{
    .tools{
      display: none;
    }
  }
}
.isExecute{
  &.node{
    &.error{
      border: 1px solid #eb517b;
      .toolAndTime{
        .time{
          color: #eb517b;
        }
      }
      .iconCirle{
        background-color: #eb517b;
      }
    }
    &.success{
      border: 1px solid #2050d2;
      .time{
        color: #2050d2;
      }
      .iconCirle{
        background-color: #2050d2;
      }
    }
    &.running{
      border: 1px solid #459bd0;
      .time{
        color: #459bd0;
      }
    }
    &.pending{
      border: 1px solid #C3CDD7;
    }
    &.isSkip{
      border: 1px solid #eb517b;
      .toolAndTime{
        .time{
          color: #eb517b;
        }
      }
      .iconCirle{
        background-color: #eb517b;
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
