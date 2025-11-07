/**
* Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
* Edition) available.
* Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
* Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
* http://opensource.org/licenses/MIT
* Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
* an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
* specific language governing permissions and limitations under the License.
*/
<template>
  <div class="node-tree-wrapper">
    <div
      v-for="tree in treeData"
      :key="tree.id"
      class="tree-item"
      data-test-id="taskExcute_tree_nodeTree">
      <div
        v-if="!tree.children || tree.name === '汇聚网关' "
        :class="['tree-item-info', tree.isGateway ? 'gateway' : '']">
        <div class="tree-line" />
        <div class="tree-item-status">
          <span class="tree-item-expanded" />
          <span
            v-if="tree.type === 'ConvergeGateway'"
            class="commonicon-icon common-icon-node-convergegateway" />
          <span
            v-else
            :class="['default-node', nodeStateMap[tree.state]]" />
        </div>
        <div
          :class="['tree-item-name', curSelectId === tree.id ? 'active-name' : '']"
          @click="onClickNode(tree)">
          {{ tree.name }}
        </div>
      </div>
      <div
        v-else
        class="tree-item-children">
        <bk-tree
          :key="treeRandomKey"
          class="node-tree"
          :data="[tree]"
          :show-icon="showIcon"
          :tpl="tpl"
          :has-border="true"
          @on-expanded="expandedSubflowNode" />
      </div>
    </div>
  </div>
</template>
<script>

  import { bkTree } from 'bk-magic-vue';
  import tools from '@/utils/tools.js';

  export default {
    name: 'NodeTree',
    components: {
      bkTree,
    },
    props: {
      data: {
        type: Array,
        default() {
          return [];
        },
      },
      nodeNav: {
        type: Array,
        default() {
          return [];
        },
      },
      selectedFlowPath: {
        type: Array,
        default() {
          return [];
        },
      },
      heirarchy: {
        type: String,
        default: '',
      },
      level: {
        type: Number,
        default: 1,
      },
      defaultActiveId: {
        type: String,
        default: '',
      },
      nodeDisplayStatus: {
        type: Object,
        default: () => ({}),
        required: true,
      },
      isCondition: Boolean,
      executeInfo: {
        type: Object,
        default: () => ({}),
      },
      subCanvasActiveId: {
          type: [String, Number],
          default: '',
      },
    },
    data() {
      const gatewayType = {
        // EmptyStartEvent: 'commonicon-icon common-icon-node-startpoint-en',
        // EmptyEndEvent: 'commonicon-icon common-icon-node-endpoint-en',
        ParallelGateway: 'commonicon-icon common-icon-node-parallelgateway-shortcut',
        ExclusiveGateway: 'commonicon-icon common-icon-node-branchgateway',
        ConvergeGateway: 'commonicon-icon common-icon-node-convergegateway conver',
        ConditionalParallelGateway: 'commonicon-icon common-icon-node-conditionalparallelgateway',
        SubProcess: 'commonicon-icon common-icon-node-subflow',
      };
      const stateColor = {
        FINISHED: 'color:#61c861;',
        FAILED: 'color:#da443c;',
        WAIT: 'color:#dedfe6;',
        BLOCKED: 'color:#4b81f7;',
        RUNNING: 'color:#4d83f7;',
        SKIP: 'color: #edbbb8',
        SUSPENDED: 'color: #699df4',
      };
      const nodeStateMap = {
        FINISHED: 'finished',
        FAILED: 'failed',
        WAIT: 'wait',
        RUNNING: 'running',
        SKIP: 'skip',
        SUSPENDED: 'running',
      };
      return {
        curSelectId: '',
        treeData: [],
        subTreeData: [],
        showIcon: false,
        allNodeDate: {},
        gatewayType,
        stateColor,
        nodeStateMap,
        curSelectTreeId: '',
        setDefaultGateway: false,
        treeRandomKey: '',
      };
    },
    watch: {
      data: {
        handler(value) {
          const nodeNavLength = this.nodeNav.length;
          if (nodeNavLength === 1) {
            this.treeData = tools.deepClone(value[0].children);
          }
          // else {
          //   const cur = this.findSubChildren(value[0].children, this.nodeNav[nodeNavLength - 1].id);
          //   this.treeData = tools.deepClone(cur[0].subChildren);
          // }
          this.$nextTick(() => {
            this.nodeAddStatus(this.treeData, this.nodeDisplayStatus.children);
            this.setDefaultActiveId(this.treeData, this.treeData, this.defaultActiveId);
          });
        },
        deep: true,
        immediate: true,
      },
      nodeDisplayStatus: {
        handler(val) {
          this.nodeAddStatus(this.treeData, val.children);
        },
        deep: true,
        immediate: true,
      },
      nodeNav: {
        handler(val, old) {
          const cur = this.findSubChildren(this.data[0].children, val[val.length - 1].id);
          this.curSelectTreeId = val[val.length - 1].nodeId;
          if (val) {
            // 从画布点击自动网关、条件展开
            if (cur.length === 0) this.setDefaultGateway = true;
            // 如果导航值长度为1且与旧值长度不同（例如从子流程返回根节点）
            if (val.length === 1 && old && val.length !== old.length) {
              const treeData = this.data[0].children;
              // 更新树数据
              this.treeData = tools.deepClone(treeData);
              this.curSelectId = '';
            } else {
              // 更新节点显示状态
              this.nodeAddStatus(this.data[0].children, this.nodeDisplayStatus.children);
            }
          }
        },
        deep: true,
        immediate: true,
      },
      defaultActiveId: {
        handler(val) {
          if (val) {
            this.setDefaultActiveId(this.treeData, this.treeData, val);
          }
        },
        deep: true,
        immediate: true,
      },
      subCanvasActiveId: {
        handler(val) {
          if (val) {
            const node = this.findSubNode(this.treeData, val);
            const isSubProcess = node?.component?.code === 'subprocess_plugin' || node.type === 'SubProcess';
            this.onSelectNode(null, node, isSubProcess ? 'subflow' : 'node');
          }
        },
      },
    },
    methods: {
      findSubChildren(data, id, node = []) {
        data?.forEach((item) => {
          // if (item.type === 'SubProcess') {
          //   if (item.id === id) {
          //     node.push(item);
          //   } else {
          //     this.findSubChildren(item.subChildren, id, node);
          //   }
          // } else {
            if (item.children) {
              this.findSubChildren(item.children, id, node);
            }
          // }
        });
        return node;
      },
      findSubNode(data, id) {
         if (!data || !Array.isArray(data)) return null;
        for (const item of data) {
          if (item.id === id) {
            return item;
          }
          if (item.children) {
            const found = this.findSubNode(item.children, id);
            if (found) {
              return found;
            }
          }
        }
        return null;
      },
      // 非网关和子流程节点点击
      onClickNode(node) {
        this.setDefaultGateway = false;
        if (node.children && node.children.length === 0) return;
        // this.$emit('onOpenGatewayInfo', this.cachecallbackData, false);
        node.expanded = !node.expanded;
        this.curSelectId = node.id;
        this.$emit('onSelectNode', node.id, 'tasknode', node);
      },
      expandedSubflowNode(node, expanded) {
        if (expanded && node?.component?.code === 'subprocess_plugin') {
            this.$emit('dynamicLoad', node, expanded);
        }
        node.expanded = expanded;
      },
      nodeAddStatus(data, states) {
        if (data) {
          data.forEach((item) => {
            if (item.id && states[item.id]) {
              item.state = states[item.id].skip ? 'SKIP' : states[item.id].state;
            } else {
              item.state = 'WAIT';
            }
            if (item.isGateway) {
              item.state = 'Gateway';
            }
            // 子流程节点添加任务状态
            if (item?.component?.code === 'subprocess_plugin' && item.children) {
              this.nodeAddStatus(item.children, states);
            }
            if (item.children && item.children.length !== 0 && item.type !== 'SubProcess' && item?.component?.code !== 'subprocess_plugin') {
              this.nodeAddStatus(item.children, states);
            }
          });
        }
        this.treeRandomKey =  new Date().getTime();
      },
      tpl(node) {
        if (!this.allNodeDate[node.id] && node.id !== 'undefined') {
          this.allNodeDate[node.id] = node;
        }
        // 退回节点
        const callbackTip = node.isLoop ? this.$t('退回节点：') + node.callbackName : '';
        const iconClass = this.gatewayType[node.component?.code === 'subprocess_plugin' || node.type === 'SubProcess' ? 'SubProcess' : node.type];
        // 并行、条件分支样式
        let conditionClass = node.title !== this.$t('默认') ? 'condition' : 'default-conditon';

        // 回退节点
        if (node.isLoop) conditionClass = 'callback-condition';

        // 根据当前选中状态设置节点激活样式-选中样式
        const isActive = this.curSelectId === node.id ? 'is-node-active' : 'default-tpl-node';
        // 根据节点是否有父节点设置节点样式-节点样式
        const nodeClass = node.parent !== null ? `node ${this.nodeStateMap[node.state]} ` : `root-node ${this.nodeStateMap[node.state]}`;
        // 处理条件分支
        // isGateway表示当前为并行网关的条件/分支网关或条件分支网关的条件
        if (node.isGateway) {
          return (
            <span class={conditionClass}>
              <span class={'commonicon-icon common-icon-return-arrow callback'} onClick={e => this.onSelectNode(e, node, 'callback')}  v-bk-tooltips={callbackTip}></span>
              <span class={isActive} style={'font-size:12px'} data-node-id={node.id} domPropsInnerHTML={node.title} onClick={e => this.onSelectNode(e, node, 'gatewayCondition')}></span>
            </span>
          );
        }
        // 处理特定网关类型的节点渲染
        if (this.gatewayType[node.type] && node.type !== 'SubProcess') {
          return (
            <span style={'font-size: 16px'}>
              <span class={iconClass} style={this.stateColor[node.state]}></span>
              <span class={isActive} data-node-id={node.id} data-gateway-type={node.gatewayType} domPropsInnerHTML={node.name} onClick={e => this.onSelectNode(e, node, 'gateway')}></span>
            </span>
          );
        }
        // 处理子流程的渲染
        if (node.component?.code === 'subprocess_plugin' || node.type === 'SubProcess') {
           return (
            <span style={'font-size: 16px'}>
              <span class={iconClass} style={this.stateColor[node.state]}></span>
              <span class={isActive} data-node-id={node.id}  domPropsInnerHTML={node.name} onClick={e => this.onSelectNode(e, node, 'subflow')}></span>
            </span>
          );
        }
        return (
          <span style={'font-size: 10px'}>
            <span class={nodeClass}></span>
            <span class={isActive} data-node-id={node.id} domPropsInnerHTML={node.name} onClick={e => this.onSelectNode(e, node, 'node')}></span>
          </span>
        );
      },
      setDefaultActiveId(data, nodes, id) {
        this.curSelectId = id;
        if (nodes) {
          nodes.forEach((node) => {
            if (node.id === id) {
              this.$set(node, 'selected', true);
              if (this.setDefaultGateway) {
                this.$set(node, 'expanded', true);
              }
              if (node.parent) {
                node.parent.expanded = true;
                this.setExpand(node.parent);
              }
            } else {
              this.$set(node, 'selected', false);
            }
            if (node.children) {
              this.setDefaultActiveId(data, node.children, id);
            }
          });
        }
      },
      setExpand(node) {
        if (node.parent) {
          node.parent.expanded = true;
          this.setExpand(node.parent);
        }
      },
      getNodeActivedState(id) {
        const len = this.selectedFlowPath.length;
        if (this.selectedFlowPath[len - 1].id === id) {
          return true;
        }
        return false;
      },
      onSelectNode(e, node, type) {
        // 当父节点展开且未选中、 节点为并行、网关条件时阻止冒泡
        this.setDefaultGateway = false;
        // if (node.selected && node.component?.code === 'subprocess_plugin') {
        //   node.selected = false;
        //   node.parent.expanded = true;
        // }
        if (node.expanded && !node.selected) e?.stopPropagation();
        if (type === 'subflow') {
          e?.stopPropagation();
        }
        // 并行网关条件-仅展开条件
        if ((node?.conditionType === 'parallel' || node?.conditionType === 'default') && type === 'gatewayCondition') {
          node.expanded = !node.expanded;
          e?.stopPropagation();
          return;
        }
        // this.$emit('onOpenGatewayInfo', node.callbackData, false);

        // 分支网关/条件分支网关的条件
        if (type === 'gatewayCondition' && node.state === 'Gateway') {
          this.curSelectId = node.id || node.name;
          this.$emit('onOpenGatewayInfo', { ...node.callbackData, outgoing: node.outgoing, taskId: node.taskId }, true);
          return;
        }
        // ConvergeGateway节点特殊处理
        if (type === 'node' || type === 'callback') {
          const treeNodes = Array.from(document.querySelectorAll('.tree-node'));
          if (node.parent) {
            const curNodeIndex = node.parent.children.findIndex(item => item.id === node.id);
            node.parent.children.forEach((item, index) => {
              if (item.type === 'ConvergeGateway') {
                const converge = treeNodes.filter(dom => dom.dataset.gatewayType === 'converge');
                if (index > curNodeIndex) {
                  if (!node.expanded) {
                    converge.forEach((cdom) => {
                      cdom.style.display = 'block';
                    });
                  } else {
                    converge.forEach((cdom) => {
                      cdom.style.display = 'none';
                    });
                  }
                }
              }
            });
          }
          if (type === 'callback') {
            node.cacheId = node.id; // 选择打回节点前缓存id
            node.id = node.callbackData ? node.callbackData.id : node.id;
          }
        }
        if (this.curSelectId === node.id) {
          // 画布节点参数入口 子流程选中状态可点击
          // if (node.component?.code === 'subprocess_plugin') {
          //   this.cacheSubflowSelectNode[this.curSelectTreeId] = tools.deepClone(this.treeData);
          //   this.$emit('onNodeClick', node.id, 'subflow');
          //   this.renderSubProcessData(node);
          //   return;
          // }
          // 当打回节点选中时，还原该条件id
          node.id = node.cacheId ? node.cacheId : node.id;
          return;
        }
        this.curSelectId = node.id;
        let nodeType = node.component?.code === 'subprocess_plugin' ? 'subflow' : 'controlNode';
        nodeType = node.type === 'ServiceActivity' ? 'tasknode' : nodeType;

        node.selected = nodeType !== 'subflow';
        // let rootNode = node;
        if (!node.id) return;

        this.setDefaultActiveId(this.treeData, this.treeData, node.id);
        this.$emit('onSelectNode', node.id, nodeType, node);
        // 取缓存id--汇聚网关的退回节点
        node.id = node.cacheId ? node.cacheId : node.id;
        node.selected = node.id === this.curSelectId;

        // 选中后,非tree列表切换到已展开tree时默认展开
        if (node.selected) {
          this.$set(node, 'expanded', true);
          e?.stopPropagation();
        }
      },
    },
  };
</script>
<style lang="scss">
.bk-tree .tree-drag-node .tree-expanded-icon {
    margin-right: 3px;
    z-index: 99;
}
</style>
<style lang="scss" scoped>
@import '../../../scss/config.scss';
@import '../../../scss/mixins/scrollbar.scss';
.finished {
    background-color: #e5f6ea !important;
    border: 1px solid #3fc06d !important;
}
.failed {
    background-color: #ecbbb7 !important;
    border: 1px solid #ecbbb7 !important;
}
.wait {
    background-color: #e0e1e9 !important;
    border: 1px solid #e0e1e9 !important;
}
.running {
    background-color: #7ea2f0 !important;
    border: 1px solid #4d83f7 !important;
}
.skip {
    background-color: #f8c4c1 !important;
    border: 1px solid #da635f !important;
}
.conver {
    margin-left: -20px;
    background: #fff;
    position: relative;
    z-index: 99;
}
.node-tree-wrapper {
    display: inline-block;
    width: 237px;
    // min-width: 229px;
    padding: 8px;
    height: 100%;
    white-space: nowrap;
    overflow-x: auto;
    @include scrollbar;
}
.tree-item {
    position: relative;
    min-height: 28px;
    margin: 9px 0;
    font-size: 14px;
    color: #63656E;
    line-height: 28px;
    .tree-item-info {

        display: flex;
        align-items: center;

        .tree-item-status {
            display: flex;
            align-items: center;
            width: 36px;
            height: 16px;
            position: relative;
            .tree-item-expanded {
                width: 14px;
                height: 14px;
                cursor: pointer;
            }
            .default-node {
                line-height: 28px;
                display: block;
                width: 8px;
                height: 8px;
                background: #E5F6EA;
                border: 1px solid #3FC06D;
                border-radius: 4px;
                margin: 0 4px;

            }
        }

        .tree-item-name {
            width: 160px;
            max-width: 100px;
            height: 28px;
            cursor: pointer;
            user-select: none;
        }
        .tree-line {
            display: inline-block;
            position: relative;
            width: 1px;
            height: 16px;
            ::before {
                content: "";
                position: absolute;
                border-width: 1px;
                border-left: 1px dashed #c3cdd7;
            }
        }
    }
    .tree-item-children {
        // width: 100px;
        min-height: 28px;
        // background-color: #3FC06D;
    }
    .gateway {
        height: 20px;
        background: #FBF9E2;
        border: 1px solid #CCC79E;
        border-radius: 1px;
        width: 100px;
        &::after {
            content: '';
            width: 1px;
            height: 10px;
            position: absolute;
            right: auto;
            border-width: 1px;
            border-left: 1px dashed #c3cdd7;
            bottom: 50px;
            top: -14px;
            left: 7px;
        }
        .tree-item-status {
            width: 16px;
        }
    }
}
.active-name {
    color: #3a84ff !important;
}
.is-node-active {
    color: #3a84ff !important;
    font-size: 14px;
    padding: 0 4px;
    cursor: pointer;
    user-select: none;
}
.activity-node {
    display: inline-block;
    border: 2px solid #81d79f;
    width: 8px;
    height: 8px;
    margin: 0 4px;
    border-radius: 4px;
    background: #e5f6ea;
    user-select: none;
}
.callback-condition {
    font-size: 10px;
    background: #FBF9E2;
    border: 1px solid #CCC79E;
    border-radius: 1px;
    color: #968E4D;
    position: relative;
    padding:0 4px;
    cursor: pointer;
    margin-left: -20px;
    z-index: 999;
    user-select: none;
    .callback {
        display: inline-block;
        height: 17px;
        width: 17px;
        line-height: 20px;
        padding: 0px 0px;
        color: #c0c4cc;
    }
}
.condition {
    font-size: 10px;
    background: #FBF9E2;
    border: 1px solid #CCC79E;
    border-radius: 1px;
    color: #968E4D;
    position: relative;
    padding-right: 4px;
    cursor: pointer;
    user-select: none;
    left: -20px;
    padding-left: 20px;
    z-index: 88;
    .callback {
        display: none;
    }
}
.default-conditon {
    font-size: 10px;
    background: #F0F1F5;
    border: 1px solid #C4C6CC;
    border-radius: 1px;
    color: #968E4D;
    position: relative;
    padding-right: 4px;
    user-select: none;
    left: -20px;
    padding-left: 20px;
    z-index: 88;
    .callback {
        display: none;
    }
}
.tpl-gateway {
    font-size: 10px;
}
.root-node {
    display: none;
    color: #7ea2f0;
}
.node {
    display: inline-block;
    width: 8px;
    height: 8px;
    background: #E5F6EA;
    border: 1px solid #3FC06D;
    border-radius: 4px;
    margin:0 3px;
    font-size: 10px;
    padding: 0 2px;
    cursor: pointer;
}
.default-tpl-node {
    font-size: 14px;
    padding: 0 4px;
    cursor: pointer;
    user-select: none;
}
</style>
