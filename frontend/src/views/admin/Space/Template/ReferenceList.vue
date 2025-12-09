<template>
  <div v-if="referenceList.length > 0">
    <div :class="titleClass">
      {{ title }}
    </div>
    <div
      v-for="referenceItem in referenceList"
      :key="referenceItem[0]">
      <bk-table
        :data="getTableData(referenceItem)"
        ext-cls="referenced-process-table"
        :max-height="197"
        :dark-header="true"
        :stripe="true">
        <bk-table-column
          :render-header="(h) => renderHeader(h, referenceItem)">
          <template slot-scope="props">
            <div class="reference-list">
              <span>{{ getDisplayName(props.row) }}</span>
              <i
                class="common-icon-box-top-right-corner icon-view-sub"
                @click="openReferencePage(props.row)" />
            </div>
          </template>
        </bk-table-column>
      </bk-table>
    </div>
  </div>
</template>

<script>
import { mapState } from 'vuex';
export default {
  name: 'ReferenceList',
  props: {
    referenceList: {
      type: Array,
      default: () => [],
    },
    title: {
      type: String,
      required: true,
    },
    titleClass: {
      type: String,
      default: '',
    },
    referenceType: {
      type: String,
      default: 'process',
    },
    renderHeaderMethod: {
      type: Function,
      required: true,
    },
  },
  computed: {
    ...mapState({
      spaceId: state => state.template.spaceId,
    }),
  },
  methods: {
    getTableData(referenceItem) {
      if (this.referenceType === 'process') {
        return referenceItem[1].referenced;
      } if (this.referenceType === 'decision') {
        return referenceItem[1].decision_info;
      }
      return [];
    },
    renderHeader(h, referenceItem) {
      return this.renderHeaderMethod(h, referenceItem);
    },
    getDisplayName(row) {
      if (this.referenceType === 'process') {
        return row.root_template_name;
      } if (this.referenceType === 'decision') {
        return row.name;
      }
      return '';
    },
    getTemplateId(row) {
      if (this.referenceType === 'process') {
        return row.root_template_id;
      } if (this.referenceType === 'decision') {
        return row.id;
      }
      return '';
    },
    openReferencePage(row) {
      try {
        const routeData = this.getJumpLink(row);
        const resolved = this.$router.resolve(routeData);
        if (resolved && resolved.href) {
          window.open(resolved.href, '_blank');
        }
      } catch (e) {
        console.error(e);
      }
    },
    getJumpLink(row) {
      if (this.referenceType === 'process') {
        return {
          name: 'templatePanel',
          params: {
            templateId: row.root_template_id,
            type: 'view',
          },
        };
      }
      if (this.referenceType === 'decision') {
        return {
          name: 'spaceAdmin',
          query: {
            activeTab: 'decisionTable',
            space_id: this.$route.query.space_id,
            id: row.id
          },
        };
      }
      return {};
    },
  },
};
</script>

<style lang="scss" scoped>
.reference-list {
  display: flex;
  align-items: center;

  .icon-view-sub {
    cursor: pointer;
    color: #3a84ff;

    &:hover {
      color: #699df4;
    }
  }
}
.decision-reference-list {
    margin-top: 16px;
}
</style>
