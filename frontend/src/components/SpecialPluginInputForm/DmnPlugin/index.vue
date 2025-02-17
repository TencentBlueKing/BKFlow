<template>
  <div class="dmn-plugin">
    <bk-form
      ref="dmnForm"
      :label-width="100"
      :model="formData">
      <bk-form-item
        :label="$t('决策表')"
        :required="true"
        property="table_id"
        :rules="rules.required">
        <bk-select
          ref="decisionSelect"
          v-model="formData.table_id"
          :disabled="isViewMode"
          :allow-create="isNotExist"
          ext-cls="decision-selector"
          :show-empty="!decisionListLoading"
          :popover-options="{ appendTo: 'parent', hideOnClick: !selectedOption.id }"
          @toggle="handleSelectToggle"
          @change="handleSelectChange">
          <div
            v-bkloading="{ isLoading: decisionListLoading }"
            :style="`min-height: ${decisionListLoading ? '32px' : '0'}`">
            <bk-option
              v-for="option in decisionTableList"
              :id="option.id"
              :key="option.id"
              :name="option.name">
              <div
                :class="['option-content', { 'is-active': selectedOption.id === option.id }]"
                @click.stop>
                <span
                  class="name"
                  @click="handleOptionClick(option)">{{ option.name }}</span>
                <div
                  class="operate-btn"
                  @click="toggleDecisionSlider(option)">
                  <i class="common-icon-audit" />
                  <span>{{ $t('查看') }}</span>
                </div>
                <div
                  class="operate-btn"
                  @click="jumpDecisionEdit(option.id)">
                  <i class="common-icon-edit" />
                  <span>{{ $t('编辑') }}</span>
                </div>
                <div
                  class="operate-btn"
                  @click="setSelectedOption(option)">
                  <decision-delete
                    :data="option"
                    :text="true"
                    @cancel="setSelectedOption()"
                    @onDeleted="onDecisionDeleted">
                    <i class="common-icon-delete" />
                  </decision-delete>
                </div>
              </div>
            </bk-option>
          </div>
          <div
            slot="extension"
            class="select-extension">
            <div @click="jumpDecisionEdit()">
              <i class="bk-icon icon-plus-circle" />
              <span>{{ $t('新建决策表') }}</span>
            </div>
            <i
              class="bk-icon icon-refresh"
              @click="onRefresh" />
          </div>
        </bk-select>
        <i
          v-if="tabledDesc"
          v-bk-tooltips.top="{
            content: filterXSS(tabledDesc),
            allowHTML: false,
            multiple: true,
            maxWidth: 400
          }"
          class="bk-icon icon-question-circle desc-icon" />
        <p
          v-if="isNotExist"
          class="not-exist-tips">
          {{ $t('无法获取决策表配置数据，引用的决策表可能已被删除') }}
        </p>
      </bk-form-item>
      <bk-form-item
        v-if="inputs.length"
        :label="$t('字段输入')"
        :required="true">
        <div class="field-input-wrap">
          <bk-form-item
            v-for="(item, index) in inputs"
            :key="item.id"
            ref="formItem"
            :required="true"
            :property="item.id"
            :rules="rules.required">
            <input-item
              :inputs="item"
              :form-data="formData"
              :is-view-mode="isViewMode || isNotExist"
              :variable-list="varSortList"
              @clear="clearValidator(index)" />
          </bk-form-item>
        </div>
      </bk-form-item>
    </bk-form>
    <!--决策表查看-->
    <decision-view
      :is-show="isDecisionViewShow"
      :row="selectedOption"
      :space-id="spaceId"
      @close="toggleDecisionSlider()"
      @onDeleted="onDecisionDeleted" />
    <!--决策表编辑-->
    <bk-dialog
      v-model="isDecisionEditDialogShow"
      class="decision-edit-dialog"
      :close-icon="false"
      :fullscreen="true"
      :show-footer="false">
      <decision-edit
        v-if="isDecisionEditDialogShow"
        :space-id="spaceId"
        path="decision"
        :decision-id="decisionId"
        :template-id="templateId"
        @close="closeDecisionEditDialog" />
    </bk-dialog>
  </div>
</template>

<script>
  import InputItem from './InputItem.vue';
  import tools from '@/utils/tools.js';
  import { mapActions, mapState } from 'vuex';
  import DecisionView from '@/views/admin/Space/DecisionTable/components/DecisionView.vue';
  import DecisionEdit from '@/views/admin/Space/DecisionTable/components/DecisionEdit.vue';
  import DecisionDelete from '@/views/admin/Space/DecisionTable/components/DecisionDelete.vue';
  export default {
    name: 'DmnInputParams',
    components: {
      InputItem,
      DecisionView,
      DecisionEdit,
      DecisionDelete,
    },
    props: {
      isViewMode: {
        type: Boolean,
        default: true,
      },
      spaceId: {
        type: [String, Number],
        default: '',
      },
      templateId: {
        type: [String, Number],
        default: '',
      },
      variableList: {
        type: Array,
        default: () => ([]),
      },
      value: {
        type: Object,
        default: () => ({}),
      },
      nodeId: {
        type: String,
        default: '',
      },
      inputsVariableFields: {
        type: Array,
        default: () => ([]),
      },
      variableCited: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        formData: {},
        facts: {},
        rules: {
          required: [
            {
              required: true,
              message: this.$t('必填项'),
              trigger: 'blur',
            },
          ],
        },
        inputs: [],
        outputs: [],
        decisionListLoading: false,
        decisionTableList: [],
        varModeFields: [], // 初始化时是变量模式的字段
        tabledDesc: '', // 决策表描述
        isNotExist: false, // 决策表是否存在
        selectedOption: {}, // 选中的决策表
        isDecisionViewShow: false,
        decisionId: '',
        isDecisionEditDialogShow: false,
      };
    },
    computed: {
      ...mapState({
        activities: state => state.template.activities,
        isAdmin: state => state.isAdmin,
        isIframe: state => state.isIframe,
      }),
      varSortList() {
        const priority = {
          custom: 1,
          component_inputs: 2,
          component_outputs: 2,
          system: 3,
        };
        return this.variableList.sort((a, b) => priority[a.source_type] - priority[b.source_type]);
      },
    },
    watch: {
      formData: {
        handler(val) {
          const varModeFields = this.inputs.reduce((acc, cur) => {
            if (cur.variableMode) {
              acc.push(cur.id);
            }
            return acc;
          }, []);
          this.$emit('update', val, varModeFields);
        },
        deep: true,
      },
      inputs(val) {
        this.$emit('updateInput', val);
      },
    },
    async created() {
      // 表单值
      this.varModeFields = [...this.inputsVariableFields];
      const formData = {
        table_id: '', // form必须要有table_id字段
        ...tools.deepClone(this.value),
      };
      const { table_id: tableId, facts = {} } = formData;
      Object.keys(facts).forEach((key) => {
        formData[key] = facts[key].value;
        if (facts[key].variable) {
          this.varModeFields.push(key);
        }
      });
      this.facts = tools.deepClone(facts);
      delete formData.facts;
      this.formData = formData;
      // 决策表列表
      await this.getDecisionTableList();
      // 初始化时如果存在决策表id则主动触发选中change
      if (tableId) {
        this.handleSelectChange();
      }
    },
    methods: {
      ...mapActions('decisionTable/', [
        'getDecisionData',
        'loadDecisionList',
        'deleteDecision',

      ]),
      async getDecisionTableList() {
        try {
          if (this.decisionListLoading) return;
          this.decisionListLoading = true;
          const params = {
            space_id: this.spaceId,
            template_id: this.templateId,
          };
          if (this.isViewMode) {
            params.id = this.formData.table_id;
            const resp = await this.getDecisionData(params);
            this.decisionTableList = resp.result ? [resp.data] : [];
          } else {
            const resp = await this.loadDecisionList(params);
            this.decisionTableList = resp.data.results;
          }
        } catch (error) {
          console.warn(error);
        } finally {
          this.decisionListLoading = this.false;
        }
      },
      async handleSelectToggle(val) {
        if (!val) return;
        this.$emit('updateVarCitedData');
      },
      handleSelectChange() {
        const { table_id: tableId } = this.formData;
        let inputs = [];
        let outputs = [];
        if (tableId) {
          const decisionInfo = this.decisionTableList.find(item => item.id === tableId);
          // 未匹配到决策表
          if (!decisionInfo) {
            this.inputs = Object.keys(this.facts).reduce((acc, key) => {
              acc.push({ id: key, name: key });
              return acc;
            }, []);
            this.isNotExist = true;
            return;
          }
          inputs = decisionInfo.data.inputs.map(item => ({
            ...item,
            variableMode: this.varModeFields.includes(item.id),
          }));
          outputs = decisionInfo.data.outputs.map(item => ({
            ...item,
            key: item.id,
            fromDmn: true,
          }));
          this.tabledDesc = decisionInfo.desc;
        }
        this.formData = inputs.reduce((acc, cur) => {
          acc[cur.id] = this.formData[cur.id] || '';
          return acc;
        }, { table_id: tableId });
        this.inputs = tools.deepClone(inputs);
        this.outputs = tools.deepClone(outputs);
        this.isNotExist = false;
        this.varModeFields = [];
        this.$emit('updateOutputs', outputs);
      },
      handleOptionClick(option) {
        const fieldIds = this.outputs.map(item => `$\{${item.id}}`);
        const varList = fieldIds.filter(key => key in this.variableCited);
        if (varList.length) {
          const h = this.$createElement;
          this.$bkInfo({
            subHeader: h('div', { class: 'custom-header' }, [
              h('div', {
                class: 'custom-header-title',
                directives: [{
                  name: 'bk-overflow-tips',
                }],
              }, [this.$t('切换决策表输出参数将被清除，是否继续切换？')]),
            ]),
            extCls: 'dialog-custom-header-title',
            maskClose: false,
            width: 500,
            confirmLoading: true,
            cancelText: this.$t('取消'),
            confirmFn: async () => {
              this.formData.table_id = option.id;
              this.close();
            },
          });
          return;
        }
        this.formData.table_id = option.id;
        this.close();
      },
      close() {
        this.$refs.decisionSelect.close();
      },
      toggleDecisionSlider(option) {
        this.selectedOption = option || {};
        this.isDecisionViewShow = !!option;
      },
      jumpDecisionEdit(id) {
        if (this.isIframe) {
          this.decisionId = id;
          this.isDecisionEditDialogShow = true;
          return;
        }
        const { href } = this.$router.resolve({
          name: 'decisionEdit',
          params: { path: 'decision', decisionId: id },
          query: {
            space_id: this.spaceId,
            template_id: this.templateId,
          },
        });
        window.open(href, '_blank');
      },
      onDecisionDeleted() {
        // 如果删除的决策表正被选中，则清空
        if (this.selectedOption.id === this.formData.table_id) {
          this.formData = { table_id: '' };
        }
        // 重新拉取列表
        this.getDecisionTableList();
        // 关闭侧栏
        this.toggleDecisionSlider();
      },
      setSelectedOption(option = {}) {
        // 删除确认框关闭是缓慢收起，则需要在关闭后在设置选中态
        setTimeout(() => {
          this.selectedOption = option;
        }, 200);
      },
      // 决策表刷新
      async onRefresh() {
        try {
          // 重新拉取列表
          await this.getDecisionTableList();
          // 重新获取决策表配置
          this.handleSelectChange();
        } catch (error) {
          console.warn(error);
        }
      },
      closeDecisionEditDialog(updated) {
        this.decisionId = '';
        this.isDecisionEditDialogShow = false;
        if (updated) {
          this.onRefresh();
        }
      },
      clearValidator(index) {
        this.$refs.formItem[index].clearValidator();
      },
      validate() {
        return this.$refs.dmnForm.validate();
      },
    },
  };
</script>

<style lang="scss">
  .decision-edit-dialog {
    .bk-dialog-tool {
      display: none;
    }
    .bk-dialog-header {
      padding: 0;
    }
    .bk-dialog-body {
      padding: 0;
    }
  }
  .compare-menu-popover {
    z-index: 2500 !important;
  }
</style>
<style lang="scss" scoped>
.dmn-plugin {
  .decision-selector {
    &.is-disabled {
      /deep/.bk-select-name {
        pointer-events: none;
        background: #fafbfd;
      }
    }
    .bk-select-dropdown-content {
      padding-top: 5px;
    }
    .option-content {
      display: flex;
      align-items: center;
      height: 32px;
      line-height: 20px;
      .name {
        flex: 1;
      }
      .operate-btn {
        display: none;
        flex-shrink: 0;
        align-items: center;
        margin-left: 12px;
        color: #3a84ff;
        font-size: 12px;
        cursor: pointer;
        i {
          margin-right: 5px;
        }
        /deep/.bk-button-text {
          font-size: 12px;
        }
      }
      &.is-active,
      &:hover {
        .operate-btn {
          display: flex;
        }
      }
    }
    .select-extension {
      display: flex;
      align-items: center;
      height: 40px;
      > div {
        flex: 1;
        text-align: center;
        margin-right: 16px;
        border-right: 1px solid #dcdee5;
        line-height: 20px;
      }
    }
  }
  .desc-icon {
    position: absolute;
    bottom: 9px;
    right: 30px;
    font-size: 14px;
    color: #979ba5;
  }
  .not-exist-tips {
    font-size: 12px;
    line-height: 20px;
    color: #ea3636;
  }
  .field-input-wrap {
    padding: 12px 16px;
    background: #fafbfd;
    border: 1px solid #eaebf0;
    border-radius: 2px;
    /deep/.bk-form-content {
      margin-left: 0 !important;
    }
    /deep/.bk-form-item {
      &.is-error{
        .icon-exclamation-circle-shape {
          right: 40px !important;
        }
      }
      &:first-child::before {
        display: none;
      }
      &:last-child .input-item{
        margin-bottom: 0;
      }
    }
  }
}
</style>
