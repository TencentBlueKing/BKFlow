<template>
  <div class="label-list">
    <table-operate
      ref="tableOperate"
      :space-id="spaceId"
      :placeholder="$t('搜索标签名称、标签范围、系统默认标签')"
      :search-list="searchList"
      @updateSearchValue="searchValue = $event">
      <bk-button
        theme="primary"
        :disabled="!spaceId"
        @click="showCreateLabelDialog = true">
        {{ $t("新增标签") }}
      </bk-button>
    </table-operate>
    <bk-table
      v-bkloading="{ isLoading: listLoading }"
      :data="labelList"
      :pagination="pagination"
      :max-height="tableMaxHeight"
      @page-change="handlePageChange"
      @page-limit-change="handlePageLimitChange"
      @expand-change="handleRowExpand">
      <bk-table-column
        type="expand"
        disabled
        width="30">
        <template slot-scope="props">
          <bk-table
            v-bkloading="{ isLoading: expandListLoading }"
            :data="props.row.children"
            :outer-border="false">
            <bk-table-column :label="$t('标签名称')">
              <template slot-scope="{ row }">
                <span
                  class="label-name"
                  :style="{ 'background-color': row.color }">
                  {{ row.full_path }}
                </span>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('标签描述')"
              prop="description" />
            <bk-table-column :label="$t('标签范围')">
              <template slot-scope="{ row }">
                <bk-tag
                  v-for="scope in row.label_scope"
                  :key="scope">
                  {{ labelScope[scope] }}
                </bk-tag>
              </template>
            </bk-table-column>
            <bk-table-column :label="$t('标签引用')">
              <i18n
                tag="div"
                path="labelReference">
                <span class="highlight">{{ 1 }}</span>
                <span class="highlight">{{ 2 }}</span>
              </i18n>
            </bk-table-column>
            <bk-table-column :label="$t('系统默认标签')">
              <template slot-scope="{ row }">
                <bk-tag
                  :theme="
                    row.is_default ? 'success' : 'default'
                  ">
                  {{ row.is_default ? $t("是") : $t("否") }}
                </bk-tag>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('操作')"
              width="200">
              <template slot-scope="{ row }">
                <bk-button
                  theme="primary"
                  text
                  @click="onEditLabel(row)">
                  {{ $t("编辑") }}
                </bk-button>
                <bk-button
                  theme="primary"
                  class="ml10"
                  text
                  @click="onDeleteLabel(row.id)">
                  {{ $t("删除") }}
                </bk-button>
              </template>
            </bk-table-column>
          </bk-table>
        </template>
      </bk-table-column>
      <bk-table-column :label="$t('标签名称')">
        <template slot-scope="{ row }">
          <span
            class="label-name"
            :style="{ 'background-color': row.color }">
            {{ row.name }}
          </span>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('标签描述')"
        prop="description" />
      <bk-table-column :label="$t('标签范围')">
        <template slot-scope="{ row }">
          <bk-tag
            v-for="scope in row.label_scope"
            :key="scope">
            {{ labelScope[scope] }}
          </bk-tag>
        </template>
      </bk-table-column>
      <bk-table-column :label="$t('标签引用')">
        <template slot-scope="{ row }">
          <i18n
            tag="div"
            path="labelReference">
            <span class="highlight">{{ row.reference.template_count }}</span>
            <span class="highlight">{{ row.reference.task_count }}</span>
          </i18n>
        </template>
      </bk-table-column>
      <bk-table-column :label="$t('系统默认标签')">
        <template slot-scope="{ row }">
          <bk-tag :theme="row.is_default ? 'success' : 'default'">
            {{ row.is_default ? $t("是") : $t("否") }}
          </bk-tag>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('操作')"
        width="200">
        <template slot-scope="{ row }">
          <bk-button
            theme="primary"
            text
            @click="onEditLabel(row)">
            {{ $t("编辑") }}
          </bk-button>
          <bk-button
            theme="primary"
            class="ml10"
            text
            @click="onDeleteLabel(row.id)">
            {{ $t("删除") }}
          </bk-button>
        </template>
      </bk-table-column>
    </bk-table>
    <create-label-dialog
      :is-show="showCreateLabelDialog"
      :label-data="editLabel"
      :is-edit="isEdit"
      @close="showCreateLabelDialog = false"
      @updateList="getLabelList" />
  </div>
</template>

<script>
import { LABEL_SCOPE } from '../../../../constants/index.js';
import { mapActions } from 'vuex';
import TableOperate from '../common/TableOperate.vue';
import tableHeader from '@/mixins/tableHeader.js';
import tableCommon from '../mixins/tableCommon.js';
import i18n from '@/config/i18n/index.js';
import CreateLabelDialog from './CreateLabelDialog.vue';
const SEARCH_LIST = [
    {
        id: 'name',
        name: i18n.t('标签名称'),
        isDefaultOption: true,
    },
    {
        id: 'creator',
        name: i18n.t('标签范围'),
    },
    {
        id: 'updated_by',
        name: i18n.t('系统默认标签'),
    },
];
export default {
    name: 'LabelManage',
    components: {
        TableOperate,
        CreateLabelDialog,
    },
    mixins: [tableHeader, tableCommon],
    data() {
        return {
            searchList: SEARCH_LIST,
            searchValue: '',
            selectedTpls: [],
            showCreateLabelDialog: false,
            labelList: [],
            labelScope: LABEL_SCOPE,
            editLabel: {},
            expandListLoading: false,
            pageType: 'labelList',
            isEdit: false,
            deleting: false,
        };
    },
    mounted() {
        this.getLabelList();
    },
    methods: {
        ...mapActions('label', [
            'loadLabelList',
            'deleteLabel',
            'loadLabelReference',
        ]),
        async getLabelList(parentId = null) {
            const isExpand = Boolean(parentId);

            const params = {
                space_id: this.spaceId,
                parent_id: parentId,
                limit: isExpand ? 1000 : this.pagination.limit,
                offset: isExpand
                    ? 0
                    : (this.pagination.current - 1) * this.pagination.limit,
            };
            try {
                isExpand
                    ? (this.expandListLoading = true)
                    : (this.listLoading = true);

                // 1. 获取标签列表
                const { data } = await this.loadLabelList(params);
                const list = data?.results || [];

                // 2. 获取引用数据
                let referenceMap = {};
                if (list.length) {
                    const refResp = await this.loadLabelReference({
                        space_id: this.spaceId,
                        label_ids: list.map(item => item.id).join(','),
                    });
                    referenceMap = refResp?.data || {};
                }

                // 3. 绑定 reference
                const bindReference = (labels) => {
                    labels.forEach((label) => {
                        label.reference = referenceMap[label.id];
                    });
                };

                if (isExpand) {
                    const parentLabel = this.labelList.find(label => label.id === parentId);
                    if (!parentLabel) return;

                    parentLabel.children = list;
                    bindReference(parentLabel.children);
                } else {
                    this.labelList = list;
                    bindReference(this.labelList);

                    this.pagination.count = data?.count || 0;
                    this.totalPage = Math.ceil(this.pagination.count / this.pagination.limit);
                }
            } catch (error) {
                console.error(error);
            } finally {
                this.listLoading = false;
                this.expandListLoading = false;
            }
        },

        onEditLabel(label) {
            this.editLabel = label;
            this.isEdit = true;
            this.showCreateLabelDialog = true;
        },
        onDeleteLabel(id) {
            this.$bkInfo({
                title: this.$t('确认删除该标签？'),
                subTitle: this.$t('关联的流程将同时移出本标签'),
                width: 400,
                confirmLoading: true,
                cancelText: this.$t('取消'),
                confirmFn: async () => {
                    await this.onDeleteConfirm(id);
                },
            });
        },
        async onDeleteConfirm(id) {
            if (this.deleting) return;
            this.deleting = true;
            try {
                const resp = await this.deleteLabel(id);
                if (resp.result === false) return;
                // 最后一页最后一条删除后，往前翻一页
                if (
                    this.pagination.current > 1
                    && this.totalPage === this.pagination.current
                    && this.pagination.count
                        - (this.totalPage - 1) * this.pagination.limit
                        === 1
                ) {
                    this.pagination.current -= 1;
                }
                this.getLabelList();
                this.updateUrl({ current: 1 });
                this.$bkMessage({
                    message: this.$t('标签删除成功！'),
                    theme: 'success',
                });
            } catch (e) {
                console.log(e);
            } finally {
                this.deleting = false;
            }
        },
        handleRowExpand(label) {
            if (label.children) return;
            this.getLabelList(label.id);
        },
    },
};
</script>

<style lang="scss" scoped>
.label-name {
    padding: 0 4px;
    border-radius: 11px;
    line-height: 16px;
    color: #ffffff;
}
:deep(.bk-table-expanded-cell) {
    padding-right: 0 !important;
    .bk-table-header-wrapper {
        display: none;
    }
}
.highlight {
    color: #3a84ff;
}
</style>
