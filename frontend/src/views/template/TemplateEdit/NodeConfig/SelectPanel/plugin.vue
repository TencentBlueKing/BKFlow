<template>
  <bk-tab
    :active="curTab"
    type="unborder-card"
    @tab-change="onTabChange">
    <bk-input
      v-if="['builtIn', 'thirdParty'].includes(curTab)"
      v-model.trim="searchStr"
      class="search-input"
      right-icon="bk-icon icon-search"
      :placeholder="$t('请输入插件名称')"
      :clearable="true"
      data-test-id="templateEdit_form_searchPlugin"
      @change="handleSearchEmpty"
      @clear="handleSearch"
      @enter="handleSearch" />
    <p
      v-if="bkPluginDevelopUrl"
      class="plugin-dev-doc"
      @click="jumpToPluginDev">
      {{ $t('找不到想要的插件？可以尝试自己动手开发！') }}
    </p>
    <!-- 内置插件 -->
    <bk-tab-panel
      name="builtIn"
      :label="$t('内置插件')">
      <template v-if="builtInPluginGroup.length > 0">
        <div class="group-area">
          <div
            v-for="group in builtInPluginGroup"
            :key="group.type"
            :class="['group-item', {
              active: group.type === activeGroup
            }]"
            :data-test-id="`templateEdit_list_${group.sort_key_group_en}`"
            @click="onSelectGroup(group.type)">
            <img
              v-if="group.group_icon"
              class="group-icon-img"
              :src="group.group_icon">
            <i
              v-else
              :class="['group-icon-font', getIconCls(group.type)]" />
            <span v-html="group.group_name" />
            <span>{{ `(${group.list.length})` }}</span>
          </div>
        </div>
        <div
          ref="selectorArea"
          class="selector-area">
          <template v-if="activeGroupPlugin.length > 0">
            <li
              v-for="(item, index) in activeGroupPlugin"
              :key="index"
              :class="['list-item', { active: item.code === crtPlugin }]"
              :title="item.name"
              :data-test-id="`templateEdit_list_${item.code.replace(/_(\w)/g, (strMatch, p1) => p1.toUpperCase())}`"
              @click="$emit('select', item)">
              <span
                v-if="item.highlightName"
                class="node-name"
                v-html="item.highlightName" />
              <span
                v-else
                class="node-name">{{ item.name }}</span>
            </li>
          </template>
          <NoData
            v-else
            :type="searchStr ? 'search-empty' : 'empty'"
            :message="searchStr ? $t('搜索结果为空') : ''"
            @searchClear="handleSearch('')" />
        </div>
      </template>
      <NoData
        v-else
        :type="searchStr ? 'search-empty' : 'empty'"
        :message="searchStr ? $t('搜索结果为空') : ''"
        @searchClear="handleSearch('')" />
    </bk-tab-panel>
    <!-- 第三方插件 -->
    <bk-tab-panel
      ref="thirdPartyPanel"
      v-bkloading="{ isLoading: thirdPluginTagsLoading || thirdPluginLoading }"
      name="thirdParty"
      :label="$t('第三方插件')">
      <div
        v-if="isThirdPartyGroupShow"
        class="group-area">
        <template v-for="group in thirdPluginGroup">
          <div
            v-if="group.isShow"
            :key="group.id"
            :class="['group-item', {
              active: group.id === thirdActiveGroup
            }]"
            :data-test-id="`templateEdit_thirdList_${group.id}`"
            @click="onSelectThirdGroup(group.id)">
            <span v-html="group.name" />
          </div>
        </template>
      </div>
      <div class="third-party-list">
        <template v-if="thirdPartyPlugin.length > 0">
          <div
            v-for="(plugin, index) in thirdPartyPlugin"
            :key="index"
            :class="['plugin-item', { 'is-active': plugin.code === crtPlugin }]"
            @click="onSelectThirdPartyPlugin(plugin)">
            <img
              class="plugin-logo"
              :src="plugin.logo_url"
              alt="">
            <div>
              <p
                v-if="plugin.highlightName"
                class="plugin-title"
                v-html="plugin.highlightName" />
              <p
                v-else
                class="plugin-title">
                {{ plugin.name }}
              </p>
              <p
                v-bk-overflow-tips="{ placement: 'bottom-end', extCls: 'plugin-desc-tips' }"
                class="plugin-desc">
                {{ plugin.introduction || '--' }}
              </p>
              <p class="plugin-contact">
                {{ $t('由') + ' ' + plugin.contact + ' ' + $t('提供') }}
              </p>
            </div>
          </div>
        </template>
        <NoData
          v-else
          :type="searchStr ? 'search-empty' : 'empty'"
          :message="searchStr ? $t('搜索结果为空') : ''"
          @searchClear="handleSearch('')" />
      </div>
    </bk-tab-panel>
    <ApiPlugin
      v-if="apiTabList.length"
      :api-tab-list="apiTabList"
      :current-tab="curTab"
      :search-str="searchStr"
      :crt-plugin="crtPlugin"
      :crt-group="crtGroup"
      :scope-info="scopeInfo"
      :space-id="spaceId"
      @select="$emit('select', $event)" />
  </bk-tab>
</template>
<script>
  import { SYSTEM_GROUP_ICON } from '@/constants/index.js';
  import NoData from '@/components/common/base/NoData.vue';
  import ApiPlugin from './apiPlugin.vue';

  export default {
    name: 'Plugin',
    components: {
      NoData,
      ApiPlugin,
    },
    props: {
      isThirdParty: Boolean,
      crtPlugin: {
        type: String,
        default: '',
      },
      crtGroup: {
        type: String,
        default: '',
      },
      builtInPlugin: {
        type: Array,
        default: () => ([]),
      },
      isApiPlugin: Boolean,
      spaceId: {
        type: [String, Number],
        default: '',
      },
      scopeInfo: {
        type: Object,
        default: () => ({}),
      },
      spaceRelatedConfig: {
        type: Object,
        default: () => ({}),
      },
      apiKey: {
        type: String,
        default: '',
      },
    },
    data() {
      let curTab = this.isThirdParty ? 'thirdParty' : 'builtIn';
      curTab = this.isApiPlugin ? this.apiKey : curTab;
      return {
        curTab,
        builtInPluginGroup: this.builtInPlugin.slice(0),
        activeGroup: this.getDefaultActiveGroup(),
        thirdPartyPlugin: [],
        thirdActiveGroup: '',
        thirdPluginGroup: [],
        thirdPluginTagsLoading: false,
        thirdPluginLoading: false,
        thirdPluginPagelimit: 15,
        isThirdPluginCompleteLoading: false,
        thirdPluginOffset: 0,
        searchStr: '',
        bkPluginDevelopUrl: window.BK_PLUGIN_DEVELOP_URL,
        apiTabList: [],
      };
    },
    computed: {
      activeGroupPlugin() {
        const group = this.builtInPluginGroup.find(item => item.type === this.activeGroup);
        return group ? group.list : [];
      },
      isThirdPartyGroupShow() {
        return this.thirdPluginGroup && this.thirdPluginGroup.some(item => item.isShow);
      },
    },
    created() {
      this.getApiTabList();
    },
    async mounted() {
      if (this.curTab === 'thirdParty') {
        await this.getThirdPluginGroup();
        this.setThirdParScrollLoading();
      }
    },
    beforeDestroy() {
      const listWrapEl = this.$refs.thirdPartyPanel.$el.querySelector('.third-party-list');
      listWrapEl.removeEventListener('scroll', this.handleThirdParPluginScroll, false);
    },
    methods: {
      getApiTabList() {
        const { uniform_api: uniformApi = {} } = this.spaceRelatedConfig;

        if (!uniformApi.api) {
          this.apiTabList = [];
          return;
        }

        this.apiTabList = Object.entries(uniformApi.api).reduce((acc, [key, value]) => {
          if (key === 'V1' && value.display_name === '-') {
            acc.push({
              key,
              name: 'Api插件',
            });
          } else {
            acc.push({
              key,
              name: value.display_name || key,
            });
          }
          return acc;
        }, []);
      },
      // 获取内置插件默认展开的分组，没有选择展开第一组，已选择展开选中的那组
      getDefaultActiveGroup() {
        let activeGroup = '';
        if (this.crtPlugin && !this.isThirdParty) {
          this.builtInPlugin.some((group) => {
            let result = false;
            if (group.list.find(item => item.code === this.crtPlugin)) {
              activeGroup = group.type;
              result = true;
            }
            return result;
          });
        } else {
          if (this.builtInPlugin.length > 0) {
            activeGroup = this.builtInPlugin[0].type;
          }
        }
        return activeGroup;
      },
      // 内置插件分组icon classname
      getIconCls(type) {
        const systemType = SYSTEM_GROUP_ICON.find(item => new RegExp(item).test(type));
        if (this.isSubflow) {
          return 'common-icon-subflow-mark';
        }
        if (systemType) {
          return `common-icon-sys-${systemType.toLowerCase()}`;
        }
        return 'common-icon-sys-default';
      },
      // 加载第三方插件列表
      async getThirdPartyPlugin() {
        if (this.thirdPluginLoading) {
          return;
        }
        try {
          this.thirdPluginLoading = true;
          // 搜索时拉取全量插件列表
          const params = {
            fetch_all: this.searchStr ? true : undefined,
            limit: this.thirdPluginPagelimit,
            offset: this.thirdPluginOffset,
            search_term: this.searchStr || undefined,
            exclude_not_deployed: true,
            tag_id: this.thirdActiveGroup || undefined,
          };
          const resp = await this.$store.dispatch('atomForm/loadPluginServiceList', params);
          const { next_offset: nextOffset, plugins, return_plugin_count: pluginCount } = resp.data;
          const searchStr = this.escapeRegExp(this.searchStr);
          const reg = new RegExp(searchStr, 'i');
          const pluginTagIds = [];
          let pluginList = plugins.map((item) => {
            const pluginItem = Object.assign({}, item.plugin, item.profile);
            if (this.searchStr !== '') {
              pluginItem.highlightName = this.filterXSS(item.plugin.name).replace(reg, `<span style="color: #ff9c01;">${this.searchStr}</span>`);
              pluginTagIds.push(item.profile.tag || -1);
            }
            return pluginItem;
          });
          if (this.searchStr) {
            // 当第三方插件搜索时，反向映射插件分类
            this.thirdPluginGroup.forEach((group) => {
              if (pluginTagIds.includes(group.id)) {
                group.isShow = true;
                if (!this.thirdActiveGroup) {
                  this.thirdActiveGroup = group.id;
                }
              }
            });
            pluginList = pluginList.filter(item => this.thirdActiveGroup === (item.tag || -1));
          }
          this.thirdPluginOffset = pluginCount ? nextOffset : 0;
          this.thirdPartyPlugin.push(...pluginList);
          if (nextOffset === -1 || pluginCount < this.thirdPluginPagelimit) {
            this.isThirdPluginCompleteLoading = true;
          }
        } catch (error) {
          console.warn(error);
        } finally {
          this.thirdPluginLoading = false;
        }
      },
      // 设置第三方插件滚动加载事件
      setThirdParScrollLoading() {
        // 设置滚动加载
        const listWrapEl = this.$refs.thirdPartyPanel.$el.querySelector('.third-party-list');
        listWrapEl.addEventListener('scroll', this.handleThirdParPluginScroll, false);
        const { height } = listWrapEl.getBoundingClientRect();

        // 计算出每页加载的条数
        // 规则为容器高度除以每条的高度，考虑到后续可能需要触发容器滚动事件，在实际可容纳的条数上再增加1条
        // @notice: 每个流程条目的高度需要固定，目前取的css定义的高度80px
        if (height > 0) {
          this.thirdPluginPagelimit = Math.ceil(height / 80) + 1;
        }
        this.getThirdPartyPlugin();
      },
      // 滚动加载逻辑
      handleThirdParPluginScroll(e) {
        if (this.thirdPluginLoading || this.isThirdPluginCompleteLoading) {
          return;
        }
        const { scrollTop, clientHeight, scrollHeight } = e.target;
        if (scrollHeight - scrollTop - clientHeight < 10) {
          this.getThirdPartyPlugin();
        }
      },
      // 切换tab
      async onTabChange(val) {
        this.curTab = val;
        // 切换tab时需要重新搜索
        this.handleSearch(this.searchStr);
      },
      // 搜索框字符为空
      handleSearchEmpty(val) {
        if (val === '') {
          this.handleSearch('');
        }
      },
      // 搜索逻辑
      async handleSearch(val) {
        this.searchStr = val;
        if (this.curTab === 'builtIn') {
          this.setBuiltInPluginSearchResult(val);
        } else if (this.curTab === 'thirdParty') {
          // 获取第三方插件分组
          if (!this.thirdPluginGroup.length) {
            await this.getThirdPluginGroup();
          }
          // 搜索时清空插件分类，由插件列表反向映射插件分类
          this.thirdPluginGroup.forEach((item) => {
            item.isShow = !val;
          });
          const { id = '' } = this.thirdPluginGroup[0];
          this.thirdActiveGroup = val ? '' : id;
          this.thirdPartyPlugin = [];
          this.thirdPluginOffset = 0;
          this.setThirdParScrollLoading();
        }
      },
      // 内置插件本地搜索
      setBuiltInPluginSearchResult(val) {
        let result = [];
        if (val === '') {
          result = this.builtInPlugin.slice(0);
          this.activeGroup = this.getDefaultActiveGroup();
        } else {
          const searchStr = this.escapeRegExp(val);
          const reg = new RegExp(searchStr, 'i');
          this.builtInPlugin.forEach((group) => {
            const { group_icon, group_name, type } = group;
            const list = [];

            if (reg.test(group_name)) { // 分组名称匹配
              const hglGroupName = this.filterXSS(group_name).replace(reg, `<span style="color: #ff9c01;">${val}</span>`);
              result.push({
                ...group,
                group_name: hglGroupName,
              });
            } else if (group.list.length > 0) { // 单个插件或者子流程名称匹配
              group.list.forEach((item) => {
                if (reg.test(item.name)) {
                  const node = { ...item };
                  node.highlightName = this.filterXSS(item.name).replace(reg, `<span style="color: #ff9c01;">${val}</span>`);
                  list.push(node);
                }
              });
              if (list.length > 0) {
                result.push({
                  group_icon,
                  group_name,
                  type,
                  list,
                });
              }
            }
          });
          if (result.length > 0) {
            this.activeGroup = result[0].type;
          }
        }
        this.builtInPluginGroup = result;
      },
      escapeRegExp(str) {
        if (typeof str !== 'string') {
          return '';
        }
        return str.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, '\\$&');
      },
      // 跳转到第三方插件开发稳单
      jumpToPluginDev() {
        window.open(this.bkPluginDevelopUrl, '_blank');
      },
      // 选择内置插件分组
      onSelectGroup(val) {
        this.activeGroup = val;
        this.$refs.selectorArea.scrollTop = 0;
      },
      // 获取第三方插件分组
      async getThirdPluginGroup() {
        try {
          this.thirdPluginTagsLoading = true;
          let tagId = '';
          // 插件重选时，选择对应的分类id
          if (this.isThirdParty && this.crtPlugin) {
            const pluginInfo = await this.$store.dispatch('atomForm/loadPluginServiceAppDetail', { plugin_code: this.crtPlugin });
            const tagInfo = pluginInfo.data.tag_info;
            tagId = tagInfo ? tagInfo.id : -1;
          }
          const resp = await this.$store.dispatch('atomForm/getThirdPluginTags');
          if (resp.result) {
            this.thirdActiveGroup = tagId || (this.searchStr ? '' : resp.data[0].id);
            this.thirdPluginGroup = resp.data.map(item => ({ ...item, isShow: true }));
          }
        } catch (error) {
          console.warn(error);
        } finally {
          this.thirdPluginTagsLoading = false;
        }
      },
      // 选中第三方插件分组
      onSelectThirdGroup(val) {
        this.thirdActiveGroup = val;
        this.thirdPartyPlugin = [];
        this.isThirdPluginCompleteLoading = false;
        this.thirdPluginOffset = 0;
        this.getThirdPartyPlugin();
      },
      async onSelectThirdPartyPlugin(plugin) {
        try {
          const resp = await this.$store.dispatch('atomForm/loadPluginServiceMeta', { plugin_code: plugin.code });
          const { code, versions, description } = resp.data;
          const versionList = versions.sort().map(version => ({ version }));
          const data = {
            code,
            name: plugin.name,
            list: versionList,
            desc: description,
            id: 'remote_plugin',
          };
          this.$emit('select', data);
        } catch (error) {
          console.warn(error);
        }
      },
    },
  };
</script>
<style lang="scss" scoped>
@import '../../../../../scss/config.scss';
@import '../../../../../scss/mixins/scrollbar.scss';
.bk-tab {
  /deep/.bk-tab-section {
        padding: 0;
        .bk-tab-content {
            height: calc(100vh - 110px);
            overflow: hidden;
        }
    }
}
.search-input {
    position: absolute;
    top: -46px;
    right: 20px;
    width: 300px;
}
.plugin-dev-doc {
    position: absolute;
    right: 15px;
    top: 15px;
    z-index: 2;
    font-size: 12px;
    color: #3a84ff;
    cursor: pointer;
}
/deep/.group-area {
    float: left;
    width: 270px;
    height: 100%;
    background-image: linear-gradient(to right, transparent 269px,#e2e4ed 0);
    background-color: #fafbfd;
    overflow: auto;
    @include scrollbar;
    .group-item {
        position: relative;
        padding: 0 18px;
        font-size: 14px;
        color: #63656e;
        height: 42px;
        line-height: 42px;
        border-bottom: 1px solid #e2e4ed;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
        cursor: pointer;
        &:hover {
            color: #3a84ff;
        }
        &.active {
            color: #3a84ff;
            background: #ffffff;
            border-right: 1px solid #ffffff;
        }
    }
}
.selector-area {
    margin-left: 270px;
    height: 100%;
    font-size: 12px;
    color: #63656e;
    overflow: auto;
    @include scrollbar;
    .list-item {
        position: relative;
        padding: 0 40px 0 20px;
        height: 42px;
        line-height: 42px;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
        cursor: pointer;
        &:hover {
            background: #e1ecff;
            color: #3a84ff;
        }
        &.active {
            background: #e1ecff;
            & > .node-name {
                color: #3a84ff;
            }
        }
    }
}
.third-party-list {
    height: calc(100vh - 110px);
    overflow: auto;
    @include scrollbar;
    .plugin-item {
        height: 80px;
        display: flex;
        align-items: center;
        cursor: pointer;
        padding: 0 59px 0 38px;
        color: #63656e;
        font-size: 12px;
        .plugin-logo {
            width: 48px;
            height: 48px;
            margin-right: 16px;
            flex-shrink: 0;
        }
        .plugin-title {
            font-size: 14px;
            font-weight: 700;
            margin-bottom: 4px;
        }
        .plugin-desc {
            width: 375px;
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
        }
        .plugin-contact {
            color: #c4c6cc;
            font-weight: 700;
        }
        &.is-active, &:hover {
            background: hsl(218, 100%, 94%);
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
}
.no-data-wrapper {
    margin-top: 50px;
}
</style>
