import { Graph, ToolsView } from '@antv/x6';
import Vue from 'vue';
import shortcutPanel from '../components/canvas/ProcessCanvas/components/shortcutPanel.vue';
import dom from '@/utils/dom.js';

let app;
class ContextMenuTool extends ToolsView.ToolItem {
  knob;
  timer;

  render() {
    super.render();
    this.knob = ToolsView.createElement('div', false);
    this.knob.style.position = 'absolute';
    this.container.appendChild(this.knob);
    this.updatePosition(this.options);
    setTimeout(() => {
      this.toggleContextMenu(true);
    });
    return this;
  }

  toggleContextMenu(visible) {
    if (app) {
      app?.$destroy();
      const panelDom = document.querySelector('.shortcut-panel');
      panelDom?.remove();
    }
    document.removeEventListener('mousemove', this.onMouseMove);

    if (visible) {
      const newDom = ToolsView.createElement('div', false);
      this.knob.appendChild(newDom);
      app = new Vue({
        data: this.options.content,
        render: h => h(shortcutPanel),
      }).$mount(newDom);
      document.addEventListener('mousemove', this.onMouseMove);
    }
  }

  updatePosition(e) {
    const { style } = this.knob;
    if (e) {
      style.left = `${e.x}px`;
      style.top = `${e.y}px`;
    } else {
      style.left = '-1000px';
      style.top = '-1000px';
    }
  }

  onMouseMove = (e) => {
    clearTimeout(this.timer);
    // 如果点击的不是节点/边/快捷面板时关闭快捷面板
    if (
      !dom.parentClsContains('shortcut-panel', e.target)
      && !dom.parentClsContains('custom-node', e.target)
      && !dom.parentClsContains('x6-edge', e.target)
    ) {
      this.timer = setTimeout(() => {
        this.updatePosition();
        this.toggleContextMenu(false);
        if (this.options.onHide) {
          this.options.onHide.call(this);
        }
      }, 200);
    }
  };
}

ContextMenuTool.config({
  tagName: 'div',
  isSVGElement: false,
});

Graph.registerEdgeTool('contextmenu', ContextMenuTool, true);
Graph.registerNodeTool('contextmenu', ContextMenuTool, true);

export default ContextMenuTool;
