<template>
  <div class="job-and-stage-edit-sld">
    <bk-sideslider
      :is-show.sync="isShowSync"
      :show-mask="false"
      :title="sldTitle"
      :quick-close="true"
      width="640"
      @hidden="cancel">
      <div
        slot="content"
        class="job-and-stage-edit-content">
        <bk-alert
          type="info"
          title="一至多个 Job 组成一个 Stage，Stage 间顺序执行。"
          style="margin-bottom: 16px;"
          closable />
        <bk-form
          ref="configForm"
          form-type="vertical"
          :rules="rules">
          <bk-form-item
            :label="`${tempData.type}名称`"
            property="name">
            <bk-input
              v-model="tempData.name" />
          </bk-form-item>
          <bk-form-item
            label="数据呈现"
            property="config">
            <div class="tool-header">
              <bk-button
                theme="primary"
                size="small"
                @click="addConfig">
                <i
                  class="commonicon-icon common-icon-add"
                  style="font-size: 16px;margin-right: 4px;" />新增数据
              </bk-button>

              <bk-button
                theme="primary"
                text
                @click="toggleAllFold(!isFold)">
                <i
                  style="font-size: 12px;margin-right: 8px;"
                  size="small"
                  class="commonicon-icon common-icon-thumbnail-view" />{{ isFold?'一键展开':'一键折叠' }}
              </bk-button>
            </div>
            <div
              ref="sortableContainer"
              class="sortable-container">
              <data-config
                v-for="(item,index) in tempData.config"
                ref="configItemRefs"
                :key="item.id"
                :config.sync="item"
                :is-fold="item.isFold"
                @deleteConfig="deleteConfig(index)" />
            </div>
          </bk-form-item>
        </bk-form>
      </div>
      <div slot="footer">
        <bk-button
          style="margin-left: 24px;"
          theme="primary"
          @click="confirm(true)">
          确定
        </bk-button>
        <bk-button
          style="margin-left: 4px;"
          theme="default"
          @click="cancel(false)">
          取消
        </bk-button>
      </div>
    </bk-sideslider>
  </div>
</template>

<script>
import cloneDeepWith from 'lodash/cloneDeepWith';
import dataConfig from './components/dataConfig.vue';
import Sortable  from 'sortablejs';
export default {
    name: 'JobAndStageEditSld',
    components: {
      dataConfig,
    },
    props: {
        isShow: {
            type: Boolean,
            default: false,
        },
        initData: {
            type: Object,
            default: null,
        },
    },
    data() {
        return {
            tempData: {
                id: 1,
                name: '',
                config: [
                  {
                    key: '已合入',
                    value: '0',
                    renders: [
                      {
                        type: 'link',
                        url: 'https://www.baidu.com',
                      },
                    ],
                  },
                ],
            },
            isFold: false,
            rules: {
              name: [{
                  trigger: 'blur',
                  message: 'stage名称不能为空',
                  validator: () => !!this.tempData.name,
              }],
            },
            sortableInstance: null,
        };
    },
    computed: {
        sldTitle() {
            return '编辑';
        },
        isShowSync: {
            get() {
                console.log('index.vue_Line:49', this);
                return this.isShow;
            },
            set(value) {
                this.$emit('update:isShow', value);
            },
        },

    },
    watch: {
        isShowSync: {
            handler(value) {
              this.isFold = false;
                if (value && this.initData) {
                    this.tempData = cloneDeepWith(this.initData);
                    this.tempData.config.forEach((config) => {
                      this.$set(config, 'isFold', false);
                    });
                    this.$nextTick(() => {
                      this.initSortable();
                    });
                }
            },
        },
    },
    mounted() {
        console.log('index.vue_Line:156', Sortable);
    },
    methods: {
        async confirm() {
          try {
            await this.validate();
            // 验证数据项填入是否合法
            await Promise.all(this.$refs.configItemRefs.map(item => item.validate()));

            Object.assign(this.initData, this.tempData);
            this.cancel();
          } catch (error) {
            console.log('index.vue_Line:164', error);
          }
        },
        cancel() {
            this.$emit('cancel');
            this.isShowSync = false;
        },
        addConfig() {
          this.tempData.config.unshift({
            id: new Date().getTime(),
            key: '',
            value: '',
            renders: [],
            isFold: this.isFold,
          });
        },
        async validate() {
          return await this.$refs.configForm.validate();
        },
        toggleAllFold(value) {
          this.isFold = value;
          this.tempData.config.forEach((config) => {
            this.$set(config, 'isFold', this.isFold);
          });
          this.sortableInstance.option('disabled', !this.isFold);
        },
        deleteConfig(index) {
          this.tempData.config.splice(index, 1);
        },
        initSortable() {
          this.sortableInstance = new Sortable(this.$refs.sortableContainer, {
              animation: 150,
              disabled: true,
              handle: '.moveIcon',
              onEnd: (evt) => {
                const currentDraggerItem = this.tempData.config.splice(evt.oldIndex, 1);
                this.tempData.config.splice(evt.newIndex, 0, ...currentDraggerItem);
                this.$forceUpdate();
              },
            });
        },
    },
};
</script>

<style lang="scss" scoped>
.job-and-stage-edit-sld {
    :deep(.bk-sideslider-content){
        height: calc(-114px + 100vh);
    }
    .job-and-stage-edit-content{
        padding: 16px;
        height: 100%;
        overflow: auto;
      .tool-header{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 0 16px;
      }
    }
}
</style>
