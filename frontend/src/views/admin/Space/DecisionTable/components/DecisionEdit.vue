<template>
  <div
    class="decision-edit"
    @click="handleClickOutside">
    <div class="header-wrap">
      <i
        v-if="isAdmin || isCurSpaceSuperuser"
        class="bk-icon icon-arrows-left back-icon"
        @click="handleCancel" />
      <span class="header-title">{{ decisionId ? $t('编辑决策表') : $t('新建决策表') }}</span>
    </div>
    <div class="content-wrap">
      <!--基础信息-->
      <div class="basic-wrap">
        <div class="title-tag">
          {{ $t('基础信息') }}
        </div>
        <bk-form
          ref="editDecisionForm"
          :label-width="isAdminPath ? 80 : 56"
          class="basic-form"
          :model="decisionData">
          <bk-form-item
            :label="$t('名称')"
            :required="true"
            :property="'name'"
            :rules="rules.required">
            <bk-input
              v-model="decisionData.name"
              :readonly="isPartiallyEdited"
              :maxlength="32"
              :show-word-limit="true" />
          </bk-form-item>
          <bk-form-item
            v-if="isAdminPath"
            :label="$t('关联流程')"
            :property="'template_id'"
            :required="true"
            :rules="rules.required">
            <template-select
              :key="decisionSelectRandomKey"
              v-model="decisionData.template_id"
              :space-id="spaceId"
              :readonly="isPartiallyEdited" />
          </bk-form-item>
          <bk-form-item
            :label="$t('描述')"
            :property="'desc'">
            <bk-input
              v-model="decisionData.desc"
              type="textarea"
              :readonly="isPartiallyEdited"
              :maxlength="256"
              :show-word-limit="true" />
          </bk-form-item>
        </bk-form>
      </div>
      <!--规则配置-->
      <div class="ruler-wrap">
        <div class="title-tag mb5">
          {{ $t('规则配置') }}
        </div>
        <p
          v-if="isPartiallyEdited"
          class="partially-edited-tips mb15">
          {{ $t('该决策表已被流程中的节点引用，仅支持修改规则，不支持修改字段(修改字段需要修改节点引用后重新保存流程)。') }}
        </p>
        <DecisionTable
          ref="decisionTable"
          :data="decisionData.data"
          :partially-edited="isPartiallyEdited"
          @updateData="updateDecisionData" />
      </div>
    </div>
    <div class="operate-wrap">
      <bk-button
        theme="primary"
        :loading="saveLoading"
        :disabled="debugLoading"
        @click="handleSave">
        {{ decisionId ? $t('保存') : $t('提交') }}
      </bk-button>
      <bk-button
        type="submit"
        :disabled="saveLoading || debugLoading"
        @click="handleCancel">
        {{ $t('取消') }}
      </bk-button>
      <bk-button
        theme="primary"
        outline
        :loading="debugLoading"
        :disabled="saveLoading"
        @click="handleDebug">
        {{ $t('调试') }}
      </bk-button>
    </div>
    <DebugDialog
      :is-show="isDebugDialogShow"
      :is-admin-pth="isAdminPath"
      :decision-id="decisionId"
      :space-id="spaceId"
      :template-id="templateId"
      :inputs="decisionData.data.inputs"
      @close="isDebugDialogShow = false" />
  </div>
</template>

<script>
  import DecisionTable from '@/components/DecisionTable/index.vue';
  import DebugDialog from './DebugDialog.vue';
  import TemplateSelect from './TemplateSelect.vue';
  import { mapState, mapActions } from 'vuex';
  import tools from '@/utils/tools.js';
  export default {
    name: 'DecisionEdit',
    components: {
      DecisionTable,
      DebugDialog,
      TemplateSelect,
    },
    props: {
      spaceId: {
        type: [String, Number],
        default: '',
      },
      path: {
        type: String,
        default: '',
      },
      decisionId: {
        type: [String, Number],
        default: '',
      },
      templateId: {
        type: [String, Number],
        default: '',
      },
    },
    data() {
      return {
        decisionData: {
          name: '',
          data: {
            inputs: [],
            outputs: [],
            records: [],
          },
          template_id: '',
          desc: '',
        },
        initData: {},
        rules: {
          required: [
            {
              required: true,
              message: this.$t('必填项'),
              trigger: 'blur',
            },
          ],
        },
        saveLoading: false,
        debugLoading: false,
        isDataChange: false,
        isDebugDialogShow: false,
        isPartiallyEdited: false, // 半编辑（决策表关联了流程并且被使用了）
        decisionSelectRandomKey: '',
      };
    },
    computed: {
      ...mapState({
        isAdmin: state => state.isAdmin,
        isIframe: state => state.isIframe,
        isCurSpaceSuperuser: state => state.isCurSpaceSuperuser,
        infoBasicConfig: state => state.infoBasicConfig,
      }),
      isAdminPath() {
        return this.path === 'admin_decision';
      },
    },
    watch: {
      decisionId: {
        handler(val) {
          if (val) {
            this.getDecisionDetail();
          }
          this.initData = tools.deepClone(this.decisionData);
        },
        immediate: true,
      },
    },
    methods: {
      ...mapActions('decisionTable/', [
        'getDecisionData',
        'updateDecision',
        'checkDecisionUsed',
      ]),
      // 决策表详情
      async getDecisionDetail() {
        try {
          const resp = await this.getDecisionData({
            id: this.decisionId,
            space_id: this.spaceId,
            template_id: this.templateId || undefined,
            isAdmin: this.path === 'admin_decision',
          });
          this.decisionData = resp.data;
          this.initData = tools.deepClone(this.decisionData);
          this.decisionSelectRandomKey = new Date().getTime();
          // 判断是否为半编辑
          this.judgePartiallyEdited();
        } catch (error) {
          console.warn(error);
        }
      },
      async judgePartiallyEdited() {
        const { template_id: templateId } = this.decisionData;
        // 如果绑定了模板
        if (!templateId) {
          this.isPartiallyEdited = false;
          return;
        }
        try {
          const resp = await this.checkDecisionUsed({
            id: this.decisionId,
            isAdmin: this.path === 'admin_decision',
            template_id: templateId,
            space_id: this.spaceId,
          });
          if (!resp.result) return;
          this.isPartiallyEdited = resp.data.has_used;
        } catch (error) {
          console.warn(error);
        }
      },
      updateDecisionData(data) {
        this.decisionData.data = data;
        this.$nextTick(() => {
          this.checkButtonPosition();
        });
      },
      // 监听按钮区域是否位于视图最下面
      checkButtonPosition() {
        const buttonDom = document.querySelector('.operate-wrap');
        const buttonRect = buttonDom.getBoundingClientRect();
        const isAtBottom = buttonRect.bottom >= window.innerHeight;

        if (isAtBottom) {
          buttonDom.classList.add('at-bottom');
        } else {
          buttonDom.classList.remove('at-bottom');
        }
      },
      handleClickOutside() {
        this.$refs.decisionTable.updateActiveCell();
      },
      validate() {
        return this.$refs.editDecisionForm.validate().then((valid) => {
          if (valid) {
            return this.$refs.decisionTable.validate();
          }
          return valid;
        });
      },
      // 保存/提交
      async handleSave() {
        const result = await this.validate();
        if (!result) return;
        try {
          this.saveLoading = !this.debugLoading;
          // 过滤掉整行为空的
          const { data } = this.decisionData;
          data.records = data.records.filter((item) => {
            const { conditions, type } = item.inputs;
            return type !== 'common'
              || ['is-null', 'not-null'].includes(conditions[0]?.compare)
              || conditions[0]?.right.obj.value;
          });
          if (!data.records.length) {
            this.$bkMessage({
              message: this.$t('请至少完整填写一条规则'),
              theme: 'error',
            });
            return;
          }
          const params = {
            id: this.decisionId,
            space_id: this.spaceId,
            isAdmin: this.isAdminPath,
            ...this.decisionData,
          };
          params.template_id = params.template_id || this.templateId || undefined;
          const resp = await this.updateDecision(params);
          if (!resp.result) return;

          this.initData = tools.deepClone(this.decisionData);
          // 新建后需更新路由
          if (!this.decisionId) {
            this.$router.replace({
              name: 'decisionEdit',
              params: {
                ...this.$route.params,
                decisionId: resp.data.id,
              },
              query: { ...this.$route.query },
            });
          }
          // 成功message
          const message = this.$t('{0}成功', [this.decisionId ? this.$t('编辑') : this.$t('新建')]);
          if (this.isIframe) {
            this.$bkMessage({
              message,
              theme: 'success',
            });
            this.$emit('close', true);
            return true;
          }
          if (this.isAdminPath) { // 管理员
            this.$bkMessage({
              message,
              theme: 'success',
            });
          } else {
            this.$bkInfo({
              type: 'success',
              title: this.$t('决策表{0}成功', [this.decisionId ? this.$t('编辑') : this.$t('新建')]),
              subTitle: this.$t('可以回到流程里继续使用'),
              cancelText: this.$t('关闭当前页'),
              extCls: 'decision-dialog',
              maskClose: false,
              escClose: false,
              cancelFn: () => {
                window.close();
              },
              closeFn: () => {},
            });
          }
          return true;
        } catch (error) {
          console.warn(error);
        } finally {
          this.saveLoading = false;
        }
      },
      // 调试
      async handleDebug() {
        const isDataEqual = tools.isDataEqual(this.decisionData, this.initData);
        if (!isDataEqual) {
          this.$bkInfo({
            title: this.$t('确定保存决策表并去执行调试?'),
            maskClose: false,
            width: 450,
            confirmLoading: true,
            confirmFn: async () => {
              try {
                this.debugLoading = true;
                const result = await this.handleSave();
                if (!result) return;
                this.isDebugDialogShow = true;
              } catch (error) {
                console.warn(error);
              } finally {
                this.debugLoading = false;
              }
            },
          });
        } else {
          this.isDebugDialogShow = true;
        }
      },
      // 取消
      handleCancel() {
        const cancelFn = () => {
          if (this.isIframe) {
            this.$emit('close');
            return;
          }
          if (this.isAdminPath) {
            this.$router.push({
              name: 'spaceAdmin',
              query: {
                activeTab: 'decisionTable',
                space_id: this.spaceId,
              },
            });
          } else {
            window.close();
          }
        };
        const isDataEqual = tools.isDataEqual(this.decisionData, this.initData);
        if (!isDataEqual) {
          this.$bkInfo({
            ...this.infoBasicConfig,
            confirmFn: () => {
              cancelFn();
            },
          });
        } else {
          cancelFn();
        }
      },
    },
  };
</script>

<style lang='scss' scoped>
  @import '../../../../../scss/mixins/scrollbar.scss';
  .decision-edit {
    height: 100%;
    display: flex;
    flex-direction: column;
    background: #f5f7fa;
    .header-wrap {
      display: flex;
      align-items: center;
      flex-shrink: 0;
      height: 48px;
      z-index: 1;
      padding-left: 24px;
      font-size: 16px;
      line-height: 24px;
      color: #313238;
      background: #fff;
      box-shadow: 0 3px 4px 0 #0000000a;
      .back-icon {
        font-size: 28px;
        color: #3a84ff;
        cursor: pointer;
      }
    }
    .content-wrap {
      padding: 24px;
      overflow-x: auto;
      @include scrollbar;
      .basic-wrap,
      .ruler-wrap {
        padding: 16px 24px 24px;
        background: #fff;
        box-shadow: 0 2px 4px 0 #1919290d;
        border-radius: 2px;
      }
      .basic-wrap {
        margin-bottom: 16px;
      }
      .partially-edited-tips {
        font-size: 12px;
        color: #ff9c01;
        font-weight: normal;
      }
    }
    .title-tag {
      font-size: 14px;
      line-height: 22px;
      font-weight: 600;
      color: #313238;
      margin-bottom: 15px;
    }
    .basic-form {
      ::v-deep .bk-form-content {
        width: 560px;
      }
    }
    .operate-wrap {
      display: flex;
      align-items: center;
      flex-shrink: 0;
      height: 48px;
      padding-left: 24px;
      button {
        margin-right: 8px !important;
        &:last-child {
          margin: 0 0 0 30px !important;
        }
      }
      &.at-bottom {
        position: relative;
        background: #fff;
        &::before {
          content: '';
          position: absolute;
          top: -4px;
          left: 0;
          z-index: 8;
          height: 4px;
          width: 100%;
          background-image: linear-gradient(0deg, #00000014 0%, #00000000 100%);
        }
      }
    }
  }
</style>
<style lang="scss">
  .decision-dialog {
    .bk-dialog-type-header {
      padding-bottom: 5px !important;
    }
    .bk-dialog-footer .bk-primary {
      display: none !important;
    }
  }
</style>
