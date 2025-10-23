<template>
  <div class="valueRender">
    <!-- 渲染进度条 -->
    <template v-if="renderItem.hasProgress">
      <div
        class="progress-wrapper"
        :class="{
          'progress-link': renderItem.hasLink
        }"
        @click.stop="openLink(renderItem.linkUrl)">
        <div class="progress-text">
          <span
            v-bk-tooltips="{
              disabled:!renderItem.key,
              content: renderItem.key,
            }"
            class="progress-done value-key word-elliptic">{{ renderItem.key }} </span>
          <div class="progress-container">
            <div
              class="progress-bar"
              :style="{
                width: progressCurrentPercent + '%',
                backgroundColor: renderItem.progess.progressColor || '#3A83FF'
              }" />
          </div>
          <span
            class="progress-total">{{ renderItem.value }}/{{ renderItem.progess.Range[1] }}</span>
        </div>
      </div>
    </template>

    <!-- 渲染高亮 -->
    <template v-else-if="!renderItem.hasProgress">
      <span
        class="highlighted-value"
        :style="{
          color: renderItem.text.color || '#4D4F56',
          fontWeight: renderItem.text.highlightStyle === 'bold' ? 'bold' : 'normal',
          backgroundColor: renderItem.text.highlightBg || 'transparent',
          ...renderItem.text.highlightStyle
        }"
        @click.stop.prevent="openLink(renderItem.linkUrl)">
        <template v-if="renderItem.hasLink">
          <a
            :href="renderItem.linkUrl"
            target="_blank"
            class="value-link">
            <span
              v-bk-tooltips="{
                disabled:!renderItem.key,
                content: renderItem.key,
              }"
              class="value-key word-elliptic">{{ renderItem.key }}</span>
            <span class="value-Item">{{ renderItem.value }}</span>
          </a>
        </template>
        <template v-else>
          <span
            v-bk-tooltips="{
              disabled:!renderItem.key,
              content: renderItem.key,
            }"
            class="value-key word-elliptic">{{ renderItem.key }}</span>
          <span class="value-Item">{{ renderItem.value }}</span>
        </template>
      </span>
    </template>
  </div>
</template>
<script>
 export default {
    props: {
        renderItem: {
          type: Object,
          default: () => ({
          key: 'label',
          value: 23,
          hasProgress: false,
          hasLink: false,
          linkUrl: '',
          text: {
            color: '#4D4F56',
            highlightStyle: {},
            highlightBg: '',
          },
          progess: {
            progressColor: '',
            Range: [0, 100],
          },
        }),
        },
    },
    computed: {
      progressCurrentPercent() {
        if (this.renderItem.value === '--' || this.renderItem.progess.Range.includes('--')) {
          return 0;
        }
           return ((this.renderItem.value - this.renderItem.progess.Range[0]) / (this.renderItem.progess.Range[1] - this.renderItem.progess.Range[0])) * 100;
      },
    },
    methods: {
      openLink(link) {
        if (link) {
          window.open(link);
        }
      },
    },
 };
</script>
<style lang="scss" scoped>
.valueRender{
  font-size: 12px;
  font-weight: 500;
}
a{
    text-decoration: none;
    cursor: pointer;
    &
    &:active {
      color: unset;
    }
    &:focus {
      color: unset;
    }
    &:-webkit-any-link {
      color: unset;
    }
}
.progress-wrapper {
    display: flex;
    flex-direction: column;
    gap: 5px;
}
.progress-link{
  &:hover{
    .progress-done{
      color: #3A83FF;
    }
    .progress-total{
      color: #3A83FF;
    }
  }

}
.progress-container {

    background-color: rgba(58, 131, 255, 0.1); /* 淡蓝色背景 */
    border-radius: 5px;
    flex: 1;
    width: 0;
    margin: 8px;
    overflow: hidden;
    height: 8px; /* 略微增加高度 */
}
.progress-bar {
    height: 100%;
    background-color: #3A83FF; /* 更新为与边框一致的蓝色 */
    border-radius: 5px;
}
.progress-text {
    font-size: 12px;
    color: #4D4F56;
    display: flex;
    // justify-content: space-between;
    align-items: center;
}
.progress-text .progress-done {
    color: #4D4F56;
    font-weight: 500;
}
.progress-text .progress-total {
    color: #4D4F56;
}
.word-elliptic{
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

.value-link {
    color: #3A83FF;
    text-decoration: none;
    display: flex;
    justify-content: space-between;
    width: 100%;
    cursor: pointer;
    &:hover {
      color: #3A83FF;
    }
}
.highlighted-value{
  line-height: 1.5;
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
  width: 100%;
  .value-key{
    flex: 1;
    min-width: 65px;
  }
}
.value-key{
  display: inline-block;
}
.value-Item{
  white-space: pre-line;
}
</style>
