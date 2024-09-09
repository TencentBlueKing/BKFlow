// 接口异常通知提示
import i18n from '@/config/i18n/index.js';
import bus from '@/utils/bus.js';
export default class ErrorNotify {
  constructor(errorInfo, vueInstance) {
    const { msg, type, traceId, errorSource, title } = errorInfo;
    this.type = type;
    // 标题
    const msgTitle = title || this.getTitleAndContent(msg, true, errorSource);

    // 详情
    let details = {};
    const msgLabel = type === 'success' ? 'success_msg' : 'error_msg';
    details[msgLabel] = this.getTitleAndContent(msg, false, errorSource);
    if (traceId) {
      details.trace_id = traceId;
    }
    details = JSON.stringify(details);

    // 助手
    const helperUrl = type === 'success' ? '' : window.MESSAGE_HELPER_URL || '';

    // 工具列表
    const actions = [
      { id: 'assistant', disabled: !helperUrl },
      { id: 'details' },
      { id: 'fix' },
      { id: 'close' },
    ];
    const errorMsgInstance = vueInstance.$bkMessage({
      message: {
        title: msgTitle,
        details,
        assistant: helperUrl,
        type: 'key-value',
      },
      actions,
      theme: type,
      ellipsisLine: 2,
      ellipsisCopy: true,
      extCls: 'interface-exception-notify-message',
      onClose: () => {
        const index = window.msg_list.findIndex(item => item.msg === msg);
        if (index > -1) {
          window.msg_list.splice(index, 1);
        }
        bus.$emit('onCloseErrorNotify', details);
      },
    });
    vueInstance.errorMsgList.push(errorMsgInstance);
  }
  getTitleAndContent(info, isTitle, errorSource) {
    let content = isTitle ? '' : info;
    if (isTitle && !content) {
      content = errorSource === 'result'
        ? i18n.t('请求异常（外部系统错误或非法操作）')
        : i18n.t('请求异常（内部系统发生未知错误）');
      content = this.type === 'success' ? i18n.t('请求成功') : content;
    }
    return content;
  }
}
