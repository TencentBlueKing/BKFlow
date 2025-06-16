<template>
  <div class="data-config">
    <div class="data-info">
      <div class="data-name">
        <span class="name"><span
          v-if="isFold&&editable"
          class="moveIcon commonicon-icon common-icon-drawable" />{{ config.key || '数据名称' }}</span>
        <span
          class="tool-btn"
          @click="deleteConfig">
          <template v-if="editable">
            <i class="icon-btn commonicon-icon common-icon-ashcan-delete" />
          </template>

        </span>
      </div>

      <bk-form
        v-show="!isFold"
        ref="configForm"
        :model="configSync"
        :rules="rules">
        <div class="form-content">
          <bk-form-item
            label="名称"
            property="key">
            <bk-input
              v-model="configSync.key"
              :disabled="!editable" />
          </bk-form-item>
          <bk-form-item
            label="取值"
            property="value">
            <bk-input
              v-model="configSync.value"
              :disabled="!editable"
              @focus="toggleShowSuggest(true)"
              @blur="toggleShowSuggest(false)" />
            <div
              v-show="ifShowSuggest&&configSync.value&&valueInputSuggestList.length"
              class="input-suggest">
              <div class="input-suggest-container">
                <div
                  v-for="item in valueInputSuggestList"
                  :key="item.key"
                  class="suggest-item"
                  @mousedown="handleSuggest(item.key)">
                  {{ item.key }}
                </div>
              </div>
            </div>
          </bk-form-item>
        </div>
        <div class="render-list">
          <bk-form-item property="renders">
            <RenderItem
              v-for="(item,index) in config.renders"
              ref="renderItemRefs"
              :key="item.type+index"
              :index="index"
              :render-data.sync="item"
              :render-list="config.renders"
              :editable="editable"
              @delete="deleteRender(index)" />
          </bk-form-item>
        </div>
      </bk-form>
    </div>

    <div
      v-show="!isFold"
      class="add-render">
      <bk-button
        size="small"
        :disabled="config.renders.length>=2 || !editable"
        @click="addRender">
        <i
          style="font-size: 16px;"
          class="commonicon-icon common-icon-add" /> 添加样式
      </bk-button>
    </div>
  </div>
</template>

<script>
import { cloneDeepWith } from 'lodash';
import { getIsDisabledSelecitonByRenderList, renderTypeMap } from '../../../utils';
import RenderItem from './renderItem/renderItem.vue';
import { mapState } from 'vuex';
import { ref } from 'vue';
export default {
    name: 'DataConfig',
    components: {
      RenderItem,
    },
    props: {
      config: {
        type: Object,
        required: true,
      },
      isFold: {
        type: Boolean,
        default: false,
      },
      editable: {
          type: Boolean,
          default: false,
      },
    },
    data() {
        return {
          rules: {
            key: [{
                    trigger: 'blur',
                    message: '数据名称不能为空',
                    validator: () => !!this.configSync.key,
              }],
            value: [{
                  trigger: 'blur',
                  message: '取值不能为空',
                  validator: () => !!this.configSync.value?.toString(),
            }],
          },
          ifShowSuggest: false,
        };
    },
    computed: {
      ...mapState({
        constants: state => state.template.constants,
      }),
      configSync: {
        get() {
          return this.config;
        },
        set(value) {
          this.$emit('update:conifg', value);
        },
      },
      valueInputSuggestList() {
        return Object.values(this.constants).filter(item => item.key.includes(this.configSync.value));
      },
    },
    methods: {
      addRender() {
        // 根据目前已选类型选择一个可以选的补充上去
        const ableSelectRenderTypeItem = Object.values(renderTypeMap).find(item => !getIsDisabledSelecitonByRenderList(item.onlySign, this.configSync.renders));
        const currentRender = {
          type: ableSelectRenderTypeItem.value,
        };
        Object.assign(currentRender, cloneDeepWith(ableSelectRenderTypeItem.initData));
        this.configSync.renders.push(ref(currentRender).value);
      },
      deleteConfig() {
        this.$emit('deleteConfig');
      },
      deleteRender(index) {
        this.configSync.renders.splice(index, 1);
      },
      async validate() {
        this.$refs.renderItemRefs && await  Promise.all(this.$refs.renderItemRefs.map(item => item.validate()));
        await this.$refs.configForm.validate();
      },
      toggleShowSuggest(value) {
        this.$nextTick(() => {
          this.ifShowSuggest = value;
        });
      },
      handleSuggest(value) {
        this.configSync.value = value;
      },
    },
};
</script>

<style lang="scss" scoped>
.data-config {
  margin-bottom: 16px;
  .data-info{
    background-color: #eff5ff;

    .data-name{
        padding: 18px;
        display: flex;
        justify-content: space-between;
        line-height: 1;
        .moveIcon{
          color: #4D4F56;
          font-size: 20px;
          cursor: move;
        }
        .name{
          font-weight: 700;
          font-size: 14px;
          color: #3A84FF;
        }
        .tool-btn{
          .icon-btn {
            font-size: 12px;
            cursor: pointer;
        }
      }
    }
    .form-content{
      display: flex;
      gap: 8px;
      padding: 0px 18px 18px;
      :deep(.bk-form-item ){
        margin-top: 0px;
        flex: 1;
      }
      .input-suggest{
        position: absolute;
        width: 100%;
        bottom: 0px;
        transform: translateY(100%);
        z-index: 100;
        background-color: #fff;
        .input-suggest-container{
          border: 1px solid #c4c6cc;
          border-top: none;
          border-radius: 0 0 2px 2px;
          color: #63656e;
          .suggest-item{
            line-height: 1;
            padding: 8px 16px;
            font-size: 12px;
            cursor: pointer;
            &:hover{
              background-color: #eaf3ff;
            }
          }
        }
      }
    }


  }

  .add-render{
    padding: 16px;
    background-color: #fafbfd;
  }
}
</style>
