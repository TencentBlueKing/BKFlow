import BoolSwitch from './BoolSwitch.vue';
import OptionRadio from './OptionRadio.vue';
import TextInput from './TextInput.vue';
import MemberSelectorControl from './MemberSelectorControl.vue';
import JsonEditorControl from './JsonEditorControl.vue';
import CredentialMap from './CredentialMap.vue';
import ApiPluginConfig from './ApiPluginConfig.vue';
import PluginScope from './PluginScope.vue';
import EngineKv from './EngineKv.vue';

const registry = {
  switch: BoolSwitch,
  radio: OptionRadio,
  select: OptionRadio,
  input: TextInput,
  member_selector: MemberSelectorControl,
  json: JsonEditorControl,
  credential_map: CredentialMap,
  api_plugin_config: ApiPluginConfig,
  plugin_scope: PluginScope,
  engine_kv: EngineKv,
};

// 未声明或未知 control 一律回退到 JSON 编辑器，保证复杂/未改造配置不回退
export function getControlComponent(control) {
  return registry[control] || JsonEditorControl;
}

export default registry;
