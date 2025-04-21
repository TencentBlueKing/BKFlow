<template>
  <bk-dialog
    :value="isShow"
    theme="primary"
    :mask-close="false"
    header-position="left"
    :width="640"
    :esc-close="false"
    render-directive="if"
    :title="$t('编辑使用范围')"
    :loading="editLoading"
    @confirm="onConfirm"
    @cancel="onCancel">
    <bk-form
      ref="spaceForm"
      form-type="vertical"
      :model="formData">
      <bk-form-item
        label="选择空间范围"
        :required="true"
        property="range">
        <bk-select
          :value="formData.ids"
          searchable
          :clearable="false"
          enable-scroll-load
          multiple
          :allow-enter="false"
          :scroll-loading="bottomLoadingOptions"
          :popover-options="{ appendTo: 'parent' }"
          :remote-method="onRemoteSearch"
          @toggle="isExpand = $event"
          @selected="handleSpaceSelected"
          @scroll-end="handleScrollToBottom">
          <div
            slot="trigger"
            class="select-trigger"
            :data-placeholder="selectedSpaceName ? '' : $t('请选择空间')">
            <span
              v-bk-overflow-tips
              class="space-name">
              {{ selectedSpaceName }}
            </span>
            <i :class="['common-icon-angle-right', { 'icon-flip': isExpand }]" />
          </div>
          <bk-option
            v-if="!searchValue"
            id="*"
            :name="$t('* (对所有空间公开)')" />
          <bk-option
            v-for="option in spaceList"
            :id="option.id"
            :key="option.id"
            :name="option.name" />
        </bk-select>
      </bk-form-item>
    </bk-form>
  </bk-dialog>
</template>
<script>
  import tools from '@/utils/tools.js';
  import { mapActions } from 'vuex';
  export default {
    props: {
      isShow: {
        type: Boolean,
        default: false,
      },
      row: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        formData: {
          ids: [],
        },
        editLoading: false,
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
        searchValue: '',
        spaceList: [],
        isExpand: false,
        selectedOptions: [],
      };
    },
    computed: {
      selectedSpaceName() {
        return this.selectedOptions.reduce((acc, cur) => acc + (acc ? ',' : '') + (cur.id === '*' ? '*' : cur.name), '');
      },
    },
    watch: {
      isShow(val) {
        this.spaceList = [];
        this.searchValue = '';
        this.pagination.current = 1;
        if (val) {
          const { white_list: whiteList } = this.row.config;
          this.selectedOptions = whiteList;

          const ids = whiteList.map(item => item.id);
          this.formData.ids = ids.includes('*') ? ids : ids.map(Number);
          this.getSpaceList();
        }
      },
    },
    created() {
      this.onRemoteSearch = tools.debounce((val) => {
        this.searchValue = val;
        this.pagination.current = 1;
        this.getSpaceList();
      }, 500);
    },
    methods: {
      ...mapActions([
        'loadSpaceList',
      ]),
      ...mapActions('plugin', [
        'updatePluginManager',
      ]),
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
          // 计算总页数
          this.pagination.count = resp.data.count;
          const totalPage = Math.ceil(this.pagination.count / this.pagination.limit);
          if (!totalPage) {
            this.totalPage = 1;
          } else {
            this.totalPage = totalPage;
          }
        } catch (error) {
          console.warn(error);
        }
      },
      handleSpaceSelected(val, options) {
        // 最后一次选中的是否为全选
        const lastOption = options[options.length - 1];
        const isLastOptionSelectAll = lastOption.id === '*';

        // 存在一开始选中的空间在最后几页，列表里面不存在的清空。更新选项时，options会没有后面页选中的选项
        const { white_list: whiteList } = this.row.config;
        const selectedOptions = [...whiteList, ...options];
        this.selectedOptions = isLastOptionSelectAll ? [lastOption] : val.reduce((acc, id) => {
          if (id === '*') return acc;
          const option = selectedOptions.find(option => Number(option.id) === id);
          option && acc.push(option);
          return acc;
        }, []);
        this.formData.ids = isLastOptionSelectAll ? ['*'] : val.filter(v => v !== '*');
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
      async onConfirm() {
        try {
          this.editLoading = true;
          const { code, status } = this.row;
          const resp = await this.updatePluginManager({
            code,
            status,
            config: {
              white_list: this.formData.ids,
            },
          });
          if (resp.result) {
            this.$bkMessage({
              message: this.$t('使用范围编辑成功'),
              theme: 'success',
            });
            this.$emit('close', true);
          }
        } catch (error) {
          console.warn(error);
        } finally {
          this.editLoading = false;
        }
      },
      onCancel() {
        this.$emit('close');
      },
    },
  };
</script>
<style lang="scss" scoped>
  /deep/.select-trigger {
    display: flex;
    align-items: center;
    height: 32px;
    padding: 0 8px;
    .space-name {
      flex: 1;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
    i {
      font-size: 22px;
      color: #979ba5;
      transform: rotate(90deg);
      transition: all 0.3s;
      &.icon-flip {
        transform: rotate(-90deg);
      }
    }
    &::before {
      position: absolute;
      content: attr(data-placeholder);
      color: #c4c6cc;
    }
  }
</style>
