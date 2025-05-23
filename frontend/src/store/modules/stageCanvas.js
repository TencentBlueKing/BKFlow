const stageCanvas = {
  namespaced: true,
  state: {
    activeNode: null,
  },
  mutations: {
    setActiveNode(state, node) {
      state.activeNode = node;
      console.log('stageCanvas.js_Line:9', state);
    },
  },
};
export default stageCanvas;
