<template>
  <bk-dialog
    v-model="visible"
    v-bind="dialogProps"
    width="1105"
    :show-footer="false">
    <template>
      <div
        v-bkloading="{ isLoading: loading, zIndex: 100 }"
        class="log-version">
        <div class="log-version-left">
          <ul class="left-list">
            <li
              v-for="(item, index) in logList"
              :key="index"
              class="left-list-item"
              :class="{ 'item-active': index === active }"
              @click="handleItemClick(index)">
              <slot>
                <span class="item-title">{{ item[0] }}</span>
                <span class="item-date">{{ item[1] }}</span>
                <span
                  v-if="index === 0"
                  class="item-current">{{ $t('当前版本') }}</span>
              </slot>
            </li>
          </ul>
        </div>
        <div class="log-version-right">
          <slot name="detail">
            <div
              :class="['detail-container', { 'markdown-theme-style': mdMode }]"
              v-html="content" />
          </slot>
        </div>
      </div>
    </template>
  </bk-dialog>
</template>
<script>
  import { bkDialog, bkLoading } from 'bk-magic-vue';
  import { marked } from 'marked';

  export default {
    name: 'BkMagicLogVersion',
    components: {
      bkDialog,
    },
    directives: {
      bkloading: bkLoading.directive,
    },
    props: {
      logList: {
        type: Array,
        default: () => ([]),
      },
      logDetail: {
        type: String,
        default: '',
      },
      mdMode: Boolean,
      loading: Boolean,
      dialogProps: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        visible: false,
        active: 0,
      };
    },
    computed: {
      content() {
        if (this.mdMode) {
          return marked(this.logDetail);
        }
        return this.logDetail;
      },
    },
    watch: {
      logList: {
        immediate: true,
        handler(logList) {
          if (logList.length) {
            this.handleItemClick(0);
          }
        },
      },
    },
    beforeDestroy() {
      this.show = false;
      this.$emit('update:dialogShow', false);
    },
    methods: {
      toggleVisible(value) {
        value ? this.show() : this.hide();
      },
      show() {
        this.visible = true;
      },
      hide() {
        this.visible = false;
      },
      handleItemClick(index) {
        this.active = index;
        this.$emit('active-change', this.logList[index]);
      },
    },
  };
</script>
<style lang="scss" scoped>
  .log-version {
    display: flex;
    margin: -33px -24px -26px;
    &-left {
      flex: 0 0 180px;
      background-color: #FAFBFD;
      border-right: 1px solid #DCDEE5;
      padding: 40px 0;
      display: flex;
      font-size: 12px;
      .left-list {
        border-top: 1px solid #DCDEE5;
        border-bottom: 1px solid #DCDEE5;
        height: 520px;
        overflow: auto;
        display: flex;
        flex-direction: column;
        width: 100%;
        &-item {
          flex: 0 0 54px;
          display: flex;
          flex-direction: column;
          justify-content: center;
          padding-left: 30px;
          position: relative;
          border-bottom: 1px solid #DCDEE5;
          &:hover {
            cursor: pointer;
            background-color: #FFFFFF;
          }
          .item-title {
            color: #313238;
            font-size: 16px;
          }
          .item-date {
            color: #979BA5;
          }
          .item-current {
            position: absolute;
            right: 20px;
            top: 8px;
            background-color: #699DF4;
            border-radius: 2px;
            width: 58px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #FFFFFF;
          }
          &.item-active {
            &::before {
              content: " ";
              position: absolute;
              top: 0px;
              bottom: 0px;
              left: 0;
              width: 6px;
              background-color: #3A84FF;
            }
            background-color: #FFFFFF;
          }
        }
      }
    }
    &-right {
      flex: 1;
      padding: 25px 30px 50px 45px;
      .markdown-container {
        max-height: 525px;
        overflow: auto;
      }
    }
  }
  .detail-container {
    max-height: 525px;
    overflow: auto;
  }
</style>
<style lang="scss">
  @import '../../scss/markdown-theme.scss';
</style>
