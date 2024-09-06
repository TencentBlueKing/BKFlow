<template>
  <div class="select-field">
    <!-- <bk-select v-model="optionInfo.type" :disabled="readonly">
      <bk-option id="custom" name="自定义"></bk-option>
      <bk-option id="dictionary" name="数据源"></bk-option>
    </bk-select> -->
    <!--自定义-->
    <template v-if="optionInfo.type === 'custom'">
      <vue-draggable
        :value="customOptions"
        handle=".option-handle"
        :force-fallback="true"
        drag-class="option-drag"
        :sort="false"
        :options="{ disabled: readonly }"
        @start="dragRowStart"
        @end="dragRowEnd">
        <div
          v-for="(option, index) in customOptions"
          :key="index"
          class="option-item"
          @mouseover="dropRowIndex = index">
          <i class="option-handle common-icon-drawable" />
          <bk-popover
            ref="optionPopover"
            class="option-popover"
            placement="top"
            width="320"
            theme="light"
            trigger="click"
            :disabled="readonly"
            :on-hide="handleOptionMenuClose">
            <div
              :class="['option-content', { 'is-incomplete': option.incomplete, 'is-disabled': readonly }]"
              @click.stop>
              <span
                v-bk-overflow-tips
                class="option-name"
                @click="handleOptionClick(option, index)">
                {{ option.name || '--' }}
              </span>
              <i
                v-if="!readonly"
                class="bk-icon icon-edit-line"
                @click="handleOptionEdit(option, index)" />
            </div>
            <!--选项编辑面板-->
            <div
              slot="content"
              class="option-menu-list">
              <bk-form
                ref="optionForm"
                :model="optionFormData"
                form-type="vertical">
                <bk-form-item
                  :label="$t('选项名称')"
                  :required="true"
                  :property="'name'"
                  :rules="rules.required">
                  <bk-input
                    v-model="optionFormData.name"
                    :maxlength="16"
                    :show-word-limit="true" />
                </bk-form-item>
                <bk-form-item
                  :label="$t('选项值')"
                  :required="true"
                  :property="'id'"
                  :rules="rules.required">
                  <bk-input
                    ref="idInput"
                    v-model="optionFormData.id" />
                </bk-form-item>
              </bk-form>
            </div>
          </bk-popover>
          <i
            v-if="!readonly"
            class="bk-icon icon-delete"
            @click="handleDeleteOption(option, index)" />
        </div>
      </vue-draggable>
      <bk-button
        v-if="!readonly"
        text
        title="primary"
        @click="handleAddOption">
        <i class="bk-icon icon-plus-circle" />
        {{ $t('添加选项') }}
      </bk-button>
    </template>
    <!--字典-->
    <bk-select
      v-else
      v-model="optionInfo.value"
      class="mt20"
      searchable
      :disabled="readonly">
      <bk-options
        v-for="option in dictionaryOptions"
        :id="option.id"
        :key="option.id"
        :name="option.name" />
    </bk-select>
  </div>
</template>

<script>
  import VueDraggable from 'vuedraggable';
  import tools from '@/utils/tools.js';
  export default {
    name: 'SelectField',
    components: {
      VueDraggable,
    },
    props: {
      options: {
        type: Object,
        default: () => ({}),
      },
      readonly: {
        type: Boolean,
        default: true,
      },
      operate: {
        type: String,
        default: '',
      },
    },
    data() {
      const options = tools.deepClone(this.options);
      return {
        optionInfo: options,
        customOptions: [...options.items],
        dictionaryOptions: [],
        dragRowIndex: -1,
        dropRowIndex: -1,
        optionFormData: {},
        rules: {
          required: [
            {
              required: true,
              message: this.$t('必填项'),
              trigger: 'blur',
            },
          ],
        },
      };
    },
    watch: {
      optionInfo: {
        handler(val) {
          const items = this.optionInfo.type === 'custom' ? this.customOptions : this.dictionaryOptions;
          this.$emit('updateOptions', { ...val, items });
        },
        deep: true,
      },
      customOptions: {
        handler(val) {
          // 过滤多余字段
          const items = tools.deepClone(val).map((item) => {
            delete item.new;
            return item;
          });
          this.$emit('updateOptions', { ...this.optionInfo, items });
        },
        deep: true,
      },
    },
    methods: {
      // 添加选项
      handleAddOption() {
        const name = this.getDefaultName();
        this.customOptions.push({
          id: '',
          name,
          new: true, // 标记新增选项
        });
        // 自动打开气泡并获焦
        this.$nextTick(() => {
          const index = this.customOptions.length - 1;
          this.optionFormData = { id: '', name, index  };
          this.handlePopoverShow(index);
          this.$nextTick(() => {
            this.$refs.idInput[index].focus();
          });
        });
      },
      // 默认名称
      getDefaultName() {
        const defaultName = this.$t('选项');
        const regex = new RegExp(`^${defaultName}[0-9]*$`);
        const defaultNameList = this.customOptions.reduce((acc, cur) => {
          if (regex.test(cur.name)) {
            acc.push(cur.name);
          }
          return acc;
        }, []);
        let name = defaultName + 1;
        if (defaultNameList.length) {
          const index = defaultNameList.map(item => (Number(item.split(defaultName)[1])));
          const maxIndex = Math.max(...index) + 1;
          name = defaultName + maxIndex;
        }
        return name;
      },
      // 删除
      handleDeleteOption(option, index) {
        // 编辑模式下-删除非新增选项时需二次确认
        if (this.operate === 'edit' && !option.new) {
          this.$bkInfo({
            title: this.$t('风险提示'),
            subTitle: this.$t('修改或删除选项可能导致现有规则不适配，请谨慎操作'),
            maskClose: false,
            width: 450,
            confirmFn: () => {
              this.customOptions.splice(index, 1);
            },
          });
          return;
        }
        this.customOptions.splice(index, 1);
      },
      // 行开始拖拽
      dragRowStart(e) {
        this.dragRowIndex = e.oldIndex;
      },
      // 行结束拖拽
      dragRowEnd() {
        const start = this.dragRowIndex;
        const end = this.dropRowIndex;
        if (end !== -1 && start !== end) {
          const rowData = this.customOptions[start];
          this.customOptions.splice(end, 0, rowData);
          const deleteIndex = start < end ? start : start + 1;
          this.customOptions.splice(deleteIndex, 1);
        }
        this.dragRowIndex = -1;
        this.dropRowIndex = -1;
      },
      // 选项点击
      handleOptionClick(option, index) {
        // 只读、非新增选项、当前选项编辑popover已打开则禁止打开编辑popover
        if (this.readonly || !option.new || this.optionFormData.index === index) return;
        this.optionFormData = { ...option, index };
        this.handlePopoverShow(index);
      },
      // 编辑选项
      handleOptionEdit(option, index) {
        // 当前选项编辑popover已打开则禁止再次打开编辑popover
        if (this.optionFormData.index === index) return;
        this.optionFormData = { ...option, index };
        // 编辑模式下-编辑非新增选项时需二次确认
        if (this.operate === 'edit' && !option.new) {
          this.$bkInfo({
            title: this.$t('风险提示'),
            subTitle: this.$t('修改或删除选项可能导致现有规则不适配，请谨慎操作'),
            maskClose: false,
            width: 450,
            confirmFn: () => {
              this.handlePopoverShow(index);
            },
            cancelFn: () => {
              this.handleOptionMenuClose();
            },
          });
          return;
        }
        this.handlePopoverShow(index);
      },
      // 选项面板关闭
      handleOptionMenuClose() {
        const { name, id, index } = this.optionFormData;
        const optionInfo = this.customOptions[index];
        if (optionInfo) {
          optionInfo.name = name;
          optionInfo.id = id;
          optionInfo.incomplete = !name || !id;
        }
        this.optionFormData = {};
      },
      handlePopoverShow(index) {
        this.$refs.optionPopover[index].showHandler();
      },
    },
  };
</script>

<style lang="scss" scoped>
  .select-field {
    .option-item {
      display: flex;
      align-items: center;
      height: 32px;
      font-size: 14px;
      margin-bottom: 8px;
      cursor: pointer;
      .common-icon-drawable {
        margin-right: 8px;
        cursor: move;
      }
      /deep/.option-popover {
        flex: 1;
        min-width: 0;
        .bk-tooltip-ref {
          width: 100%;
        }
      }
      .option-content {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 8px;
        color: #63656e;
        background: #f4f5f8;
        border: 1px solid transparent;
        border-radius: 4px;
        &:hover {
          background: #edeff3;
        }
        &.is-incomplete{
          border-color: #ea3636;
        }
        &.is-disabled {
          cursor: not-allowed;
        }
      }
      .option-name {
        width: calc(100% - 22px);
        font-size: 12px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .icon-edit-line,
      .icon-delete {
        margin-left: 8px;
        &:hover {
          color: #3a84ff;
        }
      }
      &:first-child {
        margin-top: 14px;
      }
      &:last-child {
        margin-bottom: 10px;
      }
    }
    .icon-plus-circle {
      transform: translateY(-2px);
    }
    .option-drag {
      background: #e5f4ff !important;
      border:  1px solid #e6e9ee;
      border-bottom: none;
      .row-handle {
        display: block !important;
      }
    }
  }
  .option-menu-list {
    padding: 12px 8px;
  }
</style>
