<template>
  <div
    class="JumpLinkBKFlowOrExternal"
    @click.stop="jumpToTagetUrl">
    <slot />
  </div>
</template>

<script>
import { mapState } from 'vuex';

export default {
    name: 'JumpLinkBKFlowOrExternal',
    props: {
        getTargetUrl: {
            type: Function,
            default: () => '',
        },
        query: {
            type: Object,
            default: () => ({}),
        },
    },
    computed: {
        ...mapState({
        isIframe: state => state.isIframe,
      }),
    },
    methods: {
        jumpToTagetUrl() {
            console.log('JumpLinkBKFlowOrExternal.vue_Line:25', this.getTargetUrl());
            if (!this.isIframe) {
                // console.log('JumpLinkBKFlowOrExternal.vue_Line:25', this.getTargetUrl());
                window.open(this.getTargetUrl(), '_blank');
            } else {
                console.log('JumpLinkBKFlowOrExternal.vue_Line:34', this.query);
              window.parent.postMessage({ eventName: 'jump-to-external-url', data: this.query }, '*');
            }
        },
    },
};
</script>

