<template>
  <div
    ref="container"
    class="tag-container">
    <span
      v-for="tag in visibleTags"
      :key="tag.id"
      class="tag"
      :style="tagStyle(tag)">
      {{ tag.full_path }}
    </span>

    <bk-popover theme="light">
      <span
        v-if="hiddenTags.length"
        class="more">
        +{{ hiddenTags.length }}
      </span>
      <template #content>
        <div class="tooltip">
          <span
            v-for="tag in hiddenTags"
            :key="tag.id"
            class="tag"
            :style="tagStyle(tag)">
            {{ tag.full_path }}
          </span>
        </div>
      </template>
    </bk-popover>
    <div
      ref="measure"
      class="measure">
      <span
        v-for="tag in tags"
        :key="tag.id"
        class="tag"
        :style="tagStyle(tag)">
        {{ tag.full_path }}
      </span>
    </div>
  </div>
</template>

<script>
export default {
    name: 'TagOverflow',

    props: {
        tags: {
            type: Array,
            default: () => [],
        },
    },

    data() {
        return {
            visibleTags: [],
            hiddenTags: [],
        };
    },

    watch: {
        tags: {
            deep: true,
            handler() {
                this.$nextTick(this.calcOverflow);
            },
        },
    },

    mounted() {
        this.$nextTick(this.calcOverflow);
        window.addEventListener('resize', this.calcOverflow);
    },

    beforeDestroy() {
        window.removeEventListener('resize', this.calcOverflow);
    },

    methods: {
        tagStyle(tag) {
            return {
                background: tag.color,
                color: '#fff',
            };
        },

        calcOverflow() {
            if (!this.tags.length) {
                this.visibleTags = [];
                this.hiddenTags = [];
                return;
            }

            const containerWidth = this.$refs.container.offsetWidth;
            const tagNodes = this.$refs.measure.children;

            let usedWidth = 0;
            const visible = [];
            const hidden = [];

            for (let i = 0; i < tagNodes.length; i++) {
                const width = tagNodes[i].offsetWidth + 6;
                if (usedWidth + width <= containerWidth) {
                    usedWidth += width;
                    visible.push(this.tags[i]);
                } else {
                    hidden.push(this.tags[i]);
                }
            }

            // 给 +N 预留空间（核心）
            if (hidden.length && visible.length) {
                const last = visible.pop();
                hidden.unshift(last);
            }

            this.visibleTags = visible;
            this.hiddenTags = hidden;
        },
    },
};
</script>
<style lang="scss">
.tag-container {
    position: relative;
    display: flex;
    align-items: center;
    white-space: nowrap;
    overflow: hidden;
    width: 242px;
}

.tag {
    display: inline-block;
    padding: 2px 6px;
    margin-right: 4px;
    background: #f0f2f5;
    border-radius: 11px;
    font-size: 12px;
}

.more {
    display: inline-block;
    width: 21px;
    height: 16px;
    background: #c4c6cc;
    border-radius: 11px;
    line-height: 16px;
    text-align: center;
    color: #FFFFFF;
}

.tooltip {
    display: flex;
    flex-direction: column;
    gap: 6px;
    color: #fff;
    white-space: normal;
    padding: 0 4px;
    border-radius: 11px;
    color: #ffffff;
    font-size: 10px;
    max-height: 120px;
    overflow: auto;
}

.measure {
    position: absolute;
    visibility: hidden;
    white-space: nowrap;
    height: 0;
    overflow: hidden;
}
</style>
