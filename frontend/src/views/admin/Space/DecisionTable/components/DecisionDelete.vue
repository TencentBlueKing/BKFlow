<template>
  <bk-popconfirm
    ref="delDecisionPopConfirm"
    :trigger="data.template_id ? 'manual' : 'click'"
    :ext-cls="'delete-decision-pop-confirm'"
    width="280"
    @confirm="handleConfirm"
    @cancel="$emit('cancel')">
    <template slot="content">
      <p class="pop-title">
        {{ $t('确认删除该决策表？') }}
      </p>
      <div class="pop-content">
        <span class="label">{{ $t('决策表名称：') }}</span>
        <span class="name">{{ data.name }}</span>
      </div>
      <p>{{ $t('删除后不可恢复，请谨慎操作！') }}</p>
    </template>
    <div
      class="delete-btn"
      @click="handleDeleted">
      <slot />
      <bk-button
        theme="default"
        :text="text">
        {{ $t('删除') }}
      </bk-button>
    </div>
  </bk-popconfirm>
</template>

<script>
  import { mapState, mapActions } from 'vuex';
  export default {
    name: 'DecisionDelete',
    props: {
      data: {
        type: Object,
        default: () => ({}),
      },
      text: {
        type: Boolean,
        default: false,
      },
      isAdminPath: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        deleting: false,
      };
    },
    computed: {
      ...mapState({
        isAdmin: state => state.isAdmin,
        isCurSpaceSuperuser: state => state.isCurSpaceSuperuser,
        spaceId: state => state.spaceId,
      }),
    },
    methods: {
      ...mapActions('decisionTable/', [
        'deleteDecision',
        'checkDecisionUsed',
      ]),
      async handleDeleted() {
        try {
          // 决策表没有绑定模板则不进行后续判断
          if (!this.data.template_id) return;

          // 检查决策表是否被流程使用
          const resp = await this.checkDecisionUsed({
            id: this.data.id,
            isAdmin: this.isAdminPath,
            template_id: this.data.template_id,
            space_id: this.spaceId,
          });
          if (!resp.result) return;
          if (resp.data.has_used) {
            this.$bkMessage({
              message: this.$t('当前决策表已被流程使用，禁止删除！'),
              theme: 'error',
            });
            return;
          }
          const pooInstance = this.popoverInstance();
          pooInstance && pooInstance.showHandler();
        } catch (error) {
          console.warn(error);
        }
      },
      async handleConfirm() {
        if (this.deleting) return;
        this.deleting = true;
        try {
          const data = {
            space_id: this.spaceId,
            id: this.data.id,
            isAdmin: this.isAdmin || this.isCurSpaceSuperuser,
          };
          await this.deleteDecision(data);

          this.$bkMessage({
            message: this.$t('决策表删除成功！'),
            theme: 'success',
          });
          this.$emit('onDeleted');
        } catch (e) {
          console.log(e);
        } finally {
          this.deleting = false;
        }
      },
      popoverInstance() {
        const popConfirmInstance = this.$refs.delDecisionPopConfirm;
        return popConfirmInstance && popConfirmInstance.$refs.popover;
      },
    },
  };
</script>

<style lang="scss" scoped>
  .delete-btn {
    display: flex;
    align-items: center;
  }
</style>
<style lang="scss">
// 决策表删除确认
.delete-decision-pop-confirm {
  .popconfirm-content {
    font-size: 12px;
    color: #63656e;
    margin-bottom: 14px;
    .pop-title {
      font-size: 16px;
      color: #313238;
      line-height: 24px;
      margin-bottom: 16px;
    }
    .pop-content {
      line-height: 20px;
      margin-bottom: 4px;
      .label {
        color: #63656e;
      }
      .name {
        color: #313238;
      }
    }
  }
}
</style>
