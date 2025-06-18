const stageCanvas = {
  namespaced: true,
  state: {
    activeNode: null,
    pluginsDetail: {
      component: {}, uniform_api: {}, blueking: {},
    },
  },
  mutations: {
    setActiveNode(state, node) {
      state.activeNode = node;
    },
    setPluginsDetail(state, details) {
      Object.assign(state.pluginsDetail, details);
    },
  },
};
export default stageCanvas;
