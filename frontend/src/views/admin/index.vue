<template>
  <div class="manager-page">
    <router-view />
    <!--新建空间弹框-->
    <SpaceDialog
      :is-show="isVisible"
      @close="handleSpaceDialogClose" />
  </div>
</template>

<script>
  import { mapState } from 'vuex';
  import SpaceDialog from './common/SpaceDialog.vue';

  export default {
    name: 'EngineAdmin',
    components: {
      SpaceDialog,
    },
    data() {
      return {
        isVisible: false,
      };
    },
    computed: {
      ...mapState({
        isAdmin: state => state.isAdmin,
        isSpaceSuperuser: state => state.isSpaceSuperuser,
      }),
    },
    beforeRouteEnter(to, from, next) {
      next((vm) => {
        if (vm.isAdmin ||  vm.isSpaceSuperuser) return;
        // 没任何权限下，如果从首页路由进来则打开空间申请弹框，否则重定向home
        if (from.name === 'home') {
          vm.isVisible = true;
        } else {
          next({ name: 'home' });
        }
      });
    },
    methods: {
      handleSpaceDialogClose(id) {
        this.isVisible = false;
        this.$nextTick(() => {
          // 新增空间则刷新页面，重新拉取用户身份接口
          if (id) {
            this.$router.replace({
              name: 'spaceAdmin',
              query: {
                ...this.$route.query,
                space_id: id,
              },
            });
            this.loadSpacePermission();
          }
        });
      },
    },
  };
</script>
<style lang="scss" scoped>
  .manager-page {
    padding: 24px;
  }
  ::v-deep .scope-column-label {
    display: flex;
    align-items: center;
    .table-header-tips {
      flex-shrink: 0;
      margin-left: 4px;
      font-size: 14px;
      color: #c4c6cc;
    }
  }
</style>
