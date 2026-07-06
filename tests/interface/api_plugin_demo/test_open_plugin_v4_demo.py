"""
测试 api_plugin_demo 中用于 stage 联调的 open plugin v4 协议示例。
"""

from pathlib import Path

import pytest
import yaml
from django.urls import Resolver404, resolve
from rest_framework.test import APIRequestFactory

from bkflow.api_plugin_demo import v4

URLCONF = "bkflow.api_plugin_demo.urls"
APIGW_RESOURCES_PATH = Path(__file__).resolve().parents[3] / "bkflow/apigw/management/commands/data/api-resources.yml"


def resolve_demo_view(path):
    return resolve(path, urlconf=URLCONF).func


class TestOpenPluginV4Demo:
    def setup_method(self):
        self.factory = APIRequestFactory()

    def test_apigw_resource_uses_v4_subpath_match(self):
        """测试 v4 demo 网关资源使用统一版本路径和子路径匹配。"""
        resources = yaml.safe_load(APIGW_RESOURCES_PATH.read_text())
        paths = resources["paths"]

        assert "/api_plugin_demo/v4/" in paths
        assert not any(path.startswith("/api_plugin_demo/v4/") and path != "/api_plugin_demo/v4/" for path in paths)

        resource = paths["/api_plugin_demo/v4/"]
        assert {"get", "post"} <= set(resource)
        for method in ("get", "post"):
            config = resource[method]["x-bk-apigateway-resource"]
            assert config["matchSubpath"] is True
            assert config["backend"]["path"] == "/{env.api_sub_path}api/api_plugin_demo/v4/"
            assert config["backend"]["matchSubpath"] is True

    def test_v4_urls_are_the_only_protocol_validation_entrypoints(self):
        """测试 v4 协议验证只暴露简洁版本化路径。"""
        assert resolve_demo_view("/v4/list_meta/") == v4.list_meta_api
        assert resolve_demo_view("/v4/detail_meta/") == v4.detail_meta_api
        assert resolve_demo_view("/v4/execute/") == v4.execute_api
        assert resolve_demo_view("/v4/status/") == v4.status_api
        assert resolve_demo_view("/v4/execute/demo-run-id/cancel/") == v4.cancel_api

        with pytest.raises(Resolver404):
            resolve("/open_plugin_v4/list_meta/", urlconf=URLCONF)

    def test_list_meta_returns_v4_catalog_fields(self):
        """测试 v4 示例列表返回开放插件目录所需字段。"""
        request = self.factory.get("/api/api_plugin_demo/v4/list_meta/")
        response = resolve_demo_view("/v4/list_meta/")(request)

        assert response.status_code == 200
        body = response.data
        assert body["result"] is True
        assert body["data"]["total"] == 2

        plugin_ids = {api["id"] for api in body["data"]["apis"]}
        assert plugin_ids == {"demo_polling_job", "demo_callback_job"}

        polling_plugin = next(api for api in body["data"]["apis"] if api["id"] == "demo_polling_job")
        assert polling_plugin["wrapper_version"] == "v4.0.0"
        assert polling_plugin["default_version"] == "1.0.0"
        assert polling_plugin["latest_version"] == "1.1.0"
        assert polling_plugin["versions"] == ["1.0.0", "1.1.0"]
        assert polling_plugin["meta_url_template"].endswith(
            "/api_plugin_demo/v4/detail_meta/?api_id=demo_polling_job&version={version}"
        )

    def test_detail_meta_returns_selected_version_and_schedule_config(self):
        """测试 v4 示例详情支持按业务版本返回 schema 和调度配置。"""
        request = self.factory.get(
            "/api/api_plugin_demo/v4/detail_meta/",
            {"api_id": "demo_callback_job", "version": "2.0.0"},
        )
        response = resolve_demo_view("/v4/detail_meta/")(request)

        assert response.status_code == 200
        body = response.data
        assert body["result"] is True
        detail = body["data"]
        assert detail["id"] == "demo_callback_job"
        assert detail["wrapper_version"] == "v4.0.0"
        assert detail["plugin_version"] == "2.0.0"
        assert detail["callback"] == {"enabled": True}
        assert detail["url"].endswith("/api_plugin_demo/v4/execute/")
        assert detail["outputs"][0]["key"] == "job_instance_id"

    def test_execute_accepts_context_and_returns_run_id(self):
        """测试 execute 接收 v4 payload 并返回 open_plugin_run_id。"""
        request = self.factory.post(
            "/api/api_plugin_demo/v4/execute/",
            {
                "source_key": "demo",
                "plugin_id": "demo_polling_job",
                "plugin_version": "1.1.0",
                "client_request_id": "task-1-node-node-a-attempt-1",
                "callback_url": "https://bkflow.example/callback/",
                "callback_token": "callback-token",
                "inputs": {"target_ip": "127.0.0.1"},
                "context": {"space_id": 1, "operator": "admin"},
            },
            format="json",
        )
        response = resolve_demo_view("/v4/execute/")(request)

        assert response.status_code == 200
        body = response.data
        assert body["result"] is True
        data = body["data"]
        assert data["open_plugin_run_id"] == "demo_polling_job:task-1-node-node-a-attempt-1"
        assert data["status"] == "RUNNING"
        assert data["received_context"] == {"space_id": 1, "operator": "admin"}

    def test_status_returns_outputs_for_polling_validation(self):
        """测试 status 接口返回 polling 分支可消费的 outputs。"""
        request = self.factory.get(
            "/api/api_plugin_demo/v4/status/",
            {"task_tag": "demo_polling_job:task-1-node-node-a-attempt-1", "status": "SUCCEEDED"},
        )
        response = resolve_demo_view("/v4/status/")(request)

        assert response.status_code == 200
        body = response.data
        assert body["result"] is True
        assert body["data"] == {
            "open_plugin_run_id": "demo_polling_job:task-1-node-node-a-attempt-1",
            "status": "SUCCEEDED",
            "outputs": {
                "job_instance_id": "demo-job-task-1-node-node-a-attempt-1",
                "message": "demo open plugin finished",
            },
        }
