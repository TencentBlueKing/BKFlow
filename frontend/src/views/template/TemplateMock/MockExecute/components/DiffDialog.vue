<template>
  <bk-dialog
    :width="480"
    :value="isDiffDialogShow"
    :mask-close="false"
    :auto-close="false"
    :render-directive="'if'"
    footer-position="center"
    :ok-text="$t('继续复用')"
    ext-cls="common-dialog diff-dialog"
    @confirm="$emit('confirm')"
    @cancel="$emit('cancel')">
    <template slot="header">
      <div class="warning-icon bk-icon icon-exclamation" />
      <p>{{ $t('调试数据已发生变化，请确认是否继续复用') }}</p>
    </template>
    <template>
      <i18n
        tag="div"
        path="mockReuseTips"
        class="tips-wrap">
        <span class="highlight">{{ $t('忽略') }}</span>
      </i18n>
      <table class="diff-table">
        <thead>
          <tr>
            <th>{{ $t('当前调试任务') }}</th>
            <th>{{ $t('待复用调试任务') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(item, index) in diffList"
            :key="index">
            <template v-if="item.isConstants">
              <td>{{ item.left.name || '--' }}</td>
              <td :class="{ 'is-deleted': !item.right.name, 'is-extra': !item.left.name }">
                {{ item.right.name || '--' }}
              </td>
            </template>
            <template v-else>
              <td>{{ item.left.name ? `${item.left.node_name}: ${item.left.name}` : '--' }}</td>
              <td :class="{ 'is-deleted': !item.right.name, 'is-extra': !item.left.name }">
                {{ getTdName(item.right) }}
              </td>
            </template>
          </tr>
        </tbody>
      </table>
    </template>
  </bk-dialog>
</template>
<script>
  export default {
    name: 'DiffDialog',
    props: {
      isDiffDialogShow: {
        type: Boolean,
        default: false,
      },
      diffList: {
        type: Array,
        default: () => ([]),
      },
    },
    data() {
      return {

      };
    },
    methods: {
      getTdName(data) {
        let name = data.name ? `${data.node_name}: ${data.name}` : `${data.node_name}: ID 为 【${data.id}】 的 mock 方案不存在`;
        name = !data.node_name ? '--' : name;
        return name;
      },
    },
  };
</script>
<style lang="scss">
  .diff-dialog .bk-dialog {
    .bk-dialog-header {
      padding: 7px 32px 16px;
      border-bottom: none;
    }
    .warning-icon {
      display: inline-block;
      height: 42px;
      width: 42px;
      line-height: 42px;
      margin-bottom: 19px;
      font-size: 22px;
      color: #FF9C01;
      background: #FFE8C3;
      border-radius: 50%;
    }
    .bk-dialog-body {
      padding: 0 32px;
      margin-bottom: 12px;
      .tips-wrap {
        padding: 12px 16px;
        background: #F5F6FA;
        border-radius: 2px;
        margin-bottom: 12px;
        .highlight {
          color: #FF9C01;
        }
      }
      .diff-table {
        width: 100%;
        border: 1px solid #dcdee5;
        border-collapse: collapse;
        border-radius: 2px;
        th, td {
          width: 50%;
          height: 32px;
          padding: 5px 16px;
          font-weight: normal;
          color: #63656e;
          border: none;
          border-bottom: 1px solid #dcdee5;
          border-right: 1px solid #dcdee5;
        }
        th {
          color: #313238;
          background: #f0f1f5;
          text-align: left;
        }
        td {
          font-size: 12px;
        }
        .is-deleted {
          background: #FFEEEE;
        }
        .is-extra {
          background: #F2FFF4;
        }
      }
    }
    .bk-dialog-footer {
      padding-bottom: 24px;
      border-top: none;
      background: #fff;
    }
  }
</style>
