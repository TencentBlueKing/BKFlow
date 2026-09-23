<template>
  <span class="user-display-name-container">
    <span v-if="!name">{{ '--' }}</span>
    <bk-user-display-name
      v-else-if="isMultiTenantMode"
      :user-id="name" />
    <span v-else>{{ name }}</span>
  </span>
</template>
<script>
import { mapState } from 'vuex';

export default {
  props: {
    name: { type: String, default: '' },
  },
  computed: {
    ...mapState({ isMultiTenantMode: state => state.isMultiTenantMode }),
  },
};
</script>
