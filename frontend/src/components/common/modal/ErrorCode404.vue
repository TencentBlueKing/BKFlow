<template>
  <bk-exception
    class="exception-wrap"
    type="404">
    <p class="title">
      {{ $t('找不到页面') }}
    </p>
    <p class="sub-title">
      {{ $t('仅提供从已认证平台发起访问') }}
    </p>
    <p class="sub-title">
      {{ $t('不支持直接请求本系统页面') }}
    </p>
    <p class="sub-title">
      {{ $t('如有接入需求，请联系管理员') }}
    </p>
  </bk-exception>
</template>

<script>
  export default {
    name: 'ErrorCode404',
  };
</script>

<style lang="scss" scoped>
  .exception-wrap {
    padding-top: 150px;
    ::v-deep .bk-exception-img {
      width: 440px;
      height: 200px;
    }
    .title {
      font-size: 24px;
      color: #313238;
      margin-bottom: 12px;
    }
    .sub-title {
      font-size: 14px;
      color: #63656e;
    }
  }
</style>
