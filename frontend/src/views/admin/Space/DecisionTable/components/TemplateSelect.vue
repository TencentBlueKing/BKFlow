<template>
  <bk-select
    v-model="setValue"
    class="template-select"
    :placeholder="$t('请选择')"
    searchable
    :clearable="false"
    :z-index="100"
    :disabled="readonly"
    enable-scroll-load
    :scroll-loading="bottomLoadingOptions"
    :popover-options="{ appendTo: 'parent' }"
    :remote-method="onRemoteSearch"
    @scroll-end="handleScrollToBottom">
    <bk-option
      v-for="option in templateList"
      :id="option.id"
      :key="option.id"
      :name="`[${option.id}] ${option.name}`" />
  </bk-select>
</template>

<script>
  import { mapActions } from 'vuex';
  import tools from '@/utils/tools.js';
  export default {
    name: 'TemplateSelect',
    model: {
      prop: 'value',
      event: 'change',
    },
    props: {
      spaceId: {
        type: [String, Number],
        default: '',
      },
      value: {
        type: [String, Number],
        default: '',
      },
      readonly: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        templateId: '',
        templateList: [],
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
      };
    },
    computed: {
      setValue: {
        get() {
          return this.value;
        },
        set(val) {
          this.$emit('change', val);
        },
      },
    },
    created() {
      this.getTemplateList();
      if (this.value) {
        this.getTemplateData(this.value);
      }
      this.onRemoteSearch = tools.debounce((val) => {
        this.searchValue = val;
        this.pagination.current = 1;
        this.getTemplateList();
      }, 500);
    },
    methods: {
      ...mapActions('templateList/', [
        'loadTemplateList',
      ]),
      ...mapActions('template/', [
        'loadTemplateData',
      ]),
      async getTemplateList() {
        try {
          const { limit, current } = this.pagination;
          const resp = await this.loadTemplateList({
            limit,
            offset: (current - 1) * limit,
            name__icontains: this.searchValue || undefined,
            space_id: this.spaceId,
          });
          // 如果是第一页则直接赋值
          if (current === 1) {
            this.templateList = resp.data.results;
          } else {
              const existingIds = new Set(this.templateList.map(item => item.id));
              const newItems = resp.data.results.filter(item => !existingIds.has(item.id));
              this.templateList.push(...newItems);
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
      async handleScrollToBottom() {
        try {
          if (this.pagination.current === this.totalPage) {
            return;
          }
          this.bottomLoadingOptions.isLoading = true;
          this.pagination.current += 1;
          await this.getTemplateList();
        } catch (error) {
          console.warn(error);
        } finally {
          this.bottomLoadingOptions.isLoading = false;
        }
      },
      async getTemplateData(templateId) {
        const isNeedUnshift = !this.templateList.some(item => item?.id === this.value);
        if (isNeedUnshift || this.templateList.length <= 0) {
          try {
            const templateData = await this.loadTemplateData({ templateId });
            this.$nextTick(() => {
              this.templateList.unshift(tools.deepClone(templateData));
            });
          } catch (error) {
            console.warn(error);
          }
        }
      },
    },
  };
</script>

<style lang="scss" scoped>
  .template-select {
    position: relative;
    height: 32px;
  }
</style>
