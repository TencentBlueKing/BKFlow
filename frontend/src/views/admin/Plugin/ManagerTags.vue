<template>
  <div class="manager-tags">
    <bk-tag
      v-for="tag in visibleTags"
      :key="tag">
      {{ tag }}
    </bk-tag>
    <bk-popover
      v-if="hiddenTags.length > 0"
      theme="light"
      :max-width="500">
      <bk-tag
        ref="moreTagRef"
        class="more-tag">
        +{{ hiddenTags.length }}
      </bk-tag>
      <template #content>
        <div class="more-tags-content">
          <bk-tag
            v-for="tag in hiddenTags"
            :key="tag">
            {{ tag }}
          </bk-tag>
        </div>
      </template>
    </bk-popover>
  </div>
</template>
<script>
  export default {
    props: {
      columnWidth: {
        type: Number,
        default: 0,
      },
      tags: {
        type: Array,
        default: () => ([]),
      },
    },
    data() {
      return {
        visibleTags: [],
        hiddenTags: [],
      };
    },
    watch: {
      columnWidth: {
        handler(val) {
          if (!val) return;
          this.getVisibleTags();
        },
        immediate: true,
      },
    },
    methods: {
      getVisibleTags() {
        try {
          const { tags } = this;
          if (!tags?.length) return;

          // 预计算所有原始标签的宽度
          const tagWidths = tags.map(tag => this.createTagDom(tag));

          let foldIndex = tags.length; // 未触发折叠时返回 tags.length
          let remainingWidth = this.columnWidth;
          const spacing = 6;

          // 计算折叠后的剩余数量
          for (let i = 0; i < tags.length; i++) {
            const currentWidth = tagWidths[i] + spacing;

            if (currentWidth < remainingWidth) {
              remainingWidth -= currentWidth;
            } else {
              const foldTagWidth = this.createTagDom(`+${tags.length - i}`);

              foldIndex = foldTagWidth < remainingWidth ? i : i - 1;
              break;
            }
          }

          this.visibleTags = tags.slice(0, foldIndex);
          this.hiddenTags = tags.slice(foldIndex);
        } catch (e) {
          console.error(e);
        }
      },
      createTagDom(val) {
        const tagDom = document.createElement('span');
        tagDom.style.display = 'inline-block';
        tagDom.style.padding = '0 10px';
        tagDom.style.fontSize = '12px';
        tagDom.innerText = val;
        document.body.appendChild(tagDom);
        const width = tagDom.offsetWidth;
        document.body.removeChild(tagDom);

        return width;
      },
    },
  };
</script>
