<template>
  <bk-sideslider
    :is-show.sync="sideShow"
    :width="960"
    :quick-close="true"
    :show-mask="true"
    class="decision-view-slider"
    :before-close="() => {
      $emit('close')
    }">
    <div
      slot="header"
      class="header-wrap">
      <span class="title">{{ $t('决策表详情') }}</span>
      <span
        v-bk-overflow-tips
        class="name ellipsis">{{ row.name }}</span>
      <template v-if="hasEditPermission">
        <bk-button
          theme="primary"
          @click="handleEdit">
          {{ $t('编辑') }}
        </bk-button>
        <decision-delete
          :data="row"
          :is-admin-path="path === 'admin_decision'"
          @onDeleted="$emit('onDeleted')" />
      </template>
    </div>
    <div
      slot="content"
      class="content-wrap">
      <div class="basic-wrap">
        <div class="title-tag">
          {{ $t('基础信息') }}
        </div>
        <p>
          <span class="label">{{ $t('名称：') }}</span>
          <span
            v-bk-overflow-tips
            class="content ellipsis">{{ row.name }}</span>
        </p>
        <p>
          <span class="label">{{ $t('描述：') }}</span>
          <span
            v-bk-overflow-tips
            class="content ellipsis">{{ row.desc || '--' }}</span>
        </p>
        <p v-if="path === 'admin_decision'">
          <span class="label">{{ $t('关联流程：') }}</span>
          <router-link
            v-if="row.template_id"
            class="template-name"
            target="_blank"
            :to="{
              name: 'templatePanel',
              params: {
                templateId: row.template_id,
                type: 'view'
              }
            }">
            {{ `[${row.template_id}] ${templateData.name || ''}` }}
          </router-link>
          <span v-else>{{ '--' }}</span>
        </p>
      </div>
      <div class="ruler-wrap">
        <div class="title-tag">
          {{ $t('规则配置') }}
        </div>
        <DecisionTable
          ref="decisionTable"
          :data="row.data"
          :readonly="true"
          :slider-width="800" />
      </div>
    </div>
  </bk-sideslider>
</template>

<script>
  import DecisionTable from '@/components/DecisionTable/index.vue';
  import DecisionDelete from './DecisionDelete.vue';
  import { mapActions } from 'vuex';
  export default {
    name: '',
    components: {
      DecisionTable,
      DecisionDelete,
    },
    props: {
      isShow: {
        type: Boolean,
        default: false,
      },
      row: {
        type: Object,
        default: () => ({}),
        required: true,
      },
      spaceId: {
        type: [String, Number],
        default: '',
      },
      path: {
        type: String,
        default: 'decision',
      },
    },
    data() {
      return {
        sideShow: false,
        templateData: {},
      };
    },
    computed: {
      hasEditPermission() {
        const { auth = [] } = this.templateData;
        return auth.some(action => ['EDIT', 'MOCK'].includes(action));
      },
    },
    watch: {
      isShow: {
        handler(val) {
          // 添加延迟触发sideSlider遮罩
          this.$nextTick(() => {
            this.sideShow = !!val;
          });
        },
        immediate: true,
      },
      sideShow(val) {
        if (val && this.row.template_id) {
          this.getTemplateData();
        }
      },
    },
    methods: {
      ...mapActions('template/', [
        'loadTemplateData',
      ]),
      async getTemplateData() {
        try {
          this.templateData = await this.loadTemplateData({
            templateId: this.row.template_id,
          });
        } catch (error) {
          console.warn(error);
        }
      },
      handleEdit() {
        if (this.path === 'decision') {
          const { href } = this.$router.resolve({
            name: 'decisionEdit',
            params: { decisionId: this.row.id, path: 'decision', from: 'decisionTable'},
            query: { space_id: this.spaceId, template_id: this.row.template_id },
          });
          window.open(href, '_blank');
        } else {
          this.$router.push({
            name: 'decisionEdit',
            params: { decisionId: this.row.id, path: 'admin_decision', from: 'decisionTable'},
            query: { space_id: this.spaceId },
          });
        }
      },
    },
  };
</script>

<style lang="scss" scoped>
  .decision-view-slider {
    .header-wrap {
      display: flex;
      align-items: center;
      padding-right: 40px;
      height: 100%;
      line-height: 24px;
      .title {
        position: relative;
        flex-shrink: 0;
        margin-right: 17px;
        font-size: 16px;
        color: #313238;
        &::after {
          content: '';
          position: absolute;
          right: -9px;
          top: 5px;
          width: 1px;
          height: 14px;
          background: #dcdee5;
        }
      }
      .name {
        flex: 1;
        font-size: 14px;
        color: #63656e;
      }
      .bk-primary {
        margin: 0 8px 0 24px;
      }
    }
    .content-wrap {
      padding: 22px 40px;
      .title-tag {
        height: 24px;
        padding: 1px 0 0 8px;
        margin-bottom: 18px;
        line-height: 22px;
        font-weight: Bold;
        font-size: 14px;
        color: #313238;
        background: #f0f1f5;
        border-radius: 2px;
      }
      .basic-wrap {
        margin-bottom: 24px;
        p {
          display: flex;
          padding: 0 24px;
          line-height: 32px;
          font-size: 12px;
          color: #313238;
          .label {
            width: 60px;
            flex-shrink: 0;
            margin-right: 4px;
            text-align: right;
            color: #63656e;
          }
        }
        .template-name {
          color: #3a84ff;
        }
      }
    }
    .ellipsis {
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
  }
</style>
<style lang="scss">
  .operate-menu-popover {
    z-index: 2500 !important;
  }
</style>
