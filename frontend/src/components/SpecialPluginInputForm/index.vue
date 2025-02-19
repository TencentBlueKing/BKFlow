<template>
  <div class="special-plugin-form-wrapper">
    <DmnPlugin
      v-if="code === 'dmn_plugin'"
      ref="formRef"
      :value="value"
      :is-view-mode="isViewMode"
      :space-id="spaceId"
      :template-id="templateId"
      :variable-list="variableList"
      :node-id="nodeId"
      :inputs-variable-fields="inputsVariableFields"
      :variable-cited="variableCited"
      @update="updateInputsValue"
      @updateInputs="updateInputs"
      @updateOutputs="$emit('updateOutputs', $event)"
      @updateVarCitedData="$emit('updateVarCitedData')" />

    <ValueAssignPlugin
      v-else-if="code === 'value_assign'"
      ref="formRef"
      :value="value"
      :variable-list="variableList"
      :is-view-mode="isViewMode"
      @update="updateInputsValue" />
  </div>
</template>
<script>
  import DmnPlugin from './DmnPlugin/index.vue';
  import ValueAssignPlugin from './ValueAssignPlugin/index.vue';

  export default {
    components: {
      DmnPlugin,
      ValueAssignPlugin,
    },
    props: {
      value: {
        type: Object,
        default: () => ({}),
      },
      code: {
        type: String,
        default: '',
      },
      isViewMode: {
        type: Boolean,
        default: true,
      },
      spaceId: {
        type: [String, Number],
        default: '',
      },
      templateId: {
        type: [String, Number],
        default: '',
      },
      variableList: {
        type: Array,
        default: () => ([]),
      },
      nodeId: {
        type: String,
        default: '',
      },
      variableCited: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        inputs: [],
        inputsVariableFields: [],
      };
    },
    computed: {

    },
    methods: {
      onHookChange(type, data) {
        this.$emit('onHookChange', type, data);
      },
      updateInputsValue(val, variableFields = []) {
        this.inputsVariableFields = variableFields;
        this.$emit('update', val);
      },
      updateInputs(val) {
        this.inputs = val;
      },
      validate() {
        return this.$refs.formRef.validate();
      },
    },
  };
</script>
<style lang="scss" scoped>

</style>
