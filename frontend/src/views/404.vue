<template>
  <div class="exception-box">
    <img
      src="https://magicbox.bk.tencent.com/static_api/v3/components/exception_building/images/building.png"
      alt="">
    <p>{{ $t('没找到页面！') }}</p>
  </div>
</template>

<script>
  export default {
    data() {
      return {};
    },
  };
</script>
<style scoped lang="scss">
  .exception-box {
    text-align: center;
    margin: 0 auto;

    img {
      width: 300px;
      margin-top: 150px;
    }
  }
</style>
