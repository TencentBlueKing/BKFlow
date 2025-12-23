<template>
  <!-- :disabled="isViewMode" -->
  <div
    :class="['version-select-wrapper', isSubflowNodeConfig ? 'subflow-version':'template-version']">
    <bk-select
      ref="versionSelect"
      v-model="versionSelectValue"
      v-bkloading="{ isLoading: isVersionLoading , zIndex: 100 }"
      ext-popover-cls="select-version-popover-custom"
      :popover-min-width="isSubflowNodeConfig ? 577 : 318"
      :popover-width="isSubflowNodeConfig ? 577 : 318"
      :clearable="false"
      :placeholder="$t('请选择版本')"
      :ext-cls="`${isSubflowNodeConfig ? 'subflow-select' : 'template-select'}`"
      :searchable="listData.length>0"
      enable-scroll-load
      :scroll-loading="bottomLoadingOptions"
      @scroll-end="handleScrollToBottom"
      @change="handleVersionSelectChange">
      <bk-option
        v-for="option in listData"
        :id="option.id"
        :key="option.id"
        :name="option.version ?? option.desc ?? '--'">
        <div class="option-title">
          <span>{{ option.version ? option.version : $t('草稿版本') }}</span>
          <div
            v-if="option.id === tplSnapshotId && !option.draft"
            class="latest-version">
            <div class="text">
              {{ $t('最新') }}
            </div>
          </div>
        </div>
        <div class="version-desc">
          <p
            v-bk-overflow-tips
            class="version-desc-text">
            {{ option.desc }}
          </p>
        </div>
      </bk-option>
      <div
        v-if="listData.length>0"
        slot="extension"
        class="bottom-view-btn"
        @click="viewAllVerison">
        <i class="common-icon-box-top-right-corner" />
        <span>{{ $t('查看全部版本') }}</span>
      </div>
    </bk-select>
    <div
      v-if="tplSnapshotId === curSelectedVersionId && !isDraft"
      class="latest-version select-value-show">
      <div class="text">
        {{ $t('最新') }}
      </div>
    </div>
    <!-- && tplSnapshotId !== curSelectedVersionId -->
    <div
      v-if="!isDraft && isNotDraftAndInLatestVersion"
      class="callback-version-info"
      @click="onRollbackVersion">
      <svg
        class="bk-icon"
        viewBox="0 0 64 64"
        version="1.1"
        xmlns="http://www.w3.org/2000/svg"><path
          fill="#3A84FF"
          d="M32,4C16.5,4,4,16.5,4,32s12.5,28,28,28s28-12.5,28-28S47.5,4,32,4z M47,41.7c-3-3.2-7.1-5-11.5-5	H29v5.9c0,0.6-0.5,1-1,1c-0.3,0-0.5-0.1-0.7-0.3L16.4,32.5c-0.8-0.8-0.8-2,0-2.8c0,0,0,0,0,0l10.9-11c0.4-0.4,1-0.4,1.4,0	c0.2,0.2,0.3,0.4,0.3,0.7v6.3h2.1C39.9,25.8,47,32.9,47,41.7z" /></svg>
      <span>{{ $t('恢复到此版本') }}</span>
    </div>
  </div>
</template>
<script>
import { mapActions, mapState } from 'vuex';

export default {
  name: 'VersionSelect',
  props: {
    isSubflowNodeConfig: {
      type: Boolean,
      default: false,
    },
    isViewMode: {
      type: Boolean,
      default: false,
    },
    compVersion: {
      type: String,
      default: '',
    },
    subflowFormData: {
      type: Object,
      default: () => ({}),
    },
    tplSnapshotId: {
      type: [Number, String],
      default: '',
    },
    versionListData: {
      type: Array,
      default: () => [],
    },
    templateId: {
      type: [String, Number],
      default: '',
    },
    versionCount: {
      type: Number,
      default: 0,
    },
  },
  data() {
    return {
        listData: this.versionListData,
        versionSelectValue: '',
        isShowVersionList: false,
        versionListLoading: false,
        isVersionLoading: true,
        bottomLoadingOptions: {
          size: 'mini',
          isLoading: false,
        },
        currentPage: 1,
    };
  },
  computed: {
    ...mapState({
        spaceId: state => state.template.spaceId,
    }),
    curSelectedVersionId() {
      const curItem = this.listData.find(item => item.id === this.versionSelectValue);
      return curItem ? curItem.id : null;
    },
    isDraft() {
       let curDraftId = null;
       this.listData.forEach((item) => {
        if (item.draft) {
          curDraftId = item.id;
          return;
        }
      });
      return curDraftId === this.versionSelectValue;
    },
    isHaveDraft() {
      return this.listData.some(item => item.draft);
    },
    isNotDraftAndInLatestVersion() {
      return this.isHaveDraft || this.tplSnapshotId !== this.curSelectedVersionId;
    },
  },
  watch: {
    compVersion: {
      handler(val, oldVal) {
        if (val === oldVal) {
          return;
        }
        this.$nextTick(() => {
          this.versionSelectValue = this.getVersionIdToNumber(val);
        });
      },
      immediate: true,
    },
    versionListData: {
      handler(val) {
        this.listData = val;
        this.$nextTick(() => {
          this.versionSelectValue = this.getVersionIdToNumber(this.compVersion);
        });
      },
      immediate: true,
      deep: true,
    },
  },
  methods: {
    ...mapActions('template/', [
      'getTemplateVersionSnapshotList',
    ]),
    async handleScrollToBottom() {
      if (this.listData.length >= this.versionCount) {
        return;
      }
      this.bottomLoadingOptions.isLoading = true;
      this.currentPage += 1;
      const res = await this.getTemplateVersionSnapshotList({
          template_id: this.templateId,
          space_id: this.spaceId,
          limit: 10,
          offset: (this.currentPage - 1) * 10,
      });
      this.listData = this.listData.concat(res.data.results || []);
      this.bottomLoadingOptions.isLoading = false;
    },
    viewAllVerison() {
      this.$refs.versionSelect.handleClose();
      if (this.isSubflowNodeConfig) {
        this.$emit('viewAllSubflowVerison');
      } else {
        this.$emit('viewAllVerison');
      }
    },
    handleVersionSelectChange() {
      this.$emit('versionSelectChange', this.getVersionNumber(this.versionSelectValue), this.listData);
    },
    getVersionIdToNumber(value) {
      this.isVersionLoading = true;
      let temporaryVersionId = null;
      this.listData?.forEach((item) => {
         if ((this.compVersion === null || this.compVersion === '') && item.draft) {
          temporaryVersionId = item.id;
          return;
        }
        if (item.version === value) {
          temporaryVersionId = item.id;
          return;
        }
      });
      this.isVersionLoading = false;
      return temporaryVersionId;
    },
    getVersionNumber(id) {
      let curVersion = null;
      this.listData.forEach((item) => {
        if (item.id === id) {
          curVersion = item.version;
          return;
        }
      });
      return curVersion;
    },
    // 回滚版本
    onRollbackVersion() {
      let curRollVersion = '';
      this.listData.forEach((item) => {
        if (item.id === this.versionSelectValue) {
          curRollVersion = item.version;
          return;
        }
      });
      this.$emit('rollbackVersion', curRollVersion);
    },
  },
};
</script>
<style lang="scss" scoped>
    .template-version{
      display: flex;
      align-items: center;
      margin-left: 16px;
      border-left: 1px solid #dcdee5;
      height: 24px;
      position: relative;
    }
    ::v-deep .template-select{
        margin-left: 16px;
        width: 160px;
        height: 24px;
        line-height: 24px;
        background: #F0F1F5;
        .bk-select-name{
            height: 24px;
        }
        .bk-select-angle{
            top:1px
        }
        .bk-select-clear{
            top:5px;
        }
        .is-default-trigger.is-unselected:before{
            top: -4px;
        }
    }
    .option-title{
       display: flex;
       align-items: center;
    }
    .latest-version{
        font-size: 10px;
        color: #14A568;
        line-height: 16px;
        background: #E4FAF0;
        border: 1px solid #A5E0C6;
        border-radius: 2px;
        margin-left: 15px;
        .text{
            padding: 0px 4px;
        }
    }
    .bottom-view-btn{
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 5px 0;
      cursor: pointer;
      .common-icon-box-top-right-corner{
        margin-right: 8px;
        margin-top: 3px;
      }
    }
</style>
<style lang="scss">
.common-icon-box-top-right-corner:before {
	content: "\e10f";
}
.version-desc-text{
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
  color: #979BA5;
  line-height: 20px;
  padding-bottom: 8px;
}
.select-version-popover-custom{
    .bk-options-wrapper{
        max-height: 261px !important;
        // .bk-options-single{
        //     .is-selected{
        //         .bk-option-content{
        //           background: #E1ECFF;
        //         }
        //     }
        // }
    }
}
.callback-version-info{
  font-size: 14px;
  color: #3A84FF;
  line-height: 22px;
  margin-left: 16px;
  display: flex;
  align-content: center;
  cursor: pointer;
  .bk-icon{
    width: 16px;
    height: 16px;
    margin-right: 4px;
    margin-top: 3px;
    fill: rgb(58, 132, 255) !important;
  }
}
.select-value-show{
  position: absolute;
  left: 50px;
}
</style>

