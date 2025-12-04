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


from bamboo_engine.context import Context
from bamboo_engine.eri import ContextValue, ContextValueType
from jsonschema import Draft4Validator
from pipeline.eri.runtime import BambooDjangoRuntime
from pipeline.eri.utils import CONTEXT_VALUE_TYPE_MAP
from pipeline.validators import validate_pipeline_tree

from bkflow.pipeline_web import exceptions
from bkflow.pipeline_web.parser.format import classify_constants
from bkflow.pipeline_web.parser.schemas import KEY_PATTERN_RE, WEB_PIPELINE_SCHEMA


def validate_web_pipeline_tree(web_pipeline_tree):
    # schema validate
    valid = Draft4Validator(WEB_PIPELINE_SCHEMA)
    errors = []
    for error in sorted(valid.iter_errors(web_pipeline_tree), key=str):
        errors.append("{}: {}".format("→".join(map(str, error.absolute_path)), error.message))
    if errors:
        raise exceptions.ParserWebTreeException(",".join(errors))

    # constants key pattern validate
    key_validation_errors = []
    context_values = []
    classification = classify_constants(web_pipeline_tree["constants"], is_subprocess=False)
    for key, const in web_pipeline_tree["constants"].items():
        key_value = const.get("key")
        if key != key_value:
            key_validation_errors.append("constants {} key property value: {} not matched".format(key, key_value))
            continue

        if not KEY_PATTERN_RE.match(key):
            key_validation_errors.append("invalid key: {}".format(key))

        # Skip constants that are not in data_inputs (e.g., component_outputs with empty source_info)
        if key_value not in classification["data_inputs"]:
            # If it's a component_outputs type with empty source_info, it's invalid
            if const.get("source_type") == "component_outputs" and not const.get("source_info"):
                key_validation_errors.append(
                    "constants {} has source_type 'component_outputs' but source_info is empty".format(key)
                )
            continue

        data_type = classification["data_inputs"][key_value]["type"]
        context_type = ContextValueType(CONTEXT_VALUE_TYPE_MAP[data_type])
        context_values.append(
            ContextValue(key=key_value, type=context_type, value=const["value"], code=const.get("custom_type", ""))
        )

    # outputs key pattern validate
    for output_key in web_pipeline_tree["outputs"]:
        if not KEY_PATTERN_RE.match(output_key):
            key_validation_errors.append("invalid outputs key: {}".format(output_key))

    if key_validation_errors:
        raise exceptions.ParserWebTreeException("\n".join(key_validation_errors))

    runtime = BambooDjangoRuntime()
    try:
        Context(runtime, context_values, {}).hydrate()
    except Exception as e:
        raise exceptions.ParserWebTreeException(f"constant verification failed: {str(e)}")

    validate_pipeline_tree(web_pipeline_tree, cycle_tolerate=True)
