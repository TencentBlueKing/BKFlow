<template>
  <div
    v-show="visible"
    class="image-viewer-modal">
    <div
      class="mask"
      @click="handleClose" />
    <!-- 预览内容区 -->
    <div class="viewer-content">
      <!-- 控制栏：缩放、旋转、关闭 -->
      <div class="controls">
        <bk-button
          @click="handleZoom(0.1)">
          {{ $t("放大") }}
        </bk-button>
        <bk-button @click="handleZoom(-0.1)">
          {{ $t("缩小") }}
        </bk-button>
        <bk-button @click="handleClose">
          {{ $t("关闭") }}
        </bk-button>
      </div>
      <!-- 图片容器：应用缩放样式 -->
      <div
        class="image-container"
        :style="{ transform: `scale(${scale})` }">
        <img
          :src="imageUrl"
          :alt="$t('凭证指引')"
          class="preview-image">
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ImageViewer',
  props: {
    imageUrl: {
      type: String,
      required: true,
    },
    visible: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      scale: 1,
    };
  },
  methods: {
    // 缩放图片
    handleZoom(factor) {
      const newScale = this.scale + factor;
      // 限制缩放范围（0.5 ~ 3 倍）
      if (newScale >= 0.5 && newScale <= 3) {
        this.scale = newScale;
      }
    },
    // 关闭预览
    handleClose() {
      this.$emit('update:visible', false);
      // 重置缩放
      this.scale = 1;
    },
  },
};
</script>

<style lang="scss" scoped>
.image-viewer-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 9999;
  .mask {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.8);
  }
  .viewer-content {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 20px;
    box-sizing: border-box;
    .controls {
      position: absolute;
      top: 20px;
      left: 50%;
      transform: translateX(-50%);
      display: flex;
      gap: 10px;
      z-index: 1;
    }

    .image-container {
      max-width: 90%;
      max-height: 90vh;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.3s ease;
      .preview-image {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
      }
    }
  }
}
</style>
