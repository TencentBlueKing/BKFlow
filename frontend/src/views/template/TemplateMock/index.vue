<template>
  <div
    v-bkloading="{ isLoading: templateDataLoading, zIndex: 100 }"
    class="template-mock">
    <Header
      ref="mockHeader"
      :tpl-name="tplName"
      :mock-step="mockStep"
      :save-loading="saveLoading"
      :execute-loading="executeLoading"
      :tpl-actions="tplActions"
      @onChange="mockTaskName = $event"
      @onReturn="onReturnMock"
      @onExecute="onExecuteMock"
      @onSave="onSaveTplMockData" />
    <template v-if="mockStep === 'setting' && !templateDataLoading">
      <component
        :is="canvasMode === 'vertical' ? 'VerticalCanvas' : 'ProcessCanvas'"
        ref="processCanvas"
        :key="templateDataLoading"
        class="canvas-wrapper"
        :editable="false"
        :canvas-data="canvasData"
        :node-variable-info="nodeVariableInfo"
        :show-palette="false"
        :is-all-selected="isAllSelected"
        :is-show-select-all-tool="isSelectAllShow"
        @onNodeCheckClick="onNodeCheckClick"
        @onConditionClick="onOpenConditionEdit"
        @onToggleAllNode="onToggleAllNode"
        @onShowNodeConfig="onShowNodeConfig" />
      <MockSetting
        v-if="isShowMockSetting"
        :is-show="isShowMockSetting"
        :node-id="curSelectedNodeId"
        :mock-data="mockData[curSelectedNodeId]"
        :tpl-actions="tplActions"
        @updateMockData="updateMockData"
        @onClose="isShowMockSetting = false" />
      <condition-edit
        v-if="isShowConditionEdit"
        ref="conditionEdit"
        :is-show="isShowConditionEdit"
        :is-readonly="true"
        :gateways="gateways"
        :condition-data="conditionData"
        :space-related-config="spaceRelatedConfig"
        @close="isShowConditionEdit = false" />
    </template>
    <MockExecute
      v-else-if="!templateDataLoading"
      ref="mockExecute"
      :mock-task-name="mockTaskName"
      :template-id="templateId"
      :selected-nodes="selectedNodes"
      :tpl-actions="tplActions"
      @onReturn="onReturnMock" />
  </div>
</template>

<script>
  import ProcessCanvas from '@/components/canvas/ProcessCanvas/index.vue';
  import VerticalCanvas from '@/components/canvas/VerticalCanvas/index.vue';
  import { graphToJson } from '@/utils/graphJson.js';
  import { mapState, mapActions, mapMutations } from 'vuex';
  import Header from './Header.vue';
  import MockSetting from './MockSetting/index.vue';
  import MockExecute from './MockExecute/index.vue';
  import ConditionEdit from '../TemplateEdit/ConditionEdit.vue';
  import tools from '@/utils/tools';
  import bus from '@/utils/bus.js';
  export default {
    name: 'TemplateMock',
    components: {
      Header,
      ProcessCanvas,
      VerticalCanvas,
      MockSetting,
      MockExecute,
      ConditionEdit,
    },
    props: {
      templateId: {
        type: [Number, String],
        default: '',
      },
      common: {
        type: String,
        default: '',
      },
      version: {
        type: [String, null],
        default: '',
      },
      isEnableVersionManage: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        mockStep: 'setting',
        mockData: {},
        initMockData: {},
        templateDataLoading: true,
        pollingTimer: null,
        tplActions: [],
        selectedNodes: [],
        isAllSelected: true,
        isPerspective: false, // 流程是否透视
        nodeVariableInfo: {}, // 节点输入输出变量
        isShowMockSetting: false,
        curSelectedNodeId: '',
        saveLoading: false,
        executeLoading: false,
        mockSchemeId: '',
        lastSchemeMsg: null,
        isShowConditionEdit: false,
        conditionData: {},
        spaceRelatedConfig: {}, // 空间相关配置
        tplSpaceId: '', // 模板对应的空间id
        mockTaskName: '',
      };
    },
    computed: {
      ...mapState({
        isIframe: state => state.isIframe,
        spaceId: state => state.template.spaceId,
        tplName: state => state.template.name,
        activities: state => state.template.activities,
        locations: state => state.template.location,
        lines: state => state.template.line,
        constants: state => state.template.constants,
        gateways: state => state.template.gateways,
        start_event: state => state.template.start_event,
        end_event: state => state.template.end_event,
        internalVariable: state => state.template.internalVariable,
        infoBasicConfig: state => state.infoBasicConfig,
        canvasMode: state => state.template.canvas_mode,
        isAdmin: state => state.isAdmin,
        isCurSpaceSuperuser: state => state.isCurSpaceSuperuser,
      }),
      ...mapState('project', {
        timeZone: state => state.timezone,
        projectId: state => state.project_id,
      }),
      canvasData() {
        const mockNodes = Object.keys(this.mockData);
        const locations = this.locations.map((item) => {
          const data = { ...item, mode: 'select', status: '' };
          data.create_method = mockNodes.includes(item.id) ? 'mock' : '';
          if (item.optional) {
            data.checked = this.selectedNodes.includes(item.id);
          }
          return data;
        });
        return graphToJson({
          lines: this.lines,
          locations,
        });
      },
      isSelectAllShow() {
        return this.locations.some(item => item.optional);
      },
      hasSelectNode() {
        let hasSelected = !!this.selectedNodes.length;
        hasSelected = hasSelected || Object.values(this.activities).some(item => !item.optional);
        return hasSelected;
      },
    },
    watch: {
      '$route.params': {
        handler(val) {
          this.mockStep = val.step || 'setting';
          this.initData();
        },
        immediate: true,
      },
    },
    created() {
      window.addEventListener('beforeunload', this.handleBeforeUnload, false);
    },
    beforeDestroy() {
      window.removeEventListener('beforeunload', this.handleBeforeUnload, false);
    },
    methods: {
      ...mapActions([
        'updateToken',
      ]),
      ...mapActions('template/', [
        'loadProjectBaseInfo',
        'loadTemplateData',
        'getVariableCite',
        'getTemplateMockData',
        'setTemplateMockData',
        'getTemplateMockScheme',
        'updateTplMockScheme',
        'loadSpaceRelatedConfig',
        'getDraftVersionData',
      ]),
      ...mapMutations('template/', [
        'setTemplateData',
        'setPipelineTree',
      ]),
      ...mapMutations([
        'setSpaceId',
      ]),
      async initData() {
        try {
          this.templateDataLoading = true;
          await this.getTemplateData();
          if (this.mockStep === 'setting') {
            await this.getMockData();
            this.getSpaceRelatedConfig();
          }
          await this.loadTplMockScheme();
          // 轮询更新token
          if (!this.isAdmin && !this.isCurSpaceSuperuser) {
            this.pollingToken();
          }
        } catch (error) {
          console.warn(error);
        } finally {
          this.templateDataLoading = false;
        }
      },
      /**
       * 获取模板详情
       */
      async getTemplateData() {
        try {
          const data = {
            templateId: this.templateId,
            common: this.common,
          };
          const templateData = await this.loadTemplateData(data);
          this.tplActions = templateData.auth;
          this.tplSpaceId = templateData.space_id;
          this.setTemplateData(templateData);
          this.setSpaceId(templateData.space_id);
          if (this.isEnableVersionManage && (this.version === null || this.version === '')) {
            const draftTplData = await this.getDraftVersionData({
              templateId: this.templateId,
              common: this.common,
              space_id: this.spaceId
            });
            await this.setPipelineTree(draftTplData.data.pipeline_tree);
          }
          this.selectedNodes = [];
          this.allSelectableNodes = this.locations.filter((item) => {
            if (item.optional) {
              this.selectedNodes.push(item.id);
              return true;
            }
            return false;
          });
          this.isAllSelected = this.selectedNodes.length === this.allSelectableNodes.length;
        } catch (e) {
          if (e.status === 404) {
            this.$router.push({ name: 'notFoundPage' });
          }
          console.log(e);
        }
      },
      // 获取mock数据
      async getMockData() {
        try {
          if (!this.tplActions.includes('MOCK')) return;

          const resp = await this.getTemplateMockData({
            space_id: this.spaceId,
            template_id: this.templateId,
          });
          this.templateDataLoading = false;
          this.mockData = resp.data.reduce((acc, cur) => {
            if (cur.node_id in acc) {
              acc[cur.node_id].push(cur);
            } else {
              acc[cur.node_id] = [cur];
            }
            return acc;
          }, {});
          this.initMockData = tools.deepClone(this.mockData);
        } catch (error) {
          console.warn(error);
        }
      },
      // 获取模板mock方案
      async loadTplMockScheme() {
        try {
          const resp = await this.getTemplateMockScheme({
            space_id: this.spaceId,
            template_id: this.templateId,
          });
          const { results } = resp.data;
          if (results && results.length) {
            const { nodes = [] } = results[0].data;
            if (this.mockStep === 'setting') {
              this.mockSchemeId = results[0].id;
              const h = this.$createElement;
              const self = this;
              this.lastSchemeMsg = this.$bkMessage({
                extCls: 'last-scheme-message',
                message: h('div', {
                  style: { display: 'flex', justifyContent: 'space-between', width: '100%' },
                }, [
                  this.$t('自动载入上次调试选择的节点？'),
                  h('span', {
                    style: {
                      flexShrink: 0,
                      margin: '0 5px',
                      color: '#3a84ff',
                      cursor: 'pointer',
                    },
                    on: {
                      click() {
                        self.selectedNodes = [...nodes];
                        self.isAllSelected = nodes.length === self.allSelectableNodes.length;
                        self.locations.forEach((item) => {
                          if (item.optional) {
                            self.onUpdateNodeInfo(item.id, { checked: nodes.includes(item.id) });
                          }
                        });
                        self.lastSchemeMsg.close();
                        self.lastSchemeMsg = null;
                      },
                    },
                  }, this.$t('载入')),
                ]),
                theme: 'primary',
                delay: 10000,
              });
            } else {
              this.selectedNodes = [...nodes];
            }
          }
        } catch (error) {
          console.warn(error);
        }
      },
      // 轮询更新token
      pollingToken() {
        this.pollingTimer = setTimeout(async () => {
          clearTimeout(this.pollingTimer);
          await this.updateToken();
          this.pollingToken();
        }, 1000 * 60 * 5);
      },
      // 切换全选
      onToggleAllNode(val) {
        this.isAllSelected = val;
        this.locations.forEach((item) => {
          if (item.optional) {
            this.onUpdateNodeInfo(item.id, { checked: val });
          }
        });
        if (val) {
          const selectableNodes = this.allSelectableNodes.map(item => item.id);
          this.selectedNodes = selectableNodes;
        } else {
          this.selectedNodes = [];
        }
      },
      // 节点勾选
      onNodeCheckClick(id, val) {
        this.onUpdateNodeInfo(id, { checked: val });
        if (!val) {
          this.isAllSelected = false;
          this.selectedNodes = this.selectedNodes.filter(item => item !== id);
        } else {
          if (this.selectedNodes.length === this.allSelectableNodes.length - 1) {
            this.isAllSelected = true;
          }
          this.selectedNodes.push(id);
        }
      },
      // 更新单个节点的信息
      onUpdateNodeInfo(id, data) {
        this.$refs.processCanvas && this.$refs.processCanvas.onUpdateNodeInfo(id, data);
      },
      // 打开分支条件编辑
      onOpenConditionEdit(data) {
        this.isShowConditionEdit = true;
        this.conditionData = { ...data };
      },
      // 打开节点mock面板
      onShowNodeConfig(id) {
        this.isShowMockSetting = true;
        this.curSelectedNodeId = id;
      },
      // 退出调试
      onReturnMock() {
        if (this.mockStep === 'setting') {
          if (this.$router.history.length > 1) {
            this.$router.back();
          } else {
            this.$router.push({
              name: 'templatePanel',
              params: {
                templateId: this.templateId,
                type: 'edit',
                version: this.version,
                isVersionManageQuitMock: this.isEnableVersionManage,
              },
            });
          }
          return;
        }
        const { mockExecute } = this.$refs;
        const isEqual = mockExecute ? mockExecute.judgeDataEqual() : true;
        const navigateBack = () => {
          this.$router.replace({
            name: 'templateMock',
            params: {
              templateId: this.templateId,
            },
          });
        };
        if (!isEqual) {
          this.$bkInfo({
            ...this.infoBasicConfig,
            confirmFn: navigateBack,
          });
        } else {
          navigateBack();
        }
      },
      // mock调试
      async onExecuteMock() {
        if (!this.hasSelectNode) {
          this.$bkMessage({
            message: this.$t('请至少选择一个节点'),
            theme: 'error',
          });
          return;
        }
        try {
          const isEqual = this.judgeDataEqual();
          if (!isEqual) {
            this.$bkInfo({
              title: this.$t('确定保存Mock数据并去执行调试?'),
              maskClose: false,
              width: 400,
              confirmLoading: true,
              cancelText: this.$t('取消'),
              confirmFn: this.confirmExecute,
            });
          } else {
            this.confirmExecute();
          }
        } catch (error) {
          console.warn(error);
        }
      },
      async confirmExecute() {
        try {
          this.executeLoading = true;
          await this.onSaveTplMockData();
          this.routerJump();
        } catch (error) {
          console.warn(error);
        } finally {
          this.executeLoading = false;
        }
      },
      routerJump() {
        const route = {
          name: 'templateMock',
          params: {
            templateId: this.templateId,
            step: 'execute',
          },
        };

        if (this.isIframe) {
          this.$router.push(route);
        } else {
          const { href } = this.$router.resolve(route);
          window.open(href, '_blank');
        }
      },
      // 更新节点mock数据
      updateMockData(data = {}) {
        Object.assign(this.mockData, data);
        Object.keys(data).forEach((key) => {
          this.onUpdateNodeInfo(key, { create_method: data[key].length ? 'mock' : '' });
        });
      },
      // 保存mock数据
      async onSaveTplMockData() {
        try {
          if (!this.hasSelectNode) {
            this.$bkMessage({
              message: this.$t('请至少选择一个节点'),
              theme: 'error',
            });
            return;
          }
          this.saveLoading = true;
          // 如果mock数据没有改变则不掉接口
          const isEqual = this.judgeDataEqual();
          if (!isEqual) {
            await this.setTemplateMockData({
              space_id: this.spaceId,
              template_id: this.templateId,
              data: this.mockData,
            });
            this.initMockData = tools.deepClone(this.mockData);
          }
          // 更新节点勾选方案
          const resp = await this.updateTplMockScheme({
            space_id: this.spaceId,
            template_id: this.templateId,
            data: {
              nodes: [...this.selectedNodes],
            },
            schemeId: this.mockSchemeId,
          });
          this.mockSchemeId = resp.data.id;
          this.$bkMessage({
            message: this.$t('模板mock数据保存成功'),
            theme: 'success',
          });
        } catch (error) {
          console.warn(error);
        } finally {
          this.saveLoading = false;
        }
      },
      judgeDataEqual() {
        return tools.isDataEqual(this.initMockData, this.mockData);
      },
      // 获取空间相关配置
      async getSpaceRelatedConfig() {
        try {
          const resp = await this.loadSpaceRelatedConfig({ id: this.templateId });
          if (resp.result) {
            this.spaceRelatedConfig = resp.data;
          }
        } catch (error) {
          console.warn(error);
        }
      },
      handleBeforeUnload(e) {
        e.returnValue = this.$t('系统不会保存您所做的更改，确认离开？');
        return this.$t('系统不会保存您所做的更改，确认离开？');
      },
    },
    beforeRouteLeave(to, from, next) {
      let isEqual = true;
      if (this.mockStep === 'setting') {
        isEqual = this.judgeDataEqual();
      } else {
        const { mockExecute } = this.$refs;
        isEqual = mockExecute ? mockExecute.judgeDataEqual() : true;
      }
      if (!isEqual) {
        this.$bkInfo({
          ...this.infoBasicConfig,
          cancelFn: () => {
            bus.$emit('cancelRoute');
            this.setSpaceId(this.tplSpaceId);
          },
          confirmFn: () => {
            next();
          },
        });
      } else {
        next();
      }
    },
  };
</script>

<style lang="scss" scoped>
.template-mock {
  position: relative;
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  .canvas-wrapper {
    flex: 1;
    ::v-deep .x6-graph{
      background: #f5f7fa;
    }
  }
}
</style>
<style lang="scss">
.last-scheme-message {
  width: 400px !important;
  .icon-close {
    margin-left: 0 !important;
  }
}
</style>
