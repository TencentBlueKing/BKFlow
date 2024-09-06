<template>
  <div class="tag-switch">
    <bk-switcher
      v-if="formMode"
      v-model="checkedValue"
      :disabled="!editable || disabled"
      :size="size"
      :theme="theme">
    </bk-switcher>
    <span v-else class="rf-view-value">{{ value }}</span>
  </div>
</template>
<script>
  import { getFormMixins } from '../formMixins.js'

  export const attrs = {
    value: {
      type: Boolean,
      required: true,
      default: false,
    },
    disabled: {
      type: Boolean,
      default: false,
    },
    size: {
      type: String,
      default: 'normal',
    },
    theme: {
      type: String,
      default: 'success',
    },
  }
  export default {
    name: 'TagSwitch',
    mixins: [getFormMixins(attrs)],
    computed: {
      checkedValue: {
        get () {
          return this.value
        },
        set (val) {
          this.updateForm(val)
        },
      },
    },
  }
</script>
<style lang="scss" scoped>
  .tag-switch {
    line-height: 30px;
  }
</style>
