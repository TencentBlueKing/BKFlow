<template>
  <div class="render-item">
    <div class="render-index">
      <span class="render-index-container">
        {{ `样式${index + 1}` }}
      </span>
      <span class="tool-btn">
        <i
          class="icon-btn commonicon-icon common-icon-ashcan-delete"
          @click="deleteRender" />
      </span>
    </div>

    <bk-form-item
      class="render-type"
      label="样式类型">
      <bk-select
        v-model="renderData.type"
        :clearable="false"
        @change="changeRangeType">
        <bk-option
          v-for="item in Object.values(typeSelectOption)"
          :id="item.value"
          :key="item.value"
          :name="item.label"
          :disabled="getIsDisabledSeleciton(item.onlySign)" />
      </bk-select>
    </bk-form-item>

    <template v-if="currentRenderTypeItem&&currentRenderTypeItem.render">
      <component
        :is="currentRenderTypeItem.render"
        ref="renderConfigRef"
        :render-data.sync="renderDataSync" />
    </template>
  </div>
</template>

<script>
import { cloneDeepWith } from 'lodash';
import { getIsDisabledSelecitonByRenderList, renderTypeMap } from '../../../../utils';

export default {
    name: 'RenderItem',
    props: {
        renderData: {
            type: Object,
            default: null,
        },
        index: {
            type: Number,
            default: 1,
        },
        renderList: {
            type: Array,
            default: () => [],
        },
    },
    data() {
        return {
            typeSelectOption: {
                ...renderTypeMap,
            },
        };
    },
    computed: {
        renderDataSync: {
            get() {
                return this.renderData;
            },
            set(value) {
                this.$emit('update:rendreData', value);
            },
        },
        currentRenderTypeItem() {
            if (this.renderData.type) {
                return this.typeSelectOption[this.renderData.type];
            }
                return null;
        },
        otherRenders() {
            return this.renderList.filter((item, renderIndex) => renderIndex !== this.index);
        },
    },
    methods: {
        deleteRender() {
            this.$emit('delete');
        },
        changeRangeType() {
            if (this.currentRenderTypeItem) {
                Object.assign(this.renderDataSync, cloneDeepWith(this.currentRenderTypeItem.initData));
            }
        },
        getIsDisabledSeleciton(onlySign) {
            return getIsDisabledSelecitonByRenderList(onlySign, this.otherRenders);
        },
        async validate() {
          return await this.$refs.renderConfigRef.validate();
        },
    },
};
</script>

<style lang="scss" scoped>
.render-item {
    padding: 16px;
    background-color: #fafbfd;
    border-bottom: 1px solid #DCDEE5;
    .render-index{
        display: flex;
        justify-content: space-between;
        margin-bottom: 8px;
        .render-index-container{
            font-weight: 700;
            font-size: 14px;
            color: #4D4F56;
        }
        .tool-btn{
            .icon-btn{
                font-size: 12px;
                cursor: pointer;
            }
        }

    }
    .render-type{
        margin-bottom: 16px;
    }
    :deep(.bk-select .bk-select-name){
        background-color: #fff;
    }
}
</style>
