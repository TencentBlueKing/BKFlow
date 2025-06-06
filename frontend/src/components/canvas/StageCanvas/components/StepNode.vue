<template>
  <div
    class="node"
    :class="{ active:activeNode?.id === node.id,isPreview:!editable }"
    @click="editNode(node)">
    <div class="node-icon">
      <img
        src="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjIiIGhlaWdodD0iMjIiIHZpZXdCb3g9IjAgMCAyMiAyMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB4PSIxIiB5PSIxIiB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHJ4PSIyIiBzdHJva2U9IiNENEU4RkYiIHN0cm9rZS13aWR0aD0iMSIvPjxwYXRoIGQ9Ik02IDYgTDE2IDE2IE02IDE2IEwxNiA2IiBzdHJva2U9IiNENEU4RkYiIHN0cm9rZS13aWR0aD0iMSIvPjwvc3ZnPg=="
        alt="网格图标">
    </div>
    <div class="node-title">
      <span
        v-if="activeNode?.id === node.id"
        class="editing-text">编辑中...</span>
      <span
        v-else
        class="word-elliptic step-name">{{ currentNode?.name || '新节点' }}</span>
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
        };
    },
    computed: {
      ...mapState({
        activeNode: state => state.stageCanvas.activeNode,
        activities: state => state.template.activities,
      }),
      currentNode() {
        return this.activities[this.node.id];
      },
    },
    methods: {
        editNode(node) {
          this.$emit('editNode', node);
        },
        addStep() {
          this.$emit('addNewStep');
        },
    },
};
</script>
<style lang="scss" scoped>
.node {
    background-color: #F8FBFF; /* 更浅的背景色 */
    border: 1px solid #D4E8FF;
    border-radius: 2px;
    padding: 10px 12px;
    display: flex;
    align-items: center;
    font-size: 12px;
    color: #555;
    width: 100%;
    max-width: 240px;
    height: 42px;
    box-sizing: border-box;
    margin: 0 auto;
    cursor: pointer; /* 添加鼠标指针样式 */
    transition: all 0.2s;
    position: relative;
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
    color: #666;
}
.node-icon img {
    width: 100%;
    height: 100%;
    object-fit: contain;
}
.node-title {
    flex: 1;
    font-size: 12px;
    color: #333;
    display: flex;
    height: 16px;
    align-items: center;
    justify-content: space-between;
    flex: 1;
    .step-name{
        max-width: 120px;

        flex: 1;
    }
}
.vertical-connector {
    width: 1px;
    height: 12px; /* u589eu52a0u9ad8u5ea6 */
    background-color: #D4E8FF; /* u66f4u65b0u8fdeu63a5u7ebfu989cu8272 */
    margin: 5px auto; /* u589eu52a0u4e0au4e0bu95f4u8ddd */
}
.editing-text {
    color: #3A83FF;
    font-style: italic;
    flex: 1;
}
.value-link {
    color: #3A83FF;
    text-decoration: none;
    cursor: pointer;
}
.value-link:hover {
    text-decoration: underline;
}
.highlighted-value {
    display: inline-block;
    border-radius: 3px;
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
</style>
