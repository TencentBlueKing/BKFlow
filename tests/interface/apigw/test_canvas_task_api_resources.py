import re
from pathlib import Path

import jsonschema
import pytest
import yaml

RESOURCE_PATH = Path(__file__).resolve().parents[3] / "bkflow/apigw/management/commands/data/api-resources.yml"
RESOURCES = yaml.safe_load(RESOURCE_PATH.read_text())["paths"]
ENDPOINTS = (
    ("/space/{space_id}/get_node_outputs/", "post"),
    ("/space/{space_id}/get_tasks_pipeline/", "get"),
    ("/space/{space_id}/task/{task_id}/get_task_operation_record/", "get"),
)


@pytest.mark.parametrize("path,method", ENDPOINTS)
def test_path_parameters_are_declared(path, method):
    """每个 URL 占位符都有必填的路径参数定义。"""
    operation = RESOURCES[path][method]
    parameters = {item["name"]: item for item in operation["parameters"] if item["in"] == "path"}
    assert set(parameters) == set(re.findall(r"{([^}]+)}", path))
    assert all(item["required"] and item["schema"]["type"] == "integer" for item in parameters.values())
    assert operation["x-bk-apigateway-resource"]["backend"]["method"] == method


def test_query_parameters_are_declared():
    """声明任务列表和操作记录的查询条件及必填性。"""
    pipeline = RESOURCES["/space/{space_id}/get_tasks_pipeline/"]["get"]
    records = RESOURCES["/space/{space_id}/task/{task_id}/get_task_operation_record/"]["get"]
    for operation, name, required in ((pipeline, "task_ids", True), (records, "node_id", False)):
        parameter = next(item for item in operation["parameters"] if item["name"] == name)
        assert parameter["in"] == "query"
        assert parameter["required"] is required
        assert parameter["schema"]["type"] == "string"


def test_node_outputs_request_body_matches_required_fields():
    """请求体契约接受实际参数，并拒绝缺字段或类型错误。"""
    body = RESOURCES["/space/{space_id}/get_node_outputs/"]["post"]["requestBody"]
    assert body["required"] is True
    schema = body["content"]["application/json"]["schema"]
    jsonschema.validate({"task_id": 17, "node_ids": ["n1", "n2"]}, schema)
    for invalid in ({}, {"task_id": 17}, {"task_id": 17, "node_ids": "n1"}):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, schema)


@pytest.mark.parametrize(
    "path,method,data",
    (
        ("/space/{space_id}/get_node_outputs/", "post", [{"n1": [{"_result": True, "_loop": 1}]}]),
        ("/space/{space_id}/get_tasks_pipeline/", "get", {"17": {"activities": {}}}),
        (
            "/space/{space_id}/task/{task_id}/get_task_operation_record/",
            "get",
            [{"id": 1, "instance_id": 17, "node_id": "", "operate_type": "create"}],
        ),
    ),
)
def test_success_response_has_usable_schema(path, method, data):
    """声明返回结构，并接受 Engine 返回的成功数据。"""
    schema = RESOURCES[path][method]["responses"]["200"]["content"]["application/json"]["schema"]
    assert {"result", "message", "data"} <= set(schema["properties"])
    jsonschema.validate({"result": True, "message": "success", "data": data}, schema)
