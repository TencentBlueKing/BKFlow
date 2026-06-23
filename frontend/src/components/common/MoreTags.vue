<template>
  <div class="more-tags">
    <bk-tag
      v-for="tag in visibleTags"
      :key="tag">
      <slot
        name="tag"
        :tag="tag">
        {{ tag }}
      </slot>
    </bk-tag>
    <bk-popover
      v-if="hiddenTags.length > 0"
      theme="light"
      :max-width="500">
      <bk-tag class="more-tag">
        {{ `+${hiddenTags.length}` }}
      </bk-tag>
      <template #content>
        <div class="more-tags-content">
          <bk-tag
            v-for="tag in hiddenTags"
            :key="tag">
            <slot
              name="tag"
              :tag="tag">
              {{ tag }}
            </slot>
          </bk-tag>
        </div>
      </template>
    </bk-popover>
  </div>
</template>
<script>
  import { mapState } from 'vuex';
  export default {
    props: {
      width: {
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
        observer: null,
      };
    },
    computed: {
      ...mapState({
          isMultiTenantMode: state => state.isMultiTenantMode,
      }),
    },
    watch: {
      width: {
        handler(val) {
          if (!val) return;
          this.getVisibleTags();
        },
        immediate: true,
      },
      tags() {
        this.getVisibleTags();
      },
    },
    mounted() {
      this.getVisibleTags();
      if (this.isMultiTenantMode) {
        this.observer = new MutationObserver(() => {
          this.getVisibleTags();
        });
        // 监听整个组件 DOM 的变化
        this.observer.observe(this.$el, {
          childList: true,
          subtree: true,
          characterData: true,
          attributes: true,
        });
      }
    },
    beforeDestroy() {
      // 清理 MutationObserver
      if (this.observer) {
        this.observer.disconnect();
        this.observer = null;
      }
    },
    methods: {
      getVisibleTags() {
        try {
          // 计算前先断开observer，避免修改DOM后触发observer形成循环
          if (this.observer) {
            this.observer.disconnect();
          }

          const { tags } = this;

          if (!tags?.length) {
            this.visibleTags = [];
            this.hiddenTags = [];
            return;
          }

          // 预计算所有原始标签的宽度
          const tagWidths = tags.map(tag => this.createTagDom(tag));

          let foldIndex = tags.length; // 未触发折叠时返回 tags.length
          let remainingWidth = this.width;
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
        } finally {
          this.$nextTick(() => {
            if (this.observer && this.isMultiTenantMode) {
              this.observer.observe(this.$el, {
                childList: true,
                subtree: true,
                characterData: true,
                attributes: true,
              });
            }
          });
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
<style lang="scss" scoped>
  .more-tags {
    display: flex;
    .bk-tag,
    .bk-tooltip {
      flex-shrink: 0;
    }
  }
</style>
