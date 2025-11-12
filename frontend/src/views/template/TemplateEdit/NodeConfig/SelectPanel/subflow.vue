<template>
  <div
    ref="subflowSelectPanel"
    class="subflow-select-panel">
    <p class="select-title">
      {{ $t('请选择流程进行节点配置') }}
    </p>
    <div class="type-select-wrapper">
      <bk-input
        v-model="searchStr"
        class="search-text-input"
        :placeholder="$t('请输入流程名称')"
        :clearable="true"
        right-icon="bk-icon icon-search"
        @paste="handleSearchPaste"
        @change="handleSearchEmpty"
        @clear="handleSearch"
        @enter="handleSearch" />
    </div>
    <div class="list-table">
      <div class="table-head">
        <div class="th-item tpl-name">
          {{ $t('流程名称') }}
        </div>
      </div>
      <!-- 加一层div用来放bkLoading -->
      <div v-bkloading="{ isLoading: listLoading }">
        <div class="tpl-list">
          <template v-if="tableList.length > 0">
            <div
              v-for="item in tableList"
              :key="item.id"
              :class="['tpl-item', {
                'active': String(item.id) === String(nodeConfig.template_id),
              }]"
              @click="onSelectTpl(item)">
              <div class="tpl-name name-content">
                <div
                  v-if="item.highlightName"
                  class="name"
                  v-html="item.highlightName" />
                <div
                  v-else
                  class="name">
                  {{ item.name }}
                </div>
                <span
                  class="view-tpl"
                  @click.stop="onViewTpl(item)">
                  <i class="common-icon-box-top-right-corner" />
                </span>
              </div>
            </div>
          </template>
          <NoData
            v-else
            :type="searchStr ? 'search-empty' : 'empty'"
            :message="searchStr ? $t('搜索结果为空') : ''"
            @searchClear="handleSearch('')" />
        </div>
      </div>
    </div>
  </div>
</template>
<script>
  import permission from '@/mixins/permission.js';
  import NoData from '@/components/common/base/NoData.vue';
  import { mapState } from 'vuex';

  export default {
    name: 'Subflow',
    components: {
      NoData,
    },
    mixins: [permission],
    props: {
      common: {
        type: [String, Number],
        default: '',
      },
      nodeConfig: {
        type: Object,
        default: () => ({}),
      },
      spaceId: {
        type: [String, Number],
        default: '',
      },
    },
    data() {
      return {
        tplList: [],
        listLoading: false,
        isLabelSelectorOpen: false,
        isCompleteLoading: false,
        selectedLabelName: '',
        searchStr: '',
        labels: [],
        limit: 20, // 每页的条数，默认值，在mounted会根据屏幕高度动态计算
        crtPage: 1, // 分页加载当前页数
      };
    },
    computed: {
      ...mapState({
        scopeInfo: state => state.template.scopeInfo,
      }),
      tableList() {
        // 除流程克隆的情况，流程列表中需要过滤掉url中template_id对应的流程
        if (this.$route.params.type === 'clone') {
          return this.tplList;
        }
        return this.tplList.filter(tpl => tpl.id !== Number(this.$route.params.templateId));
      },
    },
    mounted() {
      // 设置滚动加载
      const listWrapEl = this.$refs.subflowSelectPanel.querySelector('.tpl-list');
      listWrapEl.addEventListener('scroll', this.handleScroll, false);
      const { maxHeight } = window.getComputedStyle(listWrapEl);

      // 计算出每页加载的条数
      // 规则为容器高度除以每条的高度，考虑到后续可能需要触发容器滚动事件，在实际可容纳的条数上再增加1条
      // @notice: 每个流程条目的高度需要固定，目前取的css定义的高度40px
      if (maxHeight) {
        const height = Number(maxHeight.replace('px', ''));
        this.limit = Math.ceil(height / 40) + 1;
      }
      this.getTplList();
    },
    beforeDestroy() {
      const listWrapEl = this.$refs.subflowSelectPanel.querySelector('.tpl-list');
      listWrapEl.removeEventListener('scroll', this.handleScroll, false);
    },
    methods: {
      // 获取流程列表
      async getTplList() {
        if (this.listLoading) {
          return;
        }
        try {
          this.listLoading = true;
          const searchStr = this.escapeRegExp(this.searchStr);
          const data = {
            space_id: this.spaceId,
            limit: this.limit,
            offset: (this.crtPage - 1) * this.limit,
            name__icontains: this.searchStr,
            ...this.scopeInfo, // 作用域
            empty_scope: 1,
          };
          const resp = await this.$store.dispatch('templateList/loadTemplateList', data);
          const result = [];
          resp.data.results.forEach((tpl) => {
            const tplCopy = { ...tpl };
            // 高亮搜索匹配的文字部分
            if (searchStr !== '') {
              const reg = new RegExp(searchStr, 'i');
              if (reg.test(tpl.name)) {
                tplCopy.highlightName = this.filterXSS(tplCopy.name).replace(reg, `<span style="color: #ff9c01;">${this.searchStr}</span>`);
              }
            }
            result.push(tplCopy);
          });
          this.tplList.push(...result);
          this.isCompleteLoading = resp.data.count === this.tplList.length;
        } catch (e) {
          console.log(e);
        } finally {
          this.listLoading = false;
        }
      },
      // 滚动加载
      handleScroll(e) {
        if (this.listLoading || this.isCompleteLoading) {
          return;
        }
        const { scrollTop, clientHeight, scrollHeight } = e.target;
        // 距离底部一定阈值兼容大屏幕分辨率
        const threshold = clientHeight / 5;
        const distanceToBottom = scrollHeight - scrollTop - clientHeight;
        if (distanceToBottom < threshold && scrollHeight > clientHeight) {
          this.crtPage += 1;
          this.getTplList();
        }
      },
      // 对特殊字符串进行转义处理
      escapeRegExp(str) {
        if (typeof str !== 'string') {
          return '';
        }
        return str.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, '\\$&');
      },
      handleSearchPaste(value, event) {
        const paste = (event.clipboardData || window.clipboardData).getData('text');
        this.searchStr = value + paste;
        this.crtPage = 1;
        this.tplList = [];
        this.getTplList();
      },
      // 搜索框清空后触发搜索
      handleSearchEmpty(val) {
        if (val === '') {
          this.handleSearch('');
        }
      },
      handleSearch(val) {
        this.searchStr = val;
        this.crtPage = 1;
        this.tplList = [];
        this.getTplList();
      },
      // 选择流程
      onSelectTpl(tpl) {
        this.$emit('select', tpl);
      },
      // 查看流程
      onViewTpl(tpl) {
        const { name } = this.$route;
        const pathData = {
          name,
          params: {
            type: 'view',
            templateId: tpl.id,
          },
        };
        const { href } = this.$router.resolve(pathData);
        window.open(href, '_blank');
      },
    },
  };
</script>
<style lang="scss" scoped>
@import '../../../../../scss/config.scss';
@import '../../../../../scss/mixins/scrollbar.scss';
.subflow-select-panel {
    padding: 25px 32px 20px;
    height: 100%;
}
.select-title {
    margin-bottom: 16px;
    padding-bottom: 10px;
    font-size: 14px;
    color: #313238;
    font-weight: bold;
    border-bottom: 1px solid #dcdee5;
}
.type-select-wrapper {
    position: relative;
    height: 32px;
    .search-text-input {
        position: absolute;
        top: 0;
        right: 0;
        width: 240px;
    }
}
.list-table {
    margin-top: 16px;
    border: 1px solid #dcdee5;
    border-radius: 3px;
    .table-head {
        display: flex;
        align-items: center;
        padding: 12px;
        background: #fafbfd;
        border-bottom: 1px solid hsl(227, 15%, 88%);
        .th-item {
            color: #313238;
            font-size: 12px;
            font-weight: 500;
        }
        .tpl-name {
            flex: 0 0 auto;
            width: 420px;
        }
        .tpl-label {
            display: flex;
            align-items: center;
            > span {
                flex-shrink: 0;
            }
            .label-select-wrap {
                cursor: pointer;
            }
            .tpl-label-filter {
                width: 260px;
                height: 16px;
                line-height: 16px;
                border: none;
                &:hover {
                    .filter-icon {
                        color: #3a84ff;
                    }
                }
                .filter-icon {
                    margin-left: 4px;
                    color: #c4c6cc;
                }
            }
        }
    }
}
.tpl-list {
    max-height: calc(100vh - 260px);
    overflow: auto;
    @include scrollbar;
}
.tpl-item {
    display: flex;
    height: 40px;
    align-items: center;
    color: #63656e;
    border-top: 1px solid #dcdee5;
    cursor: pointer;
    &:hover:not(.text-permission-disable), &.active:not(.text-permission-disable) {
        background: #e1ecff;
        .name, .view-tpl {
            color: #3a84ff;
        }
    }
    &:first-of-type {
        border: none;
    }
    .name-content {
        display: flex;
        align-items: center;
        flex: 0 0 auto;
        width: 420px;
    }
    .name {
        padding: 0 13px;
        font-size: 12px;
        max-width: 400px;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
    }
    .view-tpl {
        margin-left: 10px;
        color: #9796a5;
        font-size: 14px;
    }
    .labels-wrap {
        padding-right: 13px;
        .label-item {
            display: inline-block;
            max-width: 144px;
            min-width: 40px;
            margin: 4px 0 4px 4px;
            padding: 2px 6px;
            font-size: 12px;
            line-height: 1;
            color: #63656e;
            border-radius: 8px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            cursor: pointer;
        }
    }
}
.tpl-loading {
    height: 40px;
    bottom: 0;
    left: 0;
    font-size: 14px;
    text-align: center;
    margin-top: 10px;
}
</style>
