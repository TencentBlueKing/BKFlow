<template>
  <div>
    <bk-popover
      ref="labelPopover"
      theme="light"
      placement="bottom-start"
      :is-show="true"
      trigger="manual"
      width="350"
      class="label-popover"
      ext-cls="label-cascade-popover"
      :arrow="false"
      :on-hide="hide">
      <div @click="isVisible(true)">
        <slot
          name="trigger"
          :list="selectLabelList"
          :is-show="isShow" />
      </div>
      <template #content>
        <bk-input
          v-model.trim="searchStr"
          :left-icon="'bk-icon icon-search'"
          class="search-input" />
        <div
          v-bkloading="{ isLoading: loading, zIndex: 102 }"
          class="cascade-content">
          <div class="first-label">
            <ul class="label-list">
              <li
                v-for="label in labelList"
                :key="label.id"
                :class="[
                  'label-item',
                  { active: label.id === foucsId },
                ]"
                @click="handleClickFirstLabel(label)">
                <bk-checkbox
                  :value="labelIds.includes(label.id)"
                  @change="handleCheckChange(label, $event)">
                  {{ label.name }}
                </bk-checkbox>
                <bk-icon
                  v-if="label.has_children"
                  type="angle-right"
                  class="angle-icon" />
              </li>
            </ul>
          </div>
          <div
            v-if="secondLabelList.length"
            class="second-label">
            <ul class="label-list">
              <li
                v-for="label in secondLabelList"
                :key="label.id"
                class="label-item">
                <bk-checkbox
                  :value="labelIds.includes(label.id)"
                  @change="handleCheckChange(label, $event)">
                  {{ label.name }}
                </bk-checkbox>
              </li>
            </ul>
          </div>
        </div>
        <div class="label-select-extension">
          <div
            class="add-label"
            data-test-id="tabTemplateConfig_form_editLabel"
            @click="onCreateLabel">
            <i class="bk-icon icon-plus-circle" />
            <span>{{ $t("新建标签") }}</span>
          </div>
          <div
            class="label-manage"
            data-test-id="tabTemplateConfig_form_LabelManage"
            @click="onManageLabel">
            <i class="common-icon-label" />
            <span>{{ $t("标签管理") }}</span>
          </div>
          <div
            class="refresh-label"
            data-test-id="process_list__refreshLabel"
            @click="getLabelList">
            <i class="bk-icon icon-right-turn-line" />
          </div>
        </div>
      </template>
    </bk-popover>
    <CreateLabelDialog
      :is-show="isShowCreate"
      :scope="scope"
      @close="isShowCreate = false"
      @updateList="getLabelList" />
  </div>
</template>

<script>
import { mapActions, mapState } from 'vuex';
import CreateLabelDialog from '../labelManage/CreateLabelDialog.vue';
import tools from '@/utils/tools.js';
export default {
    name: 'LabelCascade',
    components: {
        CreateLabelDialog,
    },
    props: {
        value: {
            type: Array,
            default: () => [],
        },
        scope: {
            type: String,
            default: '',
        },
    },
    data() {
        return {
            showCreateLabelDialog: false,
            labelList: [],
            selectLabelList: [],
            labelIds: [],
            isShow: false,
            secondLabelList: [],
            foucsId: 0,
            loading: false,
            isInitialized: false,
            isShowCreate: false,
            searchStr: '',
        };
    },
    computed: {
        ...mapState({
            spaceId: state => state.spaceId,
        }),
    },
    watch: {
        value: {
            handler(val) {
                this.selectLabelList = [...val];
                this.labelIds = val.map(item => item.id);
            },
            immediate: true,
        },
        searchStr() {
            console.log(111);
            tools.throttle(this.getLabelList, 300).call(this);
        },
    },
    methods: {
        ...mapActions('label', ['loadLabelList', 'deleteLabel']),
        async getLabelList(parentId = null) {
            try {
                this.loading = true;
                const params = {
                    space_id: this.spaceId,
                    parent_id: parentId,
                    limit: 1000,
                    offset: 0,
                    name: this.searchStr,
                };
                const resp = await this.loadLabelList(params);
                if (parentId) {
                    this.labelList.find(label => label.id === parentId).children = resp.data.results;
                    this.secondLabelList = resp.data.results;
                    return;
                }
                this.secondLabelList = [];
                this.labelList = resp.data.results;
            } catch (e) {
                console.error(e);
            } finally {
                this.loading = false;
            }
        },
        getPopoverInstance() {
            return this.$refs.labelPopover.instance;
        },
        isVisible(val) {
            const popover = this.getPopoverInstance();
            if (val) {
                popover.show();
                this.isShow = true;
                if (this.isInitialized) return;
                this.getLabelList();
                this.isInitialized = true;
            } else {
                popover.hide();
                this.isShow = false;
            }
        },
        handleClickFirstLabel(label) {
            this.foucsId = label.id;
            if (!label.has_children) {
                this.secondLabelList = [];
            } else {
                if (label.children) {
                    this.secondLabelList = label.children;
                } else {
                    this.getLabelList(label.id);
                }
            }
        },
        handleCheckChange(label, checked) {
            if (checked) {
                this.selectLabelList.push({
                    id: label.id,
                    name: label.name,
                    color: label.color,
                    full_path: label.full_path,
                });
            } else {
                this.selectLabelList = this.selectLabelList.filter(item => item.id !== label.id);
            }
        },
        hide() {
            this.isShow = false;
            const isEqual = tools.isDataEqual(this.value, this.selectLabelList);
            if (isEqual) return;
            this.$emit('confirm', this.selectLabelList);
        },
        onCreateLabel() {
            this.isShowCreate = true;
        },
        onManageLabel() {
            const { href } = this.$router.resolve({
          name: 'spaceAdmin',
          query: {
            space_id: this.spaceId,
            activeTab: 'labelManage',
          },
        });
            window.open(href, '_blank');
        },
    },
};
</script>

<style lang="scss" scoped>
.search-input {
    height: 32px;
    :deep(.bk-form-input) {
        border: none;
    }
}
.label-popover {
    width: 100%;
}
.cascade-content {
    display: flex;
    height: 205px;
    overflow: auto;
    border: 1px solid #dcdee5;
    border-left: none;
    border-right: none;
    .first-label {
        border-right: 1px solid #dcdee5;
        width: 50%;
    }
    .second-label {
        width: 50%;
    }
    .label-list {
        padding-top: 9px;
        .label-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px;
            height: 32px;
            width: 100%;
            cursor: pointer;
            .angle-icon {
                font-size: 16px !important;
                color: #c4c6cc;
            }
            &:hover {
                background-color: #f5f7fa;
            }
            &.active {
                color: #3a84ff;
                background: #e1ecff;
                :deep(.bk-checkbox-text) {
                    color: #3a84ff;
                }
            }
        }
    }
}
.label-select-extension {
    height: 40px;
    display: flex;
    text-align: center;
    line-height: 40px;
    cursor: pointer;
    .add-label {
        width: 50%;
    }
    .label-manage {
        flex: 1;
    }
    .add-label,
    .label-manage {
        position: relative;
        &:hover {
            background: #f0f1f5;
        }
        &::after {
            content: "";
            position: absolute;
            width: 1px;
            height: 16px;
            display: block;
            right: -1px;
            top: 12px;
            background: #dcdee5;
        }
    }
    .refresh-label {
        padding: 0 16px;
        &:hover {
            background: #f0f1f5;
        }
    }
    & .common-icon-label,
    & .icon-plus-circle {
        font-size: 14px;
        color: #979ba5;
    }
    & > span {
        font-size: 12px;
    }
}
</style>

<style lang="scss">
.bk-tooltip-ref {
    width: 100%;
}
.label-cascade-popover {
    .tippy-tooltip {
        border: 1px solid #dcdee5;
        padding: 4px 0 0 0;
    }
}
</style>
