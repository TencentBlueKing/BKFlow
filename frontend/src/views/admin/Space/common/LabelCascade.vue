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
            selectLabelList: [], // 实际选中的标签列表
            labelIds: [], // 绑定列表选中态
            isShow: false,
            secondLabelList: [],
            foucsId: 0,
            loading: false,
            isInitialized: false,
            isShowCreate: false,
            searchStr: '',
            needReload: true, // 是否需要重新绑定一级标签选中态（刷新列表后重新绑定）
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
            tools.throttle(this.getLabelList, 300).call(this);
        },
    },
    methods: {
        ...mapActions('label', ['loadLabelList', 'deleteLabel']),
        async getLabelList(parentLabel = null) {
            try {
                this.loading = true;
                const params = {
                    space_id: this.spaceId,
                    parent_id: parentLabel ? parentLabel.id : null,
                    limit: 1000,
                    offset: 0,
                    name: this.searchStr,
                    label_scope: this.scope,
                };
                const resp = await this.loadLabelList(params);
                if (parentLabel) {
                    const children = resp.data.results || [];
                    parentLabel.children = children;
                    this.secondLabelList = children;
                    const parentChecked = this.labelIds.includes(parentLabel.id);
                    if (parentChecked) {
                        children.forEach((child) => {
                            this.addLabelId(child);
                            this.addToSelect(child);
                        });
                    } else {
                        children.forEach((child) => {
                            this.removeLabelId(child.id);
                        });
                    }
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
        async isVisible(val) {
            const popover = this.getPopoverInstance();
            if (val) {
                popover.show();
                this.isShow = true;
                if (!this.isInitialized) {
                    // 初始化
                    await this.getLabelList();
                    this.isInitialized = true;
                }
                if (this.needReload) {
                    // 有二级标签选中时，选中其一级标签
                    this.selectLabelList.forEach((label) => {
                        if (label.full_path.includes('/')) {
                            const parentFullPath = label.full_path.split('/')[0];
                            const parentLabel = this.labelList.find(item => item.name === parentFullPath);
                            if (parentLabel) {
                                this.addLabelId(parentLabel);
                            }
                        }
                    });
                    this.needReload = false;
                }
            } else {
                popover.hide();
                this.isShow = false;
            }
        },
        async handleClickFirstLabel(label) {
            this.foucsId = label.id;
            if (!label.has_children) {
                this.secondLabelList = [];
            } else {
                if (label.children) {
                    this.secondLabelList = label.children;
                } else {
                  await this.getLabelList(label);
                }
            }
        },
        handleCheckChange(label, checked) {
            if (checked) {
                this.handleCheck(label);
            } else {
                this.handleUncheck(label);
            }
        },
        handleCheck(label) {
            this.addLabelId(label);
            // 选中一级 → 选中所有二级
            if (label.has_children && Array.isArray(label.children)) {
                label.children.forEach((child) => {
                    this.addLabelId(child);
                    this.addToSelect(child);
                });
                return;
            }
            // 选中二级
            if (label.parent_id) {
                const parent = this.labelList.find(item => item.id === label.parent_id);
                if (parent) {
                    // 父级只进 labelIds
                    this.addLabelId(parent);
                    // 展示列表里如果有父级，移除
                    this.removeFromSelect(parent.id);
                }
                // 二级进展示
                this.addToSelect(label);
                return;
            }
            // 普通一级（没有 children 的）
            if (!label.has_children) {
                this.addToSelect(label);
            }
        },
        handleUncheck(label) {
            this.removeLabelId(label.id);
            // 取消一级 → 取消所有二级
            if (label.has_children && Array.isArray(label.children)) {
                label.children.forEach((child) => {
                    this.removeLabelId(child.id);
                });
                // 确保一级也不在 select 中
                this.removeFromSelect(label.id);
            }

            // 取消二级 → 如果没有兄弟被选中，取消一级
            if (label.parent_id) {
                const parent = this.labelList.find(item => item.id === label.parent_id);
                if (!parent || !Array.isArray(parent.children)) return;
                const hasSelectedSibling = parent.children.some(child => this.labelIds.includes(child.id));
                if (!hasSelectedSibling) {
                    this.removeLabelId(parent.id);
                }
            }
        },
        addLabelId(label) {
            if (!this.labelIds.includes(label.id)) {
                this.labelIds.push(label.id);
            }
        },
        addToSelect(label) {
            if (this.selectLabelList.some(item => item.id === label.id)) return;
            this.selectLabelList.push({
                id: label.id,
                name: label.name,
                color: label.color,
                full_path: label.full_path,
            });
        },
        removeFromSelect(id) {
            this.selectLabelList = this.selectLabelList.filter(item => item.id !== id);
        },
        removeLabelId(id) {
            this.removeFromSelect(id);
            this.labelIds = this.labelIds.filter(labelId => labelId !== id);
        },
        hide() {
            this.isShow = false;
            const isEqual = tools.isDataEqual(this.value, this.selectLabelList);
            if (isEqual) return;
            this.$emit('confirm', this.selectLabelList);
            this.needReload = true;
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
