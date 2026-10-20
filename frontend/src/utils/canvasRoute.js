/**
 * 根据空间配置 canvas_mode 决定查看流程时使用新版画布（FlowDetail）还是旧版画布
 */
import store from '@/store/index.js';
import { fetchFlowDetail } from '@/views/template/TemplateEdit/flowEditApi.js';

/**
 * 获取查看流程的目标路由
 */
export async function getCanvasRoute(templateId, spaceId, query) {
  let sid = spaceId;
  if (!sid) {
    try {
      const detail = await fetchFlowDetail(templateId);
      sid = detail?.['space_id'];
    } catch (e) {
      console.warn(e);
      return { name: 'templatePanel', params: { type: 'view', templateId }, query };
    }
  }
  let canvasMode = 'horizontal';
  try {
    canvasMode = await store.dispatch('loadCanvasMode', sid);
  } catch (e) {
    console.warn(e);
  }
  if (canvasMode === 'horizontal') {
    return { name: 'templateDetail', params: { templateId }, query };
  }
  return { name: 'templatePanel', params: { type: 'view', templateId }, query };
}

/**
 * 获取目标路由后直接跳转
 */
export async function jumpToCanvas(router, templateId, spaceId, query) {
  const route = await getCanvasRoute(templateId, spaceId, query);
  await router.push(route);
}

