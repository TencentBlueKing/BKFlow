<template>
  <div class="template-page-header">
    {{ $t('头部区域') }}
  </div>
</template>
<script>
  export default {
    name: 'TemplatePageHeader',
  };
</script>
<style lang="scss" scoped>
  .template-page-header {
    position: relative;
    height: 48px;
    border-bottom: 1px solid #dcdee5;
    -webkit-box-shadow: 0 3px 4px 0 rgba(64,112,203,.06);
    box-shadow: 0 3px 4px 0 rgba(64,112,203,.06);
    background: #fff;
    z-index: 101;
  }
</style>
