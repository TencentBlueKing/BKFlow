<template>
  <bk-sideslider
    :is-show="true"
    :width="800"
    :quick-close="true"
    :before-close="closePanel">
    <div
      slot="header"
      class="setting-header">
      <span
        :class="[variableData ? 'active' : '']"
        @click="onBackToList">{{ $t('循环输出') }}</span>
      <span v-if="variableData">
        {{ '> ' }}
        {{
          variableData.key
            ? $t('编辑')
            : $t('新建')
        }}
      </span>
      <div id="loop-var-desc">
        <div class="tips-item">
          <h4>{{ $t('属性：') }}</h4>
          <p>
            {{ $t('"来源/是否显示"格式，来源是输入类型') }}
            <i
              class="common-icon-show-left"
              style="color: #219f42" />
            {{ $t('表示变量来自用户添加的变量或者标准插件/子流程节点输入参数引用的变量，来源是输出类型') }}
            <i
              class="common-icon-hide-right"
              style="color: #de9524" />
            {{ $t('表示变量来自标准插件/子流程节点输出参数引用的变量；是否显示表示该变量在新建任务填写参数时是否展示给用户，') }}
            <i
              class="common-icon-eye-show"
              style="color: #219f42;vertical-align: middle;" />
            {{ $t('表示显示，') }}
            <i
              class="common-icon-eye-hide"
              style="color: #de9524;vertical-align: middle;" />
            {{ $t('表示隐藏，输出类型的变量一定是隐藏的。') }}
          </p>
        </div>
        <div class="tips-item">
          <h4>{{ $t('输出：') }}</h4>
          <p>{{ $t('表示该变量会作为该循环节点的输出参数，在外层流程中可以引用。') }}</p>
        </div>
      </div>
    </div>
    <div
      slot="content"
      class="global-variable-panel">
      <div
        v-show="!variableData"
        :class="{ 'is-hidden': variableData }">
        <div class="add-variable">
          <template v-if="deleteVarListLen">
            <bk-button
              theme="default"
              class="delete-variable-btn"
              data-test-id="loopVariable_form_deleteVariable"
              @click="onDeleteVarList">
              {{ $t('删除') }}
            </bk-button>
            <span class="delete-variable-txt">{{ $t('已选择x项', { num: deleteVarListLen }) }}</span>
            <bk-button
              :text="true"
              class="f12"
              @click="deleteVarList = []">
              {{ $t('清空' ) }}
            </bk-button>
          </template>
          <i
            v-bk-tooltips="{
              allowHtml: true,
              content: '#loop-var-desc',
              placement: 'bottom-end',
              duration: 0,
              width: 400
            }"
            class="common-icon-info" />
        </div>
        <div
          class="global-variable-content"
          data-test-id="loopVariable_table_variableList">
          <div class="variable-header clearfix">
            <bk-checkbox
              v-if="!isViewMode && editVarList.length"
              :value="editVarList.length === deleteVarListLen"
              class="variable-checkbox"
              @change="onSelectAll" />
            <span class="col-name t-head">{{ $t('名称') }}</span>
            <span class="col-key t-head">KEY</span>
            <span class="col-cited t-head">
              {{ $t('引用') }}
            </span>
            <span class="col-type t-head">{{ $t('类型') }}</span>
            <span class="col-show t-head">{{ $t('显示（入参）') }}</span>
            <span class="col-output t-head">{{ $t('输出') }}</span>
            <span class="col-operation t-head">{{ $t('操作') }}</span>
          </div>
          <div v-bkloading="{ isLoading: varListLoading, zIndex: 10 }">
            <div class="variable-list">
              <draggable
                class="variable-drag"
                handle=".col-item-drag"
                :list="variableList"
                @end="onDragEnd($event)">
                <variable-item
                  v-for="constant in variableList"
                  :key="constant.key"
                  :outputed="outputs.indexOf(constant.key) > -1"
                  :variable-data="constant"
                  :variable-cited="variableCited"
                  :variable-checked="!!(deleteVarList.find(item => item.key === constant.key))"
                  :is-view-mode="isViewMode"
                  :is-loop-node="true"
                  :pipeline-tree-data="loopNode.pipeline"
                  @onEditVariable="onEditVariable"
                  @onDeleteVariable="onDeleteVariable"
                  @onChooseVariable="onChooseVariable"
                  @onChangeVariableShow="onChangeVariableShow"
                  @onChangeVariableOutput="onChangeVariableOutput"
                  @onCitedNodeClick="onCitedNodeClick" />
              </draggable>
              <div
                v-if="variableList.length === 0"
                class="empty-variable-tips">
                <NoData>
                  <p>{{ $t('无数据，请手动新增变量或者勾选标准插件参数自动生成') }}</p>
                </NoData>
              </div>
            </div>
          </div>
        </div>
      </div>
      <variable-edit
        v-if="variableData"
        ref="variableEdit"
        :variable-data="variableData"
        :is-view-mode="isViewMode"
        :constants="innerConstants"
        :use-store-directly="false"
        @closeEditingPanel="closeEditingPanel"
        @onSaveEditing="onSaveEditing" />
    </div>
  </bk-sideslider>
</template>

<script>
  import i18n from '@/config/i18n/index.js';
  import draggable from 'vuedraggable';
  import { mapState, mapActions } from 'vuex';
  import tools from '@/utils/tools.js';
  import VariableEdit from '../TemplateSetting/TabGlobalVariables/VariableEdit.vue';
  import VariableItem from '../TemplateSetting/TabGlobalVariables/VariableItem.vue';
  import NoData from '@/components/common/base/NoData.vue';

  export default {
    name: 'LoopGlobalVariables',
    components: {
      VariableEdit,
      VariableItem,
      draggable,
      NoData,
    },
    props: {
      loopNodeId: {
        type: String,
        required: true,
      },
      isViewMode: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        variableList: [], // 变量列表
        varListLoading: false,
        variableData: null, // 编辑中的变量
        editingOriginalKey: '', // 编辑变量时的原始 key
        variableCited: {}, // 变量引用情况
        deleteVarList: [], // 批量删除变量
        varTypeList: [],
      };
    },
    computed: {
      ...mapState({
        activities: state => state.template.activities,
        internalVariable: state => state.template.internalVariable,
      }),
      // 当前循环流节点
      loopNode() {
        return this.activities[this.loopNodeId] || null;
      },
      // 循环流节点的constants，只展示输出参数
      innerConstants() {
        if (this.loopNode && this.loopNode.pipeline && this.loopNode.pipeline.constants) {
          const result = {};
          const { constants } = this.loopNode.pipeline;
          Object.keys(constants).forEach((key) => {
            if (constants[key].source_type === 'component_outputs') {
              result[key] = constants[key];
            }
          });
          return result;
        }
        return {};
      },
      // 循环流节点的 outputs（用于判断是否输出，存储在 pipeline.outputs）
      outputs() {
        if (this.loopNode && this.loopNode.pipeline && this.loopNode.pipeline.outputs) {
          return this.loopNode.pipeline.outputs;
        }
        return [];
      },
      deleteVarListLen() {
        return this.deleteVarList.length;
      },
      editVarList() {
        return this.variableList.filter(item => item.source_type !== 'system' && item.source_type !== 'project');
      },
    },
    watch: {
      innerConstants() {
        this.setVariableList();
      },
    },
    created() {
      this.setVariableList();
      this.getVariableCitedData();
    },
    methods: {
      ...mapActions('template', [
        'getVariableCite',
      ]),
      getVariableCitedData() {
        try {
          if (!this.loopNode || !this.loopNode.pipeline) {
            return;
          }
          const data = {
            activities: this.loopNode.pipeline.activities || {},
            gateways: this.loopNode.pipeline.gateways || {},
            constants: { ...this.innerConstants },
          };
          this.getVariableCite(data).then((resp) => {
            if (resp.result) {
              this.variableCited = resp.data.defined;
            }
          });
        } catch (e) {
          console.warn(e);
        }
      },
      setVariableList() {
        try {
          this.varListLoading = true;
          const constants = this.innerConstants;
          const variableList = Object.keys(constants)
            .map(key => tools.deepClone(constants[key]))
            .sort((a, b) => a.index - b.index);
          this.variableList = variableList;
        } catch (error) {
          console.warn(error);
        } finally {
          this.varListLoading = false;
        }
      },
      // 点击面包屑返回变量列表
      onBackToList() {
        if (this.variableData) {
          this.closeEditingPanel();
        }
      },
      // 变量拖拽，改变顺序
      onDragEnd(event) {
        const { newIndex, oldIndex } = event;
        if (newIndex === oldIndex) {
          return;
        }
        const start = Math.min(newIndex, oldIndex);
        const end = Math.max(newIndex, oldIndex) + 1;
        const indexChangedVar = this.variableList.slice(start, end);

        indexChangedVar.forEach((item, index) => {
          item.index = index + start;
          this.updateVariable(item.key, tools.deepClone(item));
        });
      },
      /**
       * 打开编辑变量面板
       * @param {String} key 变量key值
       */
      onEditVariable(key) {
        this.editingOriginalKey = key;
        const variableData = tools.deepClone(this.innerConstants[key]);
        if (!('is_condition_hide' in variableData)) {
          variableData.is_condition_hide = 'false';
        }
        const { activities, conditions, constants } = this.variableCited[key] || { activities: [], conditions: [], constants: [] };
        const cited = activities.length + conditions.length + constants.length;
        this.variableData = {
          ...variableData,
          cited,
        };
      },
      onCitedNodeClick(data) {
        const { group, id } = data;
        if (group === 'constants') {
          this.onEditVariable(id);
        } else if (group === 'activities' || group === 'conditions') {
          // 通知父组件关闭变量面板并打开节点/条件配置面板
          this.$emit('onLoopVariableCitedNodeClick', data);
        }
      },
      /**
       * 变量显示勾选
       */
      onChangeVariableShow({ key, checked }) {
        const variableData = tools.deepClone(this.innerConstants[key]);
        if (variableData) {
          variableData.show_type = checked ? 'show' : 'hide';
          this.updateVariable(key, variableData);
        }
      },
      /**
       * 变量输出勾选
       */
      onChangeVariableOutput({ key, checked }) {
        this.$emit('onChangeVariableOutput', { key, checked, loopNodeId: this.loopNodeId });
      },
      /**
       * 删除变量
       */
      onDeleteVariable(key) {
        this.$bkInfo({
          title: `${i18n.t('确认删除') + i18n.t('全局变量')}"${key}"?`,
          subTitle: i18n.t('若该变量被节点引用，请及时检查并更新节点配置'),
          maskClose: false,
          width: 450,
          confirmLoading: true,
          confirmFn: () => {
            this.deleteVariable(key);
            this.getVariableCitedData();
            this.$bkMessage({
              theme: 'success',
              message: i18n.t('变量') + i18n.t('删除成功！'),
            });
          },
        });
      },
      onChooseVariable(variable, isChecked) {
        if (isChecked) {
          this.deleteVarList.push(variable);
        } else {
          const index = this.deleteVarList.findIndex(item => item.key === variable.key);
          if (index > -1) {
            this.deleteVarList.splice(index, 1);
          }
        }
      },
      onDeleteVarList() {
        let title = '';
        if (this.deleteVarListLen === 1) {
          title = `${i18n.t('确认删除') + i18n.t('全局变量')}"${this.deleteVarList[0].key}"?`;
        } else {
          title = i18n.t('确认删除所选的x个变量?', { num: this.deleteVarListLen });
        }
        this.$bkInfo({
          title,
          subTitle: i18n.t('若该变量被节点引用，请及时检查并更新节点配置'),
          maskClose: false,
          width: 450,
          confirmLoading: true,
          confirmFn: () => {
            this.deleteVarList.forEach((variableData) => {
              this.deleteVariable(variableData.key);
            });
            this.deleteVarList = [];
            this.getVariableCitedData();
          },
        });
      },
      // 编辑变量后点击保存
      onSaveEditing(variableData) {
        if (this.editingOriginalKey) {
          // 编辑现有变量，用原始 key 定位要更新的变量
          this.updateVariable(this.editingOriginalKey, variableData);
          this.editingOriginalKey = '';
        }
        this.closeEditingPanel();
        this.getVariableCitedData();
      },
      // 关闭变量编辑面板
      closeEditingPanel() {
        this.variableData = null;
        this.editingOriginalKey = '';
      },
      // 关闭面板
      closePanel() {
        if (!this.variableData) {
          this.$emit('close');
        } else {
          this.$refs.variableEdit.handleMaskClick();
        }
      },
      // 全选删除变量
      onSelectAll(isChecked) {
        if (isChecked) {
          this.deleteVarList = tools.deepClone(this.editVarList);
        } else {
          this.deleteVarList = [];
        }
      },
      // 更新变量
      updateVariable(key, variable) {
        this.$emit('updateVariable', { loopNodeId: this.loopNodeId, key, variable });
      },
      // 添加变量
      addVariable(variable) {
        this.$emit('addVariable', { loopNodeId: this.loopNodeId, variable });
      },
      // 删除变量
      deleteVariable(key) {
        this.$emit('deleteVariable', { loopNodeId: this.loopNodeId, key });
      },
    },
  };
</script>

<style lang="scss" scoped>
  @import '../../../../scss/mixins/scrollbar.scss';
  .setting-header {
    & > span.active {
      color: #3a84ff;
      cursor: pointer;
    }
    .common-icon-info {
      position: absolute;
      top: 22px;
      right: 30px;
      font-size: 16px;
      color: #c4c6cc;
      &:hover {
        color: #f4aa1a;
      }
    }
    #loop-var-desc {
      .tips-item {
        & > h4 {
          margin: 0;
        }
        &:not(:last-child) {
          margin-bottom: 10px;
        }
      }
    }
  }
  .global-variable-panel {
    height: calc(100vh - 60px);
    .is-hidden {
      transform: scale(0)
    }
    .delete-variable-btn {
      width: 90px;
    }
    .delete-variable-txt {
      font-size: 12px;
      padding: 0 10px;
    }
    .add-variable {
      position: relative;
      display: flex;
      align-items: center;
      padding: 30px 30px 20px;
      .add-variable-btn {
        width: 90px;
      }
      .common-icon-info {
        position: absolute;
        right: 30px;
        font-size: 16px;
        color: #c4c6cc;
        &:hover {
          color: #f4aa1a;
        }
      }
    }
    .global-variable-content {
      position: relative;
      margin: 0 30px;
      border: 1px solid #dcdee5;
    }
    .variable-header, .variable-list {
      position: relative;
      font-size: 12px;
      .variable-checkbox {
        position: absolute;
        top: 11px;
        left: 27px;
      }
      .col-name {
        margin-left: 55px;
        width: 160px;
      }
      .col-key {
        width: 130px;
      }
      .col-type {
        width: 80px;
      }
      .col-show {
        width: 100px;
      }
      .col-output {
        width: 50px;
      }
      .col-cited {
        width: 80px;
        margin: 0 5px 0 -5px;
      }
      .col-operation {
        width: 40px;
      }
    }
    .variable-header {
      height: 42px;
      line-height: 42px;
      background: #fafbfd;
      border-bottom: 1px solid #dcdee5;
      .t-head {
        float: left;
        height: 40px;
        line-height: 40px;
      }
    }
    .variable-list {
      width: 100%;
      max-height: calc(100vh - 214px);
      border-top: none;
      overflow-y: auto;
      @include scrollbar;
    }
    .empty-variable-tips {
      height: 280px;
      ::v-deep .no-data-wording {
        font-size: 12px;
      }
    }
  }
</style>
