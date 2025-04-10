<template>
  <bk-button
    text
    @click="setAuthorization">
    {{ row.status ? $t('取消授权') : $t('授权') }}
  </bk-button>
</template>
<script>
  import { mapActions } from 'vuex';
  export default {
    props: {
      row: {
        type: Object,
        default: () => ({}),
      },
    },
    methods: {
      ...mapActions('plugin', [
        'updatePluginManager',
      ]),
      // 授权/取消授权
      setAuthorization() {
        const { code, status, config } = this.row;
        const h = this.$createElement;

        const isAuthorize = status === 1;
        const titleMessage = this.$t(`${isAuthorize ? '确认取消授权？' : '确认授权？'}`);
        const successMessage = this.$t(`${isAuthorize ? '取消授权' : '授权'}成功`);
        const tipMessage  = status ? this.$t('取消后，流程配置页面将不能再看到对应的插件信息。') : this.$t('授权后，授权空间可以直接调用插件接口并执行插件功能。');
        const subTipMessage  = status
          ? this.$t('注意：对于已经配置在流程中的插件节点，BKFlow 仍然会触发调用。如果希望完全不提供给 BKFlow 调用，请直接在 PaaS 开发者中心取消对 BKFlow 的应用授权。')
          : this.$t('注意：空间下的执行人信息由 BKFlow 的对接系统管理并传入，BKFlow 仅进行信息传递，不保证执行人信息的真实性。请尽量保证插件仅适用于平台对接场景，勿把传递的执行人信息作为鉴权依据。');

          const dialogContent = [
            h('div', { style: { margin: '0 0 24px 0' } }, [
              this.$t('插件名称：'),
              h('span', { style: { color: '#313238' } }, code),
            ]),
            h('div', {
              style: {
                background: '#F5F6FA',
                borderRadius: '2px',
                padding: '12px 16px',
              },
            }, [
              h('div', { style: { marginBottom: '15px' } }, tipMessage),
              h('div', subTipMessage),
            ]),
          ];

        this.$bkInfo({
          type: isAuthorize ? 'warning' : '',
          title: titleMessage,
          subHeader: h('div', {
            style: {
              fontSize: '14px',
              color: '#4d4f56',
              textAlign: 'left',
              lineHeight: '22px',
            },
          }, dialogContent),
          width: 480,
          extCls: 'set-authorized-info',
          maskClose: false,
          confirmLoading: true,
          confirmFn: async () => {
            try {
              const resp = await this.updatePluginManager({
                code,
                config,
                status: isAuthorize ? 0 : 1,
              });
              if (resp.result) {
                this.$bkMessage({
                  message: successMessage,
                  theme: 'success',
                });
                this.$emit('update');
              }
            } catch (error) {
              console.warn(error);
            }
          },
        });
      },
    },
  };
</script>
<style lang="scss">
  .set-authorized-info {
    .bk-dialog-sub-header {
      padding: 6px 32px 24px !important;
    }
    .ellipsis {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
</style>
