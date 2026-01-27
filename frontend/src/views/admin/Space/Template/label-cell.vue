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
    <bk-popover
      ext-cls="label-cell-popover"
      theme="light">
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
            v-bk-overflow-tips
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
            const tagNodes = Array.from(this.$refs.measure.children);
            const tagInfos = tagNodes.map((node, index) => ({
                tag: this.tags[index],
                width: node.offsetWidth + 6,
                index,
            }));
            // 优先展示tag宽度小的
            tagInfos.sort((a, b) => a.width - b.width);
            let usedWidth = 0;
            const visible = [];
            const hidden = [];
            for (const info of tagInfos) {
                if (usedWidth + info.width <= containerWidth) {
                    usedWidth += info.width;
                    visible.push(info);
                } else {
                    hidden.push(info);
                }
            }
            if (hidden.length && visible.length) {
                const last = visible.pop();
                hidden.unshift(last);
            }
            this.visibleTags = visible
                .sort((a, b) => a.index - b.index)
                .map(i => i.tag);
            this.hiddenTags = hidden
                .sort((a, b) => a.index - b.index)
                .map(i => i.tag);
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
    padding: 0 4px;
    margin-right: 4px;
    background: #f0f2f5;
    border-radius: 11px;
    font-size: 12px;
    line-height: 16px;
}

.more {
    display: inline-block;
    padding: 0 4px;
    height: 16px;
    background: #c4c6cc;
    border-radius: 11px;
    line-height: 16px;
    text-align: center;
    color: #ffffff;
}

.tooltip {
    display: flex;
    flex-direction: column;
    gap: 6px;
    color: #fff;
    border-radius: 11px;
    color: #ffffff;
    font-size: 10px;
    max-height: 126px;
    overflow: auto;
    .tag {
        align-self: flex-start;
        margin: 0;
        white-space: nowrap;
        overflow: hidden;
    }
}

.measure {
    position: absolute;
    visibility: hidden;
    white-space: nowrap;
    height: 0;
    overflow: hidden;
}
</style>

<style>
    .label-cell-popover {
    .tippy-tooltip {
        padding: 8px;

    }
}
</style>
