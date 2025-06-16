<template>
  <div
    class="node"
    :class="{ active:activeNode?.id === node.id,isPreview:!editable,isExecute,[ETaskStatusTypeMap[status].class]:true }"
    @click="handleNode(node)">
    <div class="node-icon">
      <template v-if="!isExecute||(status===ETaskStatusType.PENDING)">
        <i
          v-if="pluginType==='component'"
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

      <span
        v-else
        style="display: inline-block;">
        <i :class="`${ETaskStatusIconMap[status]}`" />
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
          class="word-elliptic name">{{ currentNode?.name || '新节点' }}</span>
        <span
          v-if="isExecute"
          class="toolAndTime">
          <div class="tool">
            <bk-button
              v-if="status===ETaskStatusType.RUNNING"
              theme="danger"
              size="small"
              text
              @click="handleOperateNode('stop')">强制终止</bk-button>
            <bk-button
              v-if="status===ETaskStatusType.ERROR"
              theme="primary"
              size="small"
              text
              @click="handleOperateNode('reTry')">重试</bk-button>
            <bk-button
              v-if="status===ETaskStatusType.ERROR"
              theme="primary"
              size="small"
              text
              @click="handleOperateNode('skip')">跳过</bk-button>
          </div>
          <div class="time">3h1m</div>
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
          @click.stop="addStep">
          <span>+</span>
        </div>
      </div>
    </div>
  </div>
</template>
<script>
import { mapState } from 'vuex';
import { ETaskStatusType, ETaskStatusTypeMap } from '../data';
import { SYSTEM_GROUP_ICON } from '@/constants/index.js';
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
                  console.log('StageNode.vue_Line:85', 1);
                  this.$emit('deleteNode',  this.node);
                },
                disabled: () => this.nodes.length <= 1,
              },
            ],
            ETaskStatusType,
            status: ETaskStatusType.SUCCESS,
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
            defaultLogo: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjIiIGhlaWdodD0iMjIiIHZpZXdCb3g9IjAgMCAyMiAyMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB4PSIxIiB5PSIxIiB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHJ4PSIyIiBzdHJva2U9IiNENEU4RkYiIHN0cm9rZS13aWR0aD0iMSIvPjxwYXRoIGQ9Ik02IDYgTDE2IDE2IE02IDE2IEwxNiA2IiBzdHJva2U9IiNENEU4RkYiIHN0cm9rZS13aWR0aD0iMSIvPjwvc3ZnPg==',
        };
    },
    computed: {
      ...mapState({
        activeNode: state => state.stageCanvas.activeNode,
        activities: state => state.template.activities,
        pluginsDetail: state => state.stageCanvas.pluginsDetail,
      }),
      currentNode() {
        return this.activities[this.node.id];
      },
      pluginType() {
        if (this.currentNode?.component && this.currentNode.component.code) {
          const type = (this.currentNode.component.code === 'uniform_api' || this.currentNode.component.code === 'remote_plugin') ? this.codeMapToType[this.currentNode.component.code]  : 'component';
          return type;
        }
      return null;
    },
    },
    methods: {
        handleNode(node) {
          this.$emit('handleNode', node);
        },
        addStep() {
          this.$emit('addNewStep');
        },
        handleOperateNode(type) {
          this.$emit('handleOperateNode', type, this.currentNode);
        },
        getIconCls(type) {
          const systemType = SYSTEM_GROUP_ICON.find(item => new RegExp(item).test(type.toUpperCase()));
          console.log('StepNode.vue_Line:172', systemType);
          if (systemType) {
            return `common-icon-sys-${systemType.toLowerCase()}`;
          }
          return 'common-icon-sys-default';
        },
        getLogoByPluginsDetail() {
          // eslint-disable-next-line camelcase
          return this.pluginsDetail[this.pluginType]?.[this.currentNode.component.data.plugin_code.value]?.logo_url || this.defaultLogo;
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
    transition: all 0.2s;
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
        }
    }
    &.active {
        border: 1px solid #3A83FF;
        background-color: rgba(58, 131, 255, 0.05);
    }
}

.node-icon {
    width: 22px;
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
    $circleRadius:6px;
    width: $circleRadius *2;
    height:  $circleRadius *2;
    border-radius: 50%;
    color: #3A83FF;
    background-color: #fff;
    font-weight: bold;
    border: 1px solid #3A83FF;
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
      border: 1px solid #FF5656;
      .toolAndTime{
        .time{
          color: #FF5656;
        }
      }
    }
    &.success{
      border: 1px solid #5BC882;
      .time{
        color: #5BC882;
      }
    }
    &.running{
      border: 1px solid #3C96FF;
      .time{
        color: #3C96FF;
      }
    }
    &.pending{
      border: 1px solid #C3CDD7;
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
    background-color: #5BC882;
  }
}
.error{
  .iconCirle{
    background-color: #ff5656;
  }
}
.rotateAnimate{
  font-size: 14px;
  margin-right: 8px;
  transform-origin: center;
  color: #3c96ff;
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
