<template>
  <div class="table-operate">
    <div class="btn-wrap">
      <slot />
    </div>
    <search-select
      :id="`${activeTab}List`"
      ref="searchSelect"
      :key="activeTab"
      v-model="searchSelectValue"
      :placeholder="placeholder"
      :search-list="searchList"
      :disabled="!spaceId"
      @change="handleSearchValueChange" />
  </div>
</template>

<script>
  import i18n from '@/config/i18n/index.js';
  import SearchSelect from '@/components/common/searchSelect/index.vue';
  export default {
    name: 'TableOperate',
    components: {
      SearchSelect,
    },
    props: {
      searchList: {
        type: Array,
        default: () => ([]),
      },
      spaceId: {
        type: [String, Number],
        default: null,
      },
      placeholder: {
        type: String,
        default: i18n.t('请输入'),
      },
    },
    data() {
      const {
        id,
        name,
        creator,
        executor,
        updated_by,
        create_at,
        update_at,
        create_time,
        start_time,
        finish_time,
        template_id,
        is_enabled,
        activeTab = 'template',
      } = this.$route.query;
      const dateInfo = { create_at, update_at, start_time, create_time, finish_time };
      const searchList = [
        ...this.searchList,
        { id: 'create_at', name: this.$t('创建时间'), type: 'dateRange' },
        { id: 'update_at', name: this.$t('更新时间'), type: 'dateRange' },
        { id: 'create_time', name: this.$t('创建时间'), type: 'dateRange' },
        { id: 'start_time', name: this.$t('开始时间'), type: 'dateRange' },
        { id: 'finish_time', name: this.$t('结束时间'), type: 'dateRange' },
      ];
      const searchSelectValue = searchList.reduce((acc, cur) => {
        const valuesText = this.$route.query[cur.id];
        if (valuesText) {
          if (cur.type === 'dateRange') {
            acc.push({ ...cur, values: valuesText.split(',') });
          } else {
            acc.push({ ...cur, values: [valuesText] });
          }
        }
        return acc;
      }, []);
      return {
        activeTab,
        searchSelectValue,
        requestData: {
          id,
          name,
          creator,
          executor,
          updated_by,
          create_at: dateInfo.create_at ? dateInfo.create_at.split(',') : ['', ''],
          update_at: dateInfo.update_at ? dateInfo.update_at.split(',') : ['', ''],
          create_time: dateInfo.create_time ? dateInfo.create_time.split(',') : ['', ''],
          start_time: dateInfo.start_time ? dateInfo.start_time.split(',') : ['', ''],
          finish_time: dateInfo.finish_time ? dateInfo.finish_time.split(',') : ['', ''],
          template_id,
          is_enabled,
        },
      };
    },
    watch: {
      requestData: {
        handler(val) {
          this.$emit('changeRequest', val);
        },
        deep: true,
        immediate: true,
      },
      searchSelectValue: {
        handler(val) {
          this.$emit('updateSearchValue', val);
        },
        deep: true,
        immediate: true,
      },
    },
    methods: {
      handleSearchValueChange(data) {
        data = data.reduce((acc, cur) => {
          if (cur.type === 'dateRange') {
            acc[cur.id] = cur.values;
          } else {
            const value = cur.values[0];
            acc[cur.id] = cur.children ? value.id : value;
          }
          return acc;
        }, {});
        this.requestData = data;
        this.updateUrl();
      },
      updateUrl() {
        const {
          create_at: createAt,
          update_at: updateAt,
          create_time: createTime,
          start_time: startTime,
          finish_time: finishTime,
        } = this.requestData;
        const filterObj = {
          ...this.requestData,
          create_at: createAt && createAt.every(item => item) ? createAt.join(',') : '',
          update_at: updateAt && updateAt.every(item => item) ? updateAt.join(',') : '',
          create_time: createTime && createTime.every(item => item) ? createTime.join(',') : '',
          start_time: startTime && startTime.every(item => item) ? startTime.join(',') : '',
          finish_time: finishTime && finishTime.every(item => item) ? finishTime.join(',') : '',
        };
        const query = {};
        Object.keys(filterObj).forEach((key) => {
          const val = filterObj[key];
          if (val || val === 0 || val === false) {
            query[key] = val;
          }
        });
        query.spaceId = this.spaceId;
        query.activeTab = this.activeTab;
        const { name } = this.$route;
        this.$router.replace({ name, query });
      },
      addSearchRecord(data) {
        const searchDom = this.$refs.searchSelect;
        searchDom && searchDom.addSearchRecord(data);
      },
      updateSearchSelect(data) {
        if (Object.keys(data).length) {
          Object.keys(data).forEach((key) => {
            const creatorInfo = this.searchSelectValue.find(item => item.id === key);
            if (creatorInfo) {
              creatorInfo.values = data[key];
            } else {
              const form = this.searchList.find(item => item.id === key);
              this.searchSelectValue.push({ ...form, values: data[key] });
            }
          });
        } else {
          this.searchSelectValue = [];
        }
      },
    },
  };
</script>

<style lang="scss" scoped>
  .table-operate {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 15px;
    .btn-wrap {
      display: flex;
      align-items: center;
    }
    .search-select {
      position: relative;
      z-index: 1;
    }
  }
</style>
