// import { Graph } from '@antv/x6'

// 控制连接桩显示/隐藏
// const showPorts = (ports, show) => {
//   for (let i = 0, len = ports.length; i < len; i += 1) {
//     ports[i].style.visibility = show ? 'visible' : 'hidden'
//   }
// }

// ctrl键是否被按下
let ctrlPressed = false;
// 分组节点padding
const embedPadding = 20;

export const registryEvents = (graph, editable) => {
  // 控制连接桩显示/隐藏
  graph.on('node:mouseenter', ({ cell }) => {
    if (!editable) return;
    const ports = cell.getPorts();
    ports.forEach((item) => {
      cell.setPortProp(item.id, 'attrs/circle/style/visibility', 'visible');
    });
  });
  graph.on('node:mouseleave', ({ cell }) => {
    const ports = cell.getPorts();
    ports.forEach((item) => {
      cell.setPortProp(item.id, 'attrs/circle/style/visibility', 'hidden');
    });
  });

  // 鼠标移入连线添加工具
  graph.on('edge:mouseenter', ({ cell }) => {
    cell.attr('line/stroke', '#3a84ff');
    if (!editable) return;
    cell.addTools([
      // 线段拖动
      // {
      //   name: 'segments',
      //   args: {
      //     threshold: 20,
      //     snapRadius: 20,
      //     attrs: {
      //       fill: '#3a84ff',
      //     },
      //   },
      // },
      // 连线源端点拖动
      {
        name: 'source-arrowhead',
        args: {
          tagName: 'circle',
          attrs: {
            r: '6',
            fill: '#ffffff',
            stroke: '#a4deb1',
            strokeWidth: 1,
          },
        },
      },
      // 连线目标端点拖动
      {
        name: 'target-arrowhead',
        args: {
          tagName: 'circle',
          attrs: {
            r: '6',
            fill: '#ffffff',
            stroke: '#a4deb1',
            strokeWidth: 1,
          },
        },
      },
    ]);
  });

  // 鼠标移出连线删除工具
  graph.on('edge:mouseleave', ({ cell }) => {
    cell.attr('line/stroke', '#a9adb6');
    cell.removeTools();
  });

  /** --- start 分组节点内子节点拖动时自动调整尺寸 --- */
  graph.on('node:embedding', ({ e }) => {
    ctrlPressed = e.metaKey || e.ctrlKey;
  });

  graph.on('node:embedded', () => {
    ctrlPressed = false;
  });

  graph.on('node:change:size', ({ node, options }) => {
    if (options.skipParentHandler) {
      return;
    }

    const children = node.getChildren();
    if (children && children.length) {
      node.prop('originSize', node.getSize());
    }
  });

  graph.on('node:change:position', ({ node, options }) => {
    if (options.skipParentHandler || ctrlPressed) {
      return;
    }

    const children = node.getChildren();
    if (children && children.length) {
      node.prop('originPosition', node.getPosition());
    }

    const parent = node.getParent();
    if (parent && parent.isNode()) {
      let originSize = parent.prop('originSize');
      if (originSize === null) {
        originSize = parent.getSize();
        parent.prop('originSize', originSize);
      }

      let originPosition = parent.prop('originPosition');
      if (originPosition === null) {
        originPosition = parent.getPosition();
        parent.prop('originPosition', originPosition);
      }

      let { x } = originPosition;
      let { y } = originPosition;
      let cornerX = originPosition.x + originSize.width;
      let cornerY = originPosition.y + originSize.height;
      let hasChange = false;

      const children = parent.getChildren();
      if (children) {
        children.forEach((child) => {
          const bbox = child.getBBox().inflate(embedPadding);
          const corner = bbox.getCorner();

          if (bbox.x < x) {
            x = bbox.x;
            hasChange = true;
          }

          if (bbox.y < y) {
            y = bbox.y;
            hasChange = true;
          }

          if (corner.x > cornerX) {
            cornerX = corner.x;
            hasChange = true;
          }

          if (corner.y > cornerY) {
            cornerY = corner.y;
            hasChange = true;
          }
        });
      }

      if (hasChange) {
        parent.prop(
          {
            position: { x, y },
            size: { width: cornerX - x, height: cornerY - y },
          },
          // Note that we also pass a flag so that we know we shouldn't
          // adjust the `originPosition` and `originSize` in our handlers.
          { skipParentHandler: true },
        );
      }
    }
  });
  /** --- end 分组节点内子节点拖动时自动调整尺寸 --- */
};
