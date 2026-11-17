"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""

# 包装器插件 code 集合：这些组件本身不是"可独立管理的插件"，而是代理/容器型节点
#   - remote_plugin：蓝鲸标准插件代理节点
#   - uniform_api：统一 API（开放插件）代理节点
#   - subprocess_plugin：子流程节点
# 它们不出现在"内置插件"列表里，也不参与插件目录（SpacePluginCatalogEntry）的判定。
#
# 本常量单独放在无依赖的底层模块里，而不是定义在 bkflow.plugin.services.plugin_schema_service：
# plugin_catalog 下的多个模块需要用它，若从 plugin_schema_service 导入，会形成
#   plugin_catalog.services.* -> plugin.services.plugin_schema_service
#     -> plugin_catalog.services.migration_service -> plugin.services.plugin_schema_service
# 的循环依赖，只能靠函数内延迟 import 绕开。把常量下沉到本模块后该环自然解除。
WRAPPER_CODES = {"remote_plugin", "uniform_api", "subprocess_plugin"}

# 不纳入「空间插件目录」的内置插件：这类是**功能入口**（子画布等），由画布自己的
# 入口单独选择，不需要作为业务插件参与目录管理（设计稿插件列表页不展示它们）。
#
# 与 WRAPPER_CODES 的区别：WRAPPER_CODES 是"代理/容器型节点"，在画布插件选择器里
# 也不出现、流程保存时也不校验；本集合里的插件画布侧**照常可用**（前端有专门的
# 选择入口），只是不进「空间插件目录」这张管理表。所以不能并进 WRAPPER_CODES，
# 否则画布选不到、流程保存还会被 guard_service 拦下。
CATALOG_EXCLUDED_BUILTIN_CODES = {"subcanvas_plugin"}
