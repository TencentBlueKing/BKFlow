/**
 * 竖版画布自定义画布路由
 */

const getNodeType = (vm) => {
  const { _vnode: node } = vm;
  return node.data.node.store.data.data.type;
};

const isMultiOutputGatewayNode = type => ['branch-gateway', 'parallel-gateway', 'conditional-parallel-gateway'].includes(type);

export default (vertices, args, view) => {
  const points = [];
  const { sourceAnchor, sourceView, targetAnchor, targetView } = view;
  const sourceType = getNodeType(sourceView.vm);
  const targetType = getNodeType(targetView.vm);
  if (sourceAnchor.x !== targetAnchor.x) {
    if (isMultiOutputGatewayNode(sourceType)) {
      points.push({ x: targetAnchor.x, y: sourceAnchor.y });
    } else if (targetType === 'converge-gateway') {
      points.push({ x: sourceAnchor.x, y: targetAnchor.y });
    }
  }

  return points;
};
