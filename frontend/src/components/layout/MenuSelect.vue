<template>
  <!-- 选择空间 -->
  <div class="menu-select">
    <bk-select
      ref="spaceSelector"
      class="space-select"
      :style="{ background: isExpand ? '#464d60' : 'none' }"
      :value="spaceId"
      :placeholder="$t('请选择空间')"
      searchable
      :clearable="false"
      enable-scroll-load
      :scroll-loading="bottomLoadingOptions"
      :popover-options="{ appendTo: 'parent' }"
      :remote-method="onRemoteSearch"
      @selected="handleSpaceSelected"
      @scroll-end="handleScrollToBottom">
      <div
        slot="trigger"
        class="select-trigger">
        <span
          v-if="spaceName"
          class="menu-title"
          :style="`backgroundColor: ${spaceBgColor}`">
          {{ spaceName[0].toLocaleUpperCase() }}
        </span>
        <span
          v-if="isExpand && spaceName"
          v-bk-overflow-tips="{
            content: spaceName,
            theme: 'light'
          }"
          class="space-name">
          {{ `${spaceName} (${spaceId})` }}
        </span>
      </div>
      <bk-option
        v-for="option in sortedSpaceList"
        :id="option.id"
        :key="option.id"
        :name="`${option.name} (${option.id})`">
        <div class="space-option-wrapper">
          <span class="space-name">{{ option.name }} ({{ option.id }})</span>
          <i
            v-bk-tooltips="{
              content: isFavorite(option.id) ? '取消收藏' : '收藏',
              placement: 'right',
              boundary: 'window'
            }"
            :class="['bk-icon', 'favorite-icon', isFavorite(option.id) ? 'icon-star-shape' : 'icon-star']"
            :style="{ color: isFavorite(option.id) ? '#FFB848' : '#C4C6CC' }"
            @click="handleToggleFavorite(option.id, $event)" />
        </div>
      </bk-option>
      <div
        slot="extension"
        style="text-align: center;"
        @click="isVisible = true">
        <i class="bk-icon icon-plus-circle" />
        {{ $t('新建空间') }}
      </div>
    </bk-select>
    <!--新建空间弹框-->
    <SpaceDialog
      :is-show="isVisible"
      @close="isVisible = false" />
  </div>
</template>

<script>
  import { mapActions, mapMutations, mapState } from 'vuex';
  import tools from '@/utils/tools.js';
  import bus from '@/utils/bus.js';
  import SpaceDialog from '@/views/admin/common/SpaceDialog.vue';
  export default {
    name: 'MenuSelect',
    components: {
      SpaceDialog,
    },
    props: {
      isExpand: {
        type: Boolean,
        default: true,
      },
    },
    data() {
      return {
        spaceList: [],
        favoriteSpaceIds: [], // 收藏的空间ID列表
        bottomLoadingOptions: {
          size: 'mini',
          isLoading: false,
        },
        pagination: {
          current: 1,
          count: 0,
          limit: 20,
        },
        totalPage: 1,
        spaceBgColor: '#3799ba',
        spaceName: '',
        searchValue: '',
        isVisible: false,
      };
    },
    computed: {
      ...mapState({
        spaceId: state => state.spaceId,
        isAdmin: state => state.isAdmin,
        isSpaceSuperuser: state => state.isSpaceSuperuser,
      }),
      // 排序后的空间列表：收藏的空间置顶
      sortedSpaceList() {
        const favoriteSet = new Set(this.favoriteSpaceIds);
        const favoriteSpaces = [];
        const normalSpaces = [];

        this.spaceList.forEach(space => {
          if (favoriteSet.has(space.id)) {
            favoriteSpaces.push(space);
          } else {
            normalSpaces.push(space);
          }
        });

        return [...favoriteSpaces, ...normalSpaces];
      },
    },
    watch: {
      isExpand(val) {
        if (!val) {
          this.$refs.spaceSelector?.close();
        }
      },
      spaceId: {
        handler(val) {
          if (!this.spaceList.length || !val) return;
          this.updateSpaceInfo();
        },
        immediate: true,
      },
      spaceList: {
        handler(val) {
          if (!val || !this.spaceId) return;
          this.updateSpaceInfo();
        },
        immediate: true,
      },
    },
    async created() {
      this.onRemoteSearch = tools.debounce((val) => {
        this.searchValue = val;
        this.pagination.current = 1;
        this.getSpaceList();
      }, 500);

      bus.$on('updateSpaceList', async () => {
        this.pagination.current = 1;
        this.pagination.count = 0;
        this.spaceList = [];
        await this.getSpaceList();
        // 创建成功后切换到最新的空间下并且更新权限信息
        this.loadCurSpacePermission(this.spaceList[0].id);
        this.handleSpaceSelected(this.spaceList[0].id);
      });
      await this.getSpaceList();
      // 加载用户收藏列表
      await this.loadFavorites();
      // 如果没有空间列表则打开空间申请弹框
      this.isVisible = !this.spaceList.length && (this.isAdmin || this.isSpaceSuperuser);
    },
    methods: {
      ...mapActions([
        'loadSpaceList',
        'getSpaceDetail',
        'getCurrentSpacePermission',
      ]),
      ...mapActions('user', [
        'getUserPreference',
        'saveUserPreference',
        'getUserFavorites',
        'toggleSpaceFavorite',
      ]),
      ...mapMutations([
        'setSpaceId',
        'setSpaceList',
        'setAdmin',
        'setCurSpaceSuperuser',
        'setSpaceSuperuser',
      ]),
      async loadCurSpacePermission(spaceId) {
        try {
          const resp = await this.getCurrentSpacePermission({ space_id: spaceId });
          const { is_admin: isAdmin, is_space_superuser: isCurSpaceSuperuser } = resp.data || {};
          this.setAdmin(isAdmin);
          this.setCurSpaceSuperuser(isCurSpaceSuperuser);
          this.setSpaceSuperuser(isCurSpaceSuperuser);
        } catch (error) {
          console.warn(error);
        }
      },
      async loadUserPreferredSpace() {
        try {
          const resp = await this.getUserPreference();
          // API 返回的数据在 resp.data 中
          const lastSelectedSpaceId = resp.data?.last_selected_space_id || resp.last_selected_space_id;
          console.log('加载用户偏好:', resp, '最后选择的空间ID:', lastSelectedSpaceId);
          // 如果用户有偏好且该空间在列表中，使用偏好的空间
          if (lastSelectedSpaceId && this.spaceList.some(item => item.id === lastSelectedSpaceId)) {
            this.setSpaceId(lastSelectedSpaceId);
            console.log('使用用户偏好的空间:', lastSelectedSpaceId);
          } else {
            // 否则使用第一个空间
            this.setSpaceId(this.spaceList[0]?.id);
            console.log('使用默认空间:', this.spaceList[0]?.id);
          }
        } catch (error) {
          console.warn('加载用户偏好失败，使用默认空间:', error);
          // 出错时使用第一个空间
          this.setSpaceId(this.spaceList[0]?.id);
        }
      },
      async getSpaceList() {
        try {
          const { limit, current } = this.pagination;
          const resp = await this.loadSpaceList({
            limit,
            offset: (current - 1) * limit,
            id_or_name: this.searchValue || undefined,
          });
          // 如果是第一页则直接赋值
          if (current === 1) {
            this.spaceList = resp.data.results;
          } else {
            this.spaceList.push(...resp.data.results);
          }
          // 默认获取第一个，如果有用户偏好则使用用户上次选择的空间
          if (!this.spaceId && current === 1) {
            await this.loadUserPreferredSpace();
          }
          // 计算总页数
          this.pagination.count = resp.data.count;
          const totalPage = Math.ceil(this.pagination.count / this.pagination.limit);
          if (!totalPage) {
            this.totalPage = 1;
          } else {
            this.totalPage = totalPage;
          }
          // 将spaceList存到vuex（搜索时不存）
          if (!this.searchValue) {
            this.setSpaceList(this.spaceList);
          }
        } catch (error) {
          console.warn(error);
        }
      },
      async updateSpaceInfo() {
        try {
          let spaceInfo = this.spaceList.find(item => item.id === this.spaceId);
          if (!spaceInfo) {
            const resp = await this.getSpaceDetail({ id: this.spaceId });
            spaceInfo = resp.data;
          }
          this.spaceBgColor = this.randomColor(spaceInfo.id);
          this.spaceName = spaceInfo.name;
        } catch (error) {
          console.warn(error);
        }
      },
      handleSpaceSelected(val) {
        this.setSpaceId(val);
        // 保存用户选择的空间
        this.saveUserPreference({ space_id: val }).catch((error) => {
          console.warn('保存用户偏好失败:', error);
        });
        const redirectMap = {
          '/template': {
            name: 'spaceAdmin',
            query: { activeTab: 'template' },
          },
          '/taskflow': {
            name: 'spaceAdmin',
            query: { activeTab: this.$route.query.type === 'mock' ? 'mockTask' : 'task' },
          },
          '/decision': {
            name: 'spaceAdmin',
            query: { activeTab: 'decisionTable' },
          },
          '/admin_decision': {
            name: 'spaceAdmin',
            query: { activeTab: 'decisionTable' },
          },
          '/enginePanel': {
            name: 'spaceAdmin',
            query: { activeTab: this.$route.query.type || 'task' },
          },
        };
        const key = Object.keys(redirectMap).find(key => this.$route.path.indexOf(key) === 0);
        const name = key ? redirectMap[key].name : this.$route.name;
        const query = key ? redirectMap[key].query : this.$route.query;
        this.$router.push({
          name,
          query: {
            ...query,
            space_id: val,
          },
        });
      },
      async handleScrollToBottom() {
        try {
          if (this.pagination.current === this.totalPage) {
            return;
          }
          this.bottomLoadingOptions.isLoading = true;
          this.pagination.current += 1;
          await this.getSpaceList();
        } catch (error) {
          console.warn(error);
        } finally {
          this.bottomLoadingOptions.isLoading = false;
        }
      },
      /**
       * 加载用户收藏列表
       */
      async loadFavorites() {
        try {
          const resp = await this.getUserFavorites();
          this.favoriteSpaceIds = resp.favorite_space_ids || [];
          console.log('[MenuSelect] 收藏列表加载成功:', this.favoriteSpaceIds);
        } catch (error) {
          console.warn('[MenuSelect] 加载收藏列表失败:', error);
          this.favoriteSpaceIds = [];
        }
      },
      /**
       * 切换收藏状态
       * @param {Number} spaceId - 空间ID
       * @param {Event} event - 事件对象
       */
      async handleToggleFavorite(spaceId, event) {
        // 阻止事件冒泡，防止触发空间切换
        event.stopPropagation();

        try {
          const resp = await this.toggleSpaceFavorite(spaceId);
          this.favoriteSpaceIds = resp.favorite_space_ids || [];

          // 显示提示信息
          this.$bkMessage({
            theme: 'success',
            message: resp.message || '操作成功',
          });

          console.log('[MenuSelect] 收藏状态已更新:', this.favoriteSpaceIds);
        } catch (error) {
          console.error('[MenuSelect] 切换收藏失败:', error);
          this.$bkMessage({
            theme: 'error',
            message: '操作失败，请重试',
          });
        }
      },
      /**
       * 检查空间是否已收藏
       * @param {Number} spaceId - 空间ID
       * @returns {Boolean}
       */
      isFavorite(spaceId) {
        return this.favoriteSpaceIds.includes(spaceId);
      },
      randomColor(seed = 0) {
        const totalColors = 1000; // 最大支持颜色种类数
        // 计算对应下标
        const idx = (seed + 1) % totalColors;
        // 默认返回红色
        let ret = 0xFF0000;
        // RGB的最大值
        const full = 0xFFFFFF;
        // 总共需要支持多少种颜色，若传0则取255
        const total = totalColors || 0xFF;
        // 将所有颜色平均分成x份
        const perVal = full / total;
        if (idx >= 0 && idx <= total) {
          ret = perVal * idx;
        }
        ret = Math.round(ret);
        // 转成RGB 16进制字符串
        ret = ret.toString(16).padEnd(6, 'f');
        return `#${ret}`;
      },
    },
  };
</script>

<style lang="scss" scoped>
  .menu-select {
    position: relative;
    height: 32px;
    width: calc(100% - 16px);
    margin: -2px 8px 10px;
    .space-select {
      line-height: 32px;
      border: none;
      color: #dcdee5;
      background: #464d60;
      ::v-deep .select-trigger {
        display: flex;
        align-items: center;
        height: 32px;
        padding: 0 8px;
        .menu-title {
          flex-shrink: 0;
          width: 20px;
          height: 20px;
          text-align: center;
          line-height: 20px;
          margin-right: 6px;
          font-size: 12px;
          font-weight: 700;
          color: #fff;
          background: #a09e21;
          border-radius: 2px;
          overflow: hidden;
        }
        .space-name {
          flex: 1;
          overflow: hidden;
          white-space: nowrap;
          text-overflow: ellipsis;
        }
      }
      ::v-deep .tippy-popper{
        .tippy-content{
          padding: 0 !important;
        }
      }
    }
    .space-option-wrapper {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;
      .space-name {
        flex: 1;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
        margin-right: 8px;
      }
      .favorite-icon {
        flex-shrink: 0;
        font-size: 16px;
        cursor: pointer;
        transition: all 0.2s;
        &:hover {
          transform: scale(1.2);
        }
      }
    }
    &::after {
      content: '';
      display: block;
      height: 1px;
      width: calc(100%  + 16px);
      position: absolute;
      bottom: -10px;
      left: -8px;
      background: #ffffff1a;;
    }
  }
</style>
