<template>
  <div class="tag-datetime-range">
    <div v-if="formMode">
      <bk-date-picker
        v-model="dateValue"
        :type="'datetimerange'"
        :disabled="!editable || disabled"
        :placeholder="placeholder">
      </bk-date-picker>
      <span v-show="!validateInfo.valid" class="common-error-tip error-info">{{validateInfo.message}}</span>
    </div>
    <span v-else class="rf-view-value">{{(viewValue === 'undefined' || viewValue === '') ? '--' : viewValue}}</span>
  </div>
</template>
<script>
  import '@/utils/i18n.js'
  import i18n from '@/config/i18n/index.js'
  import { getFormMixins } from '../formMixins.js'
  import moment from 'moment-timezone'

  export const attrs = {
    placeholder: {
      type: String,
      required: false,
      default: i18n.t('请选择日期时间'),
      desc: 'placeholder',
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
      desc: i18n.t('禁用选择器'),
    },
    value: {
      type: Array,
      required: false,
      default: () => ([]),
    },
  }
  export default {
    name: 'TagDatetimeRange',
    mixins: [getFormMixins(attrs)],
    computed: {
      dateValue: {
        get () {
          return this.value
        },
        set (val) {
          const newVal = val.map(item => {
            if (item) {
              return moment(item).format('YYYY-MM-DD HH:mm:ss')
            }
            return item
          })
          this.updateForm(newVal)
        },
      },
      viewValue () {
        return this.value?.join('-')
      },
    },
  }
</script>
<style lang="scss" scoped>
.tag-datetime-range {
  .bk-date-picker {
    width: 100%;
  }
}
</style>
