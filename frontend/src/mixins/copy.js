

import i18n from '@/config/i18n/index.js';

const copy = {
  data() {
    return {
      copyText: '',
    };
  },
  methods: {
    // 复制
    onCopyKey(key) {
      this.copyText = key;
      document.addEventListener('copy', this.copyHandler);
      document.execCommand('copy');
      document.removeEventListener('copy', this.copyHandler);
      this.copyText = '';
    },
    // 复制操作回调函数
    copyHandler(e) {
      e.preventDefault();
      e.clipboardData.setData('text/html', this.copyText);
      e.clipboardData.setData('text/plain', this.copyText);
      this.$bkMessage({
        message: i18n.t('已复制'),
        theme: 'success',
      });
    },
  },
};
export default copy;
