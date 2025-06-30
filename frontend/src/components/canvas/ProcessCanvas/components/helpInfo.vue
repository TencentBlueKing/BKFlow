<template>
  <div
    v-if="isShowHotKey"
    class="help-info-wrap">
    <transition name="wrapperLeft">
      <div :class="['hot-key-panel', { 'min-top': !editable }]">
        <p class="title">
          {{ commonTitle + $t('快捷键列表') }}
        </p>
        <span
          class="close"
          @click.stop="$emit('onCloseHotkeyInfo')">
          <i class="common-icon-dark-circle-close" />
        </span>
        <table>
          <tbody>
            <tr>
              <td>{{ $t('放大') }}:</td>
              <td>Ctrl + (+)</td>
            </tr>
            <tr>
              <td>{{ $t('缩小') }}:</td>
              <td>Ctrl + (-)</td>
            </tr>
            <tr>
              <td>{{ $t('还原') }}:</td>
              <td>Ctrl + 0:</td>
            </tr>
            <tr>
              <td>{{ $t('缩放') }}:</td>
              <td>Ctrl + {{ $t('鼠标滚动') }}</td>
            </tr>
            <template v-if="editable">
              <tr>
                <td>{{ $t('连续选中（或取消）节点') }}:</td>
                <td>{{ commonCtrl }} + {{ $t('鼠标左键单击') }}</td>
              </tr>
              <tr>
                <td>{{ $t('移动流程元素') }}:</td>
                <td>[{{ $t('选中后') }}]{{ $t('箭头（上下左右）') }}</td>
              </tr>
              <tr>
                <td>{{ $t('删除节点') }}:</td>
                <td>[{{ $t('选中后') }}] Delete</td>
              </tr>
              <tr>
                <td>{{ $t('复制/粘贴') }}:</td>
                <td>[{{ $t('选中后') }}] Ctrl + C / Ctrl + V</td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </transition>
  </div>
</template>
<script>
  const isMac = /macintosh|mac os x/i.test(navigator.userAgent.toLowerCase());
  export default {
    name: 'HelpInfo',
    props: {
      isShowHotKey: {
        type: Boolean,
        default: false,
      },
      editable: {
        type: Boolean,
        default: true,
      },
    },
    data() {
      return {
        isMac,
        commonTitle: isMac ? 'Mac' : 'Windows',
        commonCtrl: isMac ? 'Command' : 'Ctrl',
      };
    },
  };
</script>
<style lang="scss" scoped>
.help-info-wrap {
  position: absolute;
  left: 0;
  top: 0;
  z-index: 5;
  .hot-key-panel {
    position: absolute;
    left: 0;
    top: 60px;
    padding: 20px;
    width: 340px;
    border-radius: 4px;
    background-color: #fafbfd;
    font-size: 12px;
    line-height: 17px;
    color: #63656e;
    transition: all 0.5s ease;
    box-shadow: 0px 0px 20px 0px rgba(0, 0, 0, 0.15);
    &.min-top {
      left: 40px;
      top: 70px;
    }
    .title {
      margin-bottom: 10px;
      font-weight: bold;
    }
    .close {
      display: inline-block;
      position: absolute;
      right: 10px;
      top: 10px;
      width: 16px;
      height: 16px;
      font-size: 16px;
      line-height: 16px;
      text-align: center;
      cursor: pointer;
      .common-icon-dark-circle-close {
          color: #c4c6cc;
      }
    }
    table {
      width: 100%;
    }
  }
}
</style>
