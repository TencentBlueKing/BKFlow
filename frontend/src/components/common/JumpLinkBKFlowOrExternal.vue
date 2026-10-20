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
        async jumpToTagetUrl() {
            if (!this.isIframe) {
                const url = await this.getTargetUrl();
                window.open(url, '_blank');
            } else {
              window.parent.postMessage({ eventName: 'jump-to-external-url', data: this.query }, '*');
            }
        },
    },
};
</script>

