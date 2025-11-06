<template>
  <div class="timed-trigger-wrapper">
    <bk-table :data="filteredTriggerData">
      <bk-table-column
        :label="$t('触发器')"
        :width="160"
        prop="name">
        <template slot-scope="{ row }">
          {{ row.name }}
          <div
            v-if="row.isNewTrigger"
            class="add-new-trigger">
            new
          </div>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('执行周期')"
        :width="160"
        prop="cron">
        <template slot-scope="{ row }">
          <bk-popover
            :content="translateCron(row.config.cron)"
            placement="right-end">
            <div>
              {{ joinCron(row.config.cron) }}
            </div>
          </bk-popover>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('启用状态') "
        prop="is_enabled">
        <template slot-scope="{ row }">
          <bk-switcher
            v-model="row.is_enabled"
            theme="primary"
            :disabled="isViewMode"
            @change="handelIsEnabledChange(row)" />
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('操作')"
        width="150">
        <template slot-scope="props">
          <bk-button
            theme="primary"
            text
            :disabled="isViewMode"
            @click="editTriggerConfig(props.row, props.$index)">
            {{ $t('编辑') }}
          </bk-button>
          <bk-button
            class="trigger-operation-button"
            theme="primary"
            text
            :disabled="isViewMode"
            @click="delItemTigger(props.row, props.$index)">
            {{ $t('删除') }}
          </bk-button>
        </template>
      </bk-table-column>
    </bk-table>
    <bk-popover
      :disabled="isAllowSetMultipleTrigger"
      :content="$t('只允许创建一个定时触发器')"
      placement="right">
      <bk-button
        :disabled="isViewMode || !isAllowSetMultipleTrigger && triggerData.length >= 1"
        theme="primary"
        icon="plus"
        class="add-trigger-button"
        :outline="true"
        @click="addTrigger">
        {{ $t('添加定时触发器') }}
      </bk-button>
    </bk-popover>

    <bk-dialog
      v-model="isShowTriggerDialog"
      theme="primary"
      :mask-close="false"
      :width="640"
      :auto-close="false"
      header-position="left"
      :title="type === 'edit' ? $t('修改定时触发器') : $t('添加定时触发器')"
      @confirm="onTriggerConfirm(type)"
      @cancel="onTriggerCancel">
      <bk-form
        ref="triggerForm"
        :label-width="70"
        :model="currentTriggerConfig">
        <bk-form-item
          :label="$t('执行周期')"
          property="cron">
          <CronRuleSelect
            ref="cronRuleSelect"
            v-model="currentJoinIcon"
            class="loop-rule" />
        </bk-form-item>
        <bk-form-item
          ref="codeFormItem"
          :label="$t('请求参数')"
          property="params">
          <div class="bk-button-group">
            <bk-button
              :class="currentTriggerConfig.config.mode === 'form' ? 'is-selected' : ''"
              @click="changeMode('form')">
              {{ $t('表单模式') }}
            </bk-button>
            <bk-button
              :class="currentTriggerConfig.config.mode === 'json' ? 'is-selected' : ''"
              @click="changeMode('json')">
              {{ $t('json模式') }}
            </bk-button>
          </div>
          <div
            v-if="currentTriggerConfig.config.mode === 'form'"
            class="form-wrapper">
            <TaskParamEdit
              ref="taskParamEdit"
              :template-id="templateId"
              :editable="true"
              :constants="constants"
              :trigger-config="currentTriggerConfig"
              :saved-request-constants="copyTriggerConstants"
              :is-trigger-config="true"
              @change="onChangeRenderForm" />
          </div>
          <div
            v-else
            class="code-wrapper">
            <FullCodeEditor
              ref="fullCodeEditor"
              v-model="currentConstantToJson"
              :options="{ language: 'json', placeholder: { '${key}': 'value' } }" />
            <p
              v-if="!isJsonConstantsValid"
              v-bk-tooltips.top="$t('请求参数格式不正确，应为JSON格式')"
              class="valid-error-tips bk-icon icon-exclamation-circle-shape" />
          </div>
        </bk-form-item>
      </bk-form>
    </bk-dialog>
  </div>
</template>

<script>
import { mapState } from 'vuex';
import CronRuleSelect from './CronRuleSelect';
import FullCodeEditor from '@/components/common/FullCodeEditor.vue';
import TaskParamEdit from '../../TemplateMock/MockExecute/components/TaskParamEdit.vue';
import i18n from '@/config/i18n/index.js';
import tools from '@/utils/tools.js';
import Translate from '@/utils/cron.js';
export default {
    name: 'TimedTriggerConfig',
    components: {
      CronRuleSelect,
      FullCodeEditor,
      TaskParamEdit,
    },
    props: {
      isViewMode: {
        type: Boolean,
        default: false,
      },
      templateId: {
        type: [String, Number],
        default: '',
      },
      triggers: {
        type: Array,
        default() {
          return [];
        },
      },
      isAllowSetMultipleTrigger: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
          triggerData: tools.deepClone(this.triggers),
          triggerFields: [
            {
              key: 'name',
              name: i18n.t('触发器'),
            },
            {
              key: 'is_enabled',
              name: i18n.t('启用状态'),
            },
            {
              key: 'cron',
              name: i18n.t('执行周期'),
            },
          ],
          triggerTypeSelect: '',
          isShowTriggerDialog: false,
          currentTriggerConfig: {
            config: {
              mode: 'form',
              constants: {},
              cron: {
                minute: '*/30',
                hour: '*',
                day_of_week: '*',
                day_of_month: '*',
                month_of_year: '*',
              },
            },
          },
          type: '',
         isNewTrigger: false,
         currentJoinIcon: '',
         currentConstantToJson: '',
         currentTriggerIndex: null,
         isAdd: false,
         copyTrigger: {},
         copyTriggerConstants: {},
         copyTriggerCron: {},
         savedChangeRenderConstants: {},
         initTrigger: {
              id: null,
              config: {
                  mode: 'form',
                  constants: {},
                  cron: {
                    minute: '*/30',
                    hour: '*',
                    day_of_week: '*',
                    day_of_month: '*',
                    month_of_year: '*',
                  },
              },
              is_deleted: false,
              space_id: '',
              template_id: this.templateId,
              is_enabled: true,
              name: '定时触发',
              type: 'periodic',
         },
         saveInitialBackfillData: {},
        };
    },
    computed: {
        ...mapState('template', {
        spaceId: state => state.spaceId,
        constants: state => state.constants,
        }),
        isJsonConstantsValid() {
          return this.currentTriggerConfig.config.mode === 'json' ? tools.checkIsJSON(this.currentConstantToJson) : true;
        },
        filteredTriggerData() {
          if (this.isAdd) {
            return this.triggerData.slice(0, -1);
          }
          return this.triggerData;
        },
    },
    watch: {
        currentJoinIcon(val) {
          if (this.currentTriggerIndex < this.triggerData.length) {
             const cronArray = val.split(' ');
             const jsonCron = {
                  minute: cronArray[0],
                  hour: cronArray[1],
                  day_of_month: cronArray[2],
                  month_of_year: cronArray[3],
                  day_of_week: cronArray[4],
              };
            this.$set(this.triggerData[this.currentTriggerIndex].config, 'cron', jsonCron);
          }
        },
    },
    methods: {
       joinCron(cron) {
          const afterCron = [
            cron.minute,
            cron.hour,
            cron.day_of_month,
            cron.month_of_year,
            cron.day_of_week].join(' ');
          return afterCron;
      },
      translateCron(value) {
        const orderedValues = Translate(this.joinCron(value));
        let afterTime = '';
        orderedValues.forEach((item, index) => {
          if (index !== 2) {
            afterTime += `${item} `;
          } else {
            if (orderedValues[2]) {
              afterTime += `以及当月 ${item} `;
            } else {
              afterTime += `${item} `;
            }
          }
        });
        return afterTime;
      },
       handelIsEnabledChange() {
          this.$emit('change', this.triggerData);
       },
       delItemTigger(row, index) {
          this.triggerData.splice(index, 1);
          this.$emit('change', this.triggerData);
        },
        changeMode(mode) {
          this.mode = mode;
          this.$set(this.currentTriggerConfig.config, 'mode', mode);
          this.triggerData[this.currentTriggerIndex].config.mode = mode;
          if (this.mode === 'form') {
              this.$set(this.currentTriggerConfig.config, 'constant', null);
          this.triggerData[this.currentTriggerIndex].config.constants = null;
          }
        },
        editTriggerConfig(row, index) {
          this.currentTriggerIndex = index;
          this.type = 'edit';
          this.currentTriggerConfig = row;
          this.currentJoinIcon  = this.joinCron(row.config.cron);
          if (row.config.mode === 'json') {
            this.currentConstantToJson = JSON.stringify(row.config.constants, null, 2);
          } else {
            this.currentConstantToJson = '';
          }
          this.coppyTrigger = row;
          this.copyTriggerConstants = row.config.constants;
          this.copyTriggerCron = row.config.cron;
          this.isShowTriggerDialog = true;
        },
        addTrigger() {
          this.isAdd = true;
          this.type = 'add';
          this.initTrigger.space_id = this.spaceId;
          this.currentTriggerConfig = {
            ...tools.deepClone(this.initTrigger),
            isNewTrigger: true,
          };
          this.copyTriggerConstants = {};
          this.copyTriggerCron = {
              minute: '*/30',
              hour: '*',
              day_of_week: '*',
              day_of_month: '*',
              month_of_year: '*',
          },
          this.coppyTrigger = tools.deepClone(this.currentTriggerConfig);
          this.currentJoinIcon  = this.joinCron(this.currentTriggerConfig.config.cron);
          this.isShowTriggerDialog = true;
          this.currentConstantToJson = '';
          this.triggerData.push(this.currentTriggerConfig);
          this.currentTriggerIndex = this.triggerData.length - 1;
        },
        onTriggerCancel() {
          if (this.type === 'add') {
            this.triggerData.splice(this.triggerData.length - 1, 1);
            this.isAdd = false;
          }
          if (Object.values(this.triggerData).length > 0) {
              if (this.currentTriggerConfig.config.mode === 'form') {
                //  this.$set(this.triggerData[this.currentTriggerIndex].config, 'constants', this.currentTriggerConfig.config.constants);
                this.currentTriggerConfig.config.constants = this.copyTriggerConstants;
                 this.triggerData[this.currentTriggerIndex].config.constants = this.copyTriggerConstants;
              }
              // this.$set(this.triggerData[this.currentTriggerIndex].config, 'cron', this.currentTriggerConfig.config.cron);
              this.triggerData[this.currentTriggerIndex].config.cron = this.currentTriggerConfig.config.cron;
          }
          this.initTrigger.space_id = this.spaceId;
          this.currentTriggerConfig = tools.deepClone(this.initTrigger);
          this.copyTriggerConstants = {};
          this.isShowTriggerDialog = false;
        },
        onTriggerConfirm(type) {
          const isCronError = this.$refs.cronRuleSelect.isError;
          const isParamsValid = this.currentTriggerConfig.config.mode === 'json' ? this.isJsonConstantsValid : this.$refs.taskParamEdit.validate();
          if (!isParamsValid || isCronError) {
            return;
          }
          if (type === 'add') {
            this.isAdd = false;
          }
          if (this.currentTriggerConfig.config.mode === 'json') {
             this.$set(this.triggerData[this.currentTriggerIndex].config, 'constants', JSON.parse(this.currentConstantToJson));
          } else {
            this.$set(this.triggerData[this.currentTriggerIndex].config, 'constants', tools.deepClone(this.savedChangeRenderConstants));
          }
          this.initTrigger.space_id = this.spaceId;
          this.isShowTriggerDialog = false;
          this.$emit('change', this.triggerData);
          this.currentTriggerConfig = tools.deepClone(this.initTrigger);
        },
        onChangeRenderForm(constants, saveInitialBackfillData) {
          this.saveInitialBackfillData = saveInitialBackfillData;
          this.savedChangeRenderConstants = constants;
        },
    },

};
</script>

<style lang="scss" scoped>
  .timed-trigger-wrapper{
    margin-left: 140px;
  }
  .trigger-operation-button{
    margin-left: 16px;
  }
  .add-trigger-button{
    margin: 12px 0;
  }
  .loop-rule {
    padding: 16px 20px;
  }
  .trigger-type-select{
    width: 150px;
    margin-bottom: 15px;
  }
  .dialog-top-text{
    // font-size: 14px;
    // color: #63656e;
    margin-bottom: 8px;
  }
  ::v-deep .bk-dialog-header{
    padding:3px 24px 16px;
  }
  ::v-deep .bk-table-row{
    .cell{
       display: flex;
      }
    .add-new-trigger{
       margin-left: 4px;
       background: #E4FAF0;
       border-radius: 2px;
       color: #14A568;
       font-size: 10px;
       line-height: 16px;
       padding: 2px 3px;
     }
  }
    .bk-form-item {
      .form-wrapper {
        padding: 12px;
        background: #F0F1F5;
        border-radius: 2px;
      }
      .code-wrapper {
        height: 300px;
      }
      .valid-error-tips {
        position: absolute;
        top: 12px;
        right: 0;
        color: #ea3636;
        cursor: pointer;
        font-size: 16px;
      }
      &:not(:first-child) {
        margin-top: 28px;
      }
    }
    .bk-button-group{
      margin-bottom: 8px;
    }
    ::v-deep .bk-form{
      .bk-label{
        height: 20px;
        font-size: 12px;
        text-align: right;
        line-height: 20px;
        padding-right: 22px;
      }
    }
    ::v-deep .bk-dialog-body{
      max-height: 500px;
      overflow-y: scroll;
    }
</style>
