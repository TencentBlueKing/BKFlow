
// 分组节点padding
const embedPadding = 20;

export const registryEvents = (graph) => {
  // 节点新增/删除时更新父组群尺寸坐标
  const updateParent = (cell) => {
    if (cell.shape === 'edge') return;

    const parent = cell.data.type === 'group' ? cell : cell.parent;
    if (!parent) return;

    let minX = Infinity;
    let maxX = -Infinity;
    let maxXNodeWidth = 0;
    let minY = Infinity;
    let maxY = -Infinity;
    let maxYNodeHeight = 0;
    // 遍历所有子节点
    parent.getDescendants().forEach((child) => {
      if (child.shape === 'edge' || child.getChildCount()) return;
      const { x, y } = child.position();
      const { width, height } = child.size();
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      if (x > maxX) {
        maxX = x;
        maxXNodeWidth = width;
      } else if (x === maxX) {
        maxXNodeWidth = Math.max(maxXNodeWidth, width);
      }
      if (y > maxY) {
        maxY = y;
        maxYNodeHeight = height;
      } else if (y === maxY) {
        maxYNodeHeight = Math.max(maxYNodeHeight, height);
      }
    });
    const width = maxX - minX + maxXNodeWidth + embedPadding * 2;
    const height = maxY - minY + maxYNodeHeight + embedPadding * 2;
    const left = minX - embedPadding;
    const top = minY - embedPadding;
    parent.prop({
      position: { x: left, y: top },
      size: { width, height },
    });
    const parentCell = cell.parent || graph.getCellById(cell.data.parent);
    if (parentCell) {
      updateParent(parentCell);
    }
  };
  // 节点被挂载到画布上时触发
  graph.on('view:mounted', ({ view }) => {
    const { cell } = view;
    updateParent(cell);
  });
  // 节点被删除时触发
  graph.on('node:removed', ({ cell }) => {
    updateParent(cell);
  });
  // 节点移动时触发
  graph.on('node:change:position', ({ cell }) => {
    updateParent(cell);
  });
};
