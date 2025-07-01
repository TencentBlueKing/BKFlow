/**
 * 横版画布自定义画布路由
 */

const padding = 20;

export default (vertices, args, view) => {
  const points = [];
  const { sourceAnchor, targetAnchor } = view;
  const { sourcePort, targetPort } = args;

  switch (sourcePort) {
    case 'port_right':
      if (targetPort === 'port_bottom') {
        points.push({ x: targetAnchor.x, y: sourceAnchor.y });
      }
      break;
    case 'port_bottom':
      if (targetPort === 'port_bottom') {
        points.push(
          { x: sourceAnchor.x, y: sourceAnchor.y + padding },
          { x: targetAnchor.x, y: sourceAnchor.y + padding },
        );
      } else {
        points.push({ x: sourceAnchor.x, y: targetAnchor.y });
      }
      break;
  }

  return points;
};
