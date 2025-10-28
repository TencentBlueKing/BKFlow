<template>
  <div class="dnd-panel">
    <ul
      ref="containerRef"
      class="nodes-wrapper">
      <li
        v-for="node in NODES"
        :key="node.id"
        :class="[
          'node-item',
          node.id === 'group' ? 'group-node' : `common-icon-node-${node.icon}`,
          { disabled: isShowStartOrEndPoint(node) },
        ]"
        :data-type="node.id" />
    </ul>
  </div>
</template>
<script>
  import { Graph } from '@antv/x6';
  import { Dnd } from '@/utils/dnd.js';
  import { uuid } from '@/utils/uuid.js';
  import Guide from '@/utils/guide.js';
  import dom from '@/utils/dom.js';
  import i18n from '@/config/i18n/index.js';

  const NODES = [
    { id: 'start', icon: 'startpoint-zh', name: i18n.t('开始节点') },
    { id: 'end', icon: 'endpoint-zh', name: i18n.t('结束节点') },
    { id: 'task', icon: 'tasknode', name: i18n.t('任务节点') },
    { id: 'subflow', icon: 'subprocess', name: i18n.t('子流程') },
    { id: 'branch-gateway', icon: 'branchgateway', name: i18n.t('分支网关') },
    { id: 'parallel-gateway', icon: 'parallelgateway', name: i18n.t('并行网关') },
    { id: 'conditional-parallel-gateway', icon: 'conditionalparallelgateway', name: i18n.t('条件并行网关') },
    { id: 'converge-gateway', icon: 'convergegateway', name: i18n.t('汇聚节点') },
    // { id: 'group', icon: 'group', name: '分组节点' },
  ];

  export default {
    name: 'ProcessDnd',
    props: {
      instance: Graph,
      canvasData: {
        type: Array,
        default: () => ([]),
      },
    },
    data() {
      return {
        NODES,
        dnd: null,
      };
    },
    computed: {
      isDisableStartPoint() {
        return !!Object.values(this.canvasData).find(node => node.data.type === 'start');
      },
      isDisableEndPoint() {
        return !!Object.values(this.canvasData).find(node => node.data.type === 'end');
      },
    },
    mounted() {
      this.dnd = new Dnd({
        target: this.instance,
        scaled: false,
        dndContainer: this.$refs.containerRef,
        nodeDragging: (e, node) => this.handleNodeDragging(e, node),
        nodeDragEnd: (e, node) => this.handleNodeDragEnd(e, node),
        getDragNode: node => node.clone({ keepId: true }),
        getDropNode: node => node.clone({ keepId: true }),
      });
      // 将分组节点层级设置在普通节点之下
      this.instance.on('node:added', ({ node }) => {
        const zIndex = node.shape === 'custom-group-node' ? 1 : 2;
        node.setZIndex(zIndex);
      });
      // 添加指引tip
      this.renderGuide();
      // 监听鼠标按下
      const dndPanelDom = document.querySelector('.dnd-panel');
      dndPanelDom.addEventListener('mousedown', this.handleMouseDown);
    },
    methods: {
      isShowStartOrEndPoint(node) {
        if (node.id === 'start') {
          return this.isDisableStartPoint;
        } if (node.id === 'end') {
          return this.isDisableEndPoint;
        }
        return false;
      },
      handleNodeDragging(e, node) {
        this.$emit('dragging', { e, node, type: 'add' });
      },
      handleNodeDragEnd(e, node) {
        this.$emit('dragEnd', { e, node, type: 'add' });
      },
      // 监听鼠标是否点在节点上
      handleMouseDown(e) {
        if (dom.parentClsContains('node-item', e.target) || dom.parentClsContains('entry-item', e.target)) {
          this.downEvent = e;
          document.addEventListener('mousemove', this.handleMouseMove);
          document.addEventListener('mouseup', this.handleMouseUp);
        }
      },
      // 移动距离大于 3 像素，认为是拖拽事件
      handleMouseMove(event) {
        if (!this.downEvent) return;
        const { pageX, pageY } = this.downEvent;
        const max = Math.max(event.pageX - pageX, event.pageY - pageY);
        if (max > 3) {
          this.startDrag(this.downEvent);
          document.removeEventListener('mousemove', this.handleMouseMove);
        }
      },
      handleMouseUp() {
        this.downEvent = null;
        document.removeEventListener('mouseup', this.handleMouseUp);
      },
      startDrag(e) {
        const data = this.getNodeCustomAttribute(e.target);
        const isRectShape = ['task', 'subflow'].includes(data.type);
        // 该 node 为拖拽的节点，默认也是放置到画布上的节点，可以自定义任何属性
        let node;
        if (data.type === 'group') {
          node = this.instance.createNode({
            shape: 'custom-group-node',
            width: 300,
            height: 150,
            data: {
              parent: true,
            },
          });
        } else {
          node = this.instance.createNode({
            id: `node${uuid()}`,
            shape: 'custom-node',
            width: isRectShape ? 154 : 34,
            height: isRectShape ? 54 : 34,
            data,
            zIndex: 5,
          });
        }
        this.dnd.start(node, e);
      },
      getNodeCustomAttribute(el) {
        return el.getAttributeNames().reduce((acc, cur) => {
          if (cur === 'data-type') {
            acc.type = el.getAttribute(cur);
          } else if (cur.indexOf('data-config') > -1) {
            const fields = cur.split('data-config')[1].split('-').filter(item => item);
            let key = '';
            fields.forEach((item, index) => {
              const text = index === 0 ? item : `${item.charAt(0).toUpperCase()}${item.slice(1)}`;
              key += text;
            });
            acc[key] = el.getAttribute(cur);
          }
          return acc;
        }, {});
      },
      renderGuide() {
        const nodesGuide = [
          {
            el: '.node-item[data-type=task]',
            url: require('@/assets/images/left-tasknode-guide.gif'),
            text: [
              {
                type: 'name',
                val: this.$t('标准插件节点：'),
              },
              {
                type: 'text',
                val: this.$t('已封装好的可用插件，可直接选中拖拽至画布中。'),
              },
            ],
          },
          {
            el: '.node-item[data-type=subflow]',
            url: require('@/assets/images/left-subflow-guide.gif'),
            text: [
              {
                type: 'name',
                val: this.$t('子流程：'),
              },
              {
                type: 'text',
                val: this.$t('同一个项目下已新建的流程，作为子流程可以嵌套进至当前流程，并在执行任务时可以操作子流程的单个节点。'),
              },
            ],
          },
          {
            el: '.node-item[data-type=parallel-gateway]',
            url: require('@/assets/images/left-parallelgateway-guide.gif'),
            text: [
              {
                type: 'name',
                val: this.$t('并行网关：'),
              },
              {
                type: 'text',
                val: this.$t('有多个流出分支，并且多个流出分支都默认执行。'),
              },
            ],
          },
          {
            el: '.node-item[data-type=branch-gateway]',
            url: require('@/assets/images/left-branchgateway-guide.gif'),
            text: [
              {
                type: 'name',
                val: this.$t('分支网关：'),
              },
              {
                type: 'text',
                val: this.$t('执行符合条件的唯一流出分支。'),
              },
            ],
          },
          {
            el: '.node-item[data-type=converge-gateway]',
            url: require('@/assets/images/left-convergegateway-guide.gif'),
            text: [
              {
                type: 'name',
                val: this.$t('汇聚网关：'),
              },
              {
                type: 'text',
                val: this.$t('当汇聚网关用于汇聚并行网关时，所有进入顺序流的分支都到达以后，流程才会通过汇聚网关。'),
              },
            ],
          },
          {
            el: '.node-item[data-type=conditional-parallel-gateway]',
            url: require('@/assets/images/left-branch-converge-gateway-guide.gif'),
            text: [
              {
                type: 'name',
                val: this.$t('条件并行网关：'),
              },
              {
                type: 'text',
                val: this.$t('执行时满足分支条件的都会执行。'),
              },
            ],
          },
        ];
        const baseConfig = {
          el: '',
          width: 330,
          delay: 500,
          arrow: false,
          placement: 'right',
          trigger: 'mouseenter',
          img: {
            height: 155,
            url: '',
          },
          text: [],
        };
        nodesGuide.forEach((m) => {
          baseConfig.img.url = m.url;
          baseConfig.text = m.text;
          const guide = new Guide(baseConfig);
          guide.mount(document.querySelector(m.el));
        });
      },
    },
  };
</script>
<style lang="scss" scoped>
  .nodes-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    position: relative;
    z-index: 3;
    margin: 0;
    padding: 0;
    width: 60px;
    height: 100%;
    border-right: 1px solid #cacedb;
    user-select: none;
    list-style: none;
    background: #fff;
    .node-item {
      width: 100%;
      margin: 15px 0;
      text-align: center;
      font-size: 28px;
      color: #546a9e;
      list-style: none;
      cursor: move;
      &.actived,
      &:hover {
        color: #3a84ff;
      }
      &.disabled {
        opacity: 0.3;
        pointer-events: none;
      }
    }
    .common-icon-node-tasknode,
    .common-icon-node-subprocess {
      font-size: 20px;
    }
    .group-node {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 24px;
      border: 1px solid #546a9e;
      border-radius: 2px;
      &:hover {
        border-color: #3a84ff;
      }
      .text {
        display: inline-block;
        font-size: 20px;
        transform: scale(0.4);
      }
    }
  }
</style>
