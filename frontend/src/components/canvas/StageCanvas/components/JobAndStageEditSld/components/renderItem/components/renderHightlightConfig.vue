<template>
  <div class="render-hightlight-config">
    <bk-form
      ref="configForm"
      :model="renderDataSync"
      :rules="rules">
      <div
        v-for="(item,index) in renderDataSync.conditions"
        :key="index"
        class="highlight-rule">
        <bk-form-item
          class="condition-select"
          style="max-width: 80px;"
          :label="`条件${index + 1}`"
          :property="`condition${index}`">
          <bk-select
            v-model="item.condition"
            :disabled="!editable">
            <bk-option
              v-for="condition in
                conditionConfig"
              :id="condition.value"
              :key="condition.value"
              :name="condition.value" />
          </bk-select>
        </bk-form-item>
        <bk-form-item
          class="match-value-input"
          :label="`匹配值`"
          :property="`value${index}`"
          style="flex: 1;">
          <bk-input
            v-model="item.value"
            :disabled="!editable" />
        </bk-form-item>
        <bk-form-item
          class="font-style-input"
          style="min-width: 280px;"
          :label="`字体样式`">
          <div class="font-style-input-container">
            <bk-color-picker
              v-model="item.color"
              class="color-picker"
              :show-value="false"
              :disabled="!editable"
              @change="(value)=>changeColor(value,item)" />
            <bk-radio-group
              v-model="item.fontStyle"
              class="font-style-tab">
              <bk-radio-button
                v-for="fontStyle in Object.values(fontStyleMap)"
                :key="fontStyle.value"
                :value="fontStyle.value"
                :disabled="!editable">
                {{ fontStyle.label }}
              </bk-radio-button>
            </bk-radio-group>
          </div>
        </bk-form-item>
      </div>
      <div class="tooltips-input">
        <bk-form-item
          class="match-value-input"
          :label="`提示信息`"
          style="flex: 1;">
          <bk-input
            v-model="renderDataSync.tooltips"
            type="textarea"
            :disabled="!editable" />
        </bk-form-item>
      </div>
    </bk-form>
  </div>
</template>

<script>
import { fontStyleMap } from '../../../../../utils';
export default {
    name: 'RenderHightlightConfig',
    props: {
        renderData: {
            type: Object,
            required: true,
        },
        editable: {
          type: Boolean,
          default: false,
        },
    },
    data() {
        return {
            conditionConfig: [
                {
                    value: '>',
                },
                {
                    value: '>=',
                },
                {
                    value: '=',
                },
                {
                    value: '<=',
                },
                {
                    value: '<',
                },
            ],
            fontStyleMap: {
                ...fontStyleMap,
            },

        };
    },
    computed: {
        renderDataSync: {
            get() {
                return this.renderData;
            },
            set(value) {
                this.$emit('update:renderData', value);
            },
        },
        rules() {
          const tempRule = {};
          this.renderDataSync.conditions.forEach((item, index) => {
            tempRule[`condition${index}`] = [{
              trigger: 'blur',
              message: '请选择有效的条件',
              validator: () => !!this.renderDataSync.conditions[index].condition,
            }];
            tempRule[`value${index}`] = [{
              trigger: 'blur',
              message: '请输入有效的匹配值',
              validator: () => this.renderDataSync.conditions[index].value !== '' && !isNaN(this.renderDataSync.conditions[index].value),
            }];
          });
          return {
            ...tempRule,
                };
        },
    },
    created() {
        if (this.renderDataSync.conditions) {
            this.renderDataSync.conditions.forEach((conditionItem) => {
                if (!conditionItem.condition) {
                    this.$set(conditionItem, 'condition', this.conditionConfig[0].value);
                }
                if (!conditionItem.fontStyle) {
                    this.$set(conditionItem, 'fontStyle', fontStyleMap.normal.value);
                }
                if (!conditionItem.color) {
                    this.$set(conditionItem, 'color', '#000000');
                }
                if (!conditionItem.value) {
                    this.$set(conditionItem, 'value', 0);
                }
            });
        } else {
          this.$set(this.renderDataSync, 'conditions', [{
                condition: '>',
                value: 0,
                color: '#000000',
                fontStyle: 'normal',
          }]);
        }
        this.$set(this.renderDataSync.conditions[0], 'color', this.renderDataSync.conditions[0].color);
        if (this.renderDataSync.tooltips) {
          this.$set(this.renderDataSync, 'tooltips', '');
        }
    },
    methods: {
      async validate() {
            return await this.$refs.configForm.validate();
        },
        changeColor() {
          this.$forceUpdate();
        },
    },
};
</script>

<style lang="scss" scoped>
.render-hightlight-config{
    .highlight-rule{
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 16px;
        :deep(.bk-form-item ){
          margin-top: 0px;
          flex: 1;
        }
        .condition-select{
            max-width: 80px;
        }
        .match-value-input{
            flex: 1;
        }
        .font-style-input{
            min-width: 280px;
            .font-style-input-container{
                display: flex;
                align-items: center;
                .color-picker{
                    width: 60px;
                    margin-right: 8px;
                }
                .font-style-tab{
                    flex: 1;
                }
            }
        }
    }
    :deep(.bk-form-radio-button:first-child .bk-radio-button-text) {
      border-left: 1px solid currentColor;
    }
}
</style>
<style lang="scss">

</style>
