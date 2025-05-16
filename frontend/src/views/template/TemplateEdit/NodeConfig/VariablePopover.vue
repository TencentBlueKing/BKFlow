<template>
  <bk-popover
    ext-cls="variable-popover"
    class="view-variable"
    placement="bottom-end"
    :tippy-options="{ hideOnClick: false }">
    <div style="cursor: pointer;">
      {{ $t('全局变量') }}
    </div>
    <div
      slot="content"
      class="variable-list">
      <div class="header-area">
        <span>{{ $t('全局变量') }}</span>
        <bk-link
          v-if="!isViewMode"
          theme="primary"
          icon="bk-icon icon-plus"
          @click="openVariablePanel()">
          {{ $t('新建变量') }}
        </bk-link>
      </div>
      <bk-table
        :data="variableList"
        :outer-border="false"
        :max-height="400">
        <bk-table-column
          :label="$t('名称')"
          prop="name"
          width="165">
          <div
            slot-scope="props"
            v-bk-overflow-tips>
            {{ props.row.name }}
          </div>
        </bk-table-column>
        <bk-table-column
          label="KEY"
          width="209">
          <template
            slot-scope="props"
            width="165">
            <div
              v-bk-overflow-tips
              class="key">
              {{ props.row.key }}
            </div>
            <i
              class="copy-icon common-icon-double-paper-2"
              @click="onCopyKey(props.row.key)" />
          </template>
        </bk-table-column>
        <bk-table-column
          :label="$t('属性')"
          width="80">
          <div
            slot-scope="props"
            class="icon-wrap">
            <i
              v-bk-tooltips="{
                content: props.row.source_type !== 'component_outputs' ? $t('输入') : $t('输出'),
                placements: ['bottom']
              }"
              :class="[
                props.row.source_type !== 'component_outputs'
                  ? 'common-icon-show-left'
                  : 'common-icon-show-right color-org'
              ]" />
            <i
              v-bk-tooltips="{
                content: props.row.show_type === 'show' ? $t('显示') : $t('隐藏'),
                placements: ['bottom']
              }"
              :class="[
                props.row.show_type === 'show' ? 'common-icon-eye-show' : 'common-icon-eye-hide color-org'
              ]" />
          </div>
        </bk-table-column>
        <bk-table-column
          v-if="!isViewMode"
          :label="$t('操作')"
          width="80">
          <template slot-scope="props">
            <bk-link
              :theme="props.row.source_type === 'system' ? 'default' : 'primary'"
              :disabled="props.row.source_type === 'system'"
              @click="openVariablePanel(props.row)">
              {{ $t('编辑') }}
            </bk-link>
          </template>
        </bk-table-column>
        <div
          slot="empty"
          class="empty-data">
          <NoData />
        </div>
      </bk-table>
    </div>
  </bk-popover>
</template>

<script>
  import NoData from '@/components/common/base/NoData.vue';
  export default {
    name: 'VariablePopover',
    components: {
      NoData,
    },
    props: {
      isViewMode: {
        type: Boolean,
        default: true,
      },
      variableList: {
        type: Array,
        default: () => ([]),
      },
    },
    methods: {
      openVariablePanel(val) {
        this.$emit('openVariablePanel', val);
      },
      /**
       * 变量 key 复制
       */
      onCopyKey(key) {
        this.copyText = key;
        document.addEventListener('copy', this.copyHandler);
        document.execCommand('copy');
        document.removeEventListener('copy', this.copyHandler);
        this.copyText = '';
      },
      /**
       * 复制操作回调函数
       */
      copyHandler(e) {
        e.preventDefault();
        e.clipboardData.setData('text/html', this.copyText);
        e.clipboardData.setData('text/plain', this.copyText);
        this.$bkMessage({
          message: this.$t('已复制'),
          theme: 'success',
        });
      },
    },
  };
</script>

<style lang="scss" scoped>
.view-variable {
  position: absolute;
  top: 20px;
  right: 20px;
  font-size: 14px;
  line-height: 19px;
  font-weight: normal;
  &:hover {
      color: #3a84ff;
  }
  &.r30 {
      right: 30px;
  }
}
</style>
<style lang="scss">
.variable-popover {
  .tippy-tooltip {
    padding: 0;
    .tippy-arrow {
      border: none;
    }
  }
  .variable-list {
    width: 536px;
    background: #ffffff;
    border: 1px solid #dcdee5;
    box-shadow: 0 4px 12px 0 rgba(0, 0, 0, 0.2);
    ::v-deep .bk-table-body-wrapper {
      overflow-y: auto;
    }
    .icon-wrap {
      i {
        margin-right: 4px;
        color: #219f42;
        font-size: 14px;
    }
      .color-org {
        color: #de9524;
      }
    }
    .header-area {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 14px;
      height: 48px;
      & > span {
        font-size: 14px;
        color: #313238;
      }
      i {
        font-size: 18px;
      }
    }
    .bk-link-text {
      font-size: 12px;
    }
  }
  td {
    position: relative;
    &:hover {
      .copy-icon {
        display: inline-block;
      }
    }
  }
  .copy-icon {
    display: none;
    position: absolute;
    top: 14px;
    right: 2px;
    font-size: 14px;
    cursor: pointer;
    &:hover {
      color: #3a84ff;
    }
  }
}
</style>
