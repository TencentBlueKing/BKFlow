"""Test API client"""
import importlib
import sys
import types
from unittest import mock

from bkflow.contrib.api.client import BaseComponentClient, BKComponentClient


def _import_task_component_client(monkeypatch, module_info_cls):
    """Import TaskComponentClient with a stubbed bkflow.admin.models.ModuleInfo.

    Engine test settings may not include `bkflow.admin` in INSTALLED_APPS, so importing
    the real Django model will raise at collection time.
    """

    if "bkflow.admin" not in sys.modules:
        monkeypatch.setitem(sys.modules, "bkflow.admin", types.ModuleType("bkflow.admin"))

    models_mod = types.ModuleType("bkflow.admin.models")
    models_mod.ModuleInfo = module_info_cls
    monkeypatch.setitem(sys.modules, "bkflow.admin.models", models_mod)

    sys.modules.pop("bkflow.contrib.api.collections.task", None)
    task_mod = importlib.import_module("bkflow.contrib.api.collections.task")
    return task_mod.TaskComponentClient, task_mod


class TestBKComponentClient:
    """Test BKComponentClient"""

    def test_client_initialization(self):
        """Test client initialization"""
        client = BKComponentClient(username="admin", language="zh-cn")
        assert client.username == "admin"
        assert client.language == "zh-cn"
        assert client.use_test_env is False

        # Default language
        with mock.patch("bkflow.contrib.api.client.translation.get_language", return_value="en"):
            client = BKComponentClient(username="admin")
            assert client.language == "en"

        # Default app credentials
        with mock.patch("bkflow.contrib.api.client.settings") as mock_settings:
            mock_settings.APP_CODE = "test_app"
            mock_settings.SECRET_KEY = "test_secret"
            client = BKComponentClient(username="admin")
            assert client.app_code == "test_app"
            assert client.app_secret == "test_secret"

        # Custom credentials
        client = BKComponentClient(username="admin", app_code="custom_app", app_secret="custom_secret")
        assert client.app_code == "custom_app"
        assert client.app_secret == "custom_secret"

    def test_pre_process_headers(self):
        """Test preprocessing headers"""
        # Default headers
        client = BKComponentClient(username="admin", language="zh-cn")
        headers = client._pre_process_headers(None)
        assert headers["Content-Type"] == "application/json"
        assert headers["blueking-language"] == "zh-cn"

        # Existing headers
        client = BKComponentClient(username="admin", language="en")
        headers = {"Authorization": "Bearer token"}
        result = client._pre_process_headers(headers)
        assert result["Authorization"] == "Bearer token"
        assert result["blueking-language"] == "en"

        # Test env flag
        client = BKComponentClient(username="admin", use_test_env=True)
        headers = client._pre_process_headers(None)
        assert headers["x-use-test-env"] == "1"

    @mock.patch("bkflow.contrib.api.client.settings")
    def test_pre_process_data(self, mock_settings):
        """Test preprocessing request data"""
        mock_settings.APP_CODE = "app"
        mock_settings.SECRET_KEY = "secret"

        client = BKComponentClient(username="admin")
        data = {"key": "value"}
        client._pre_process_data(data)

        assert data["bk_username"] == "admin"
        assert data["bk_app_code"] == "app"
        assert data["bk_app_secret"] == "secret"

    @mock.patch("bkflow.contrib.api.client.http.post")
    @mock.patch("bkflow.contrib.api.client.settings")
    def test_request_post(self, mock_settings, mock_http_post):
        """Test making POST request"""
        mock_settings.APP_CODE = "app"
        mock_settings.SECRET_KEY = "secret"
        mock_http_post.return_value = {"result": True}

        client = BKComponentClient(username="admin")
        data = {"param": "value"}
        result = client._request("POST", "http://api.example.com", data)

        assert result["result"] is True
        mock_http_post.assert_called_once()
        call_kwargs = mock_http_post.call_args[1]
        assert call_kwargs["data"]["bk_username"] == "admin"

    @mock.patch("bkflow.contrib.api.client.http.get")
    def test_request_get(self, mock_http_get):
        """Test making GET request"""
        mock_http_get.return_value = {"result": True}

        client = BKComponentClient(username="admin")
        result = client._request("GET", "http://api.example.com", {})

        assert result["result"] is True
        mock_http_get.assert_called_once()


class TestBaseComponentClient:
    """Test BaseComponentClient"""

    def test_base_client(self):
        """Test base client methods"""
        # Initialization
        client = BaseComponentClient(username="admin")
        assert client.username == "admin"

        # Default username
        client = BaseComponentClient()
        assert client.username == ""

        # Headers preprocessing
        headers = client._pre_process_headers(None)
        assert headers["Content-Type"] == "application/json"

        headers = {"Custom": "Header"}
        result = client._pre_process_headers(headers)
        assert result["Custom"] == "Header"

    @mock.patch("bkflow.contrib.api.client.http.post")
    def test_base_request(self, mock_http_post):
        """Test base client request"""
        mock_http_post.return_value = {"result": True}

        client = BaseComponentClient(username="test")
        result = client._request("POST", "http://api.com", {"data": "test"})

        assert result["result"] is True
        mock_http_post.assert_called_once()


class TestTaskComponentClient:
    def test_get_module_info_fallback(self, monkeypatch):
        class FakeModuleInfo:
            class DoesNotExist(Exception):
                pass

        default_module = types.SimpleNamespace(token="default_token", url="http://task.service", space_id=0)

        def _get_side_effect(**kwargs):
            if kwargs.get("space_id") == 999:
                raise FakeModuleInfo.DoesNotExist
            if kwargs.get("space_id") == 0:
                return default_module
            raise AssertionError(f"unexpected kwargs: {kwargs}")

        FakeModuleInfo.objects = mock.Mock()
        FakeModuleInfo.objects.get.side_effect = _get_side_effect

        TaskComponentClient, _ = _import_task_component_client(monkeypatch, FakeModuleInfo)
        client = TaskComponentClient(space_id=999)

        assert client.module_info is default_module
        assert FakeModuleInfo.objects.get.call_args_list == [
            mock.call(type="TASK", space_id=999),
            mock.call(type="TASK", space_id=0),
        ]

    def test_get_module_info_space_specific(self, monkeypatch):
        class FakeModuleInfo:
            class DoesNotExist(Exception):
                pass

        space_module = types.SimpleNamespace(token="space_token", url="http://task.space1", space_id=1)
        FakeModuleInfo.objects = mock.Mock()
        FakeModuleInfo.objects.get.return_value = space_module

        TaskComponentClient, _ = _import_task_component_client(monkeypatch, FakeModuleInfo)
        client = TaskComponentClient(space_id=1)

        assert client.module_info is space_module
        FakeModuleInfo.objects.get.assert_called_once_with(type="TASK", space_id=1)

    def test_pre_process_headers(self, monkeypatch):
        class FakeModuleInfo:
            class DoesNotExist(Exception):
                pass

        space_module = types.SimpleNamespace(token="space_token", url="http://task.space1", space_id=1)
        FakeModuleInfo.objects = mock.Mock()
        FakeModuleInfo.objects.get.return_value = space_module

        TaskComponentClient, task_mod = _import_task_component_client(monkeypatch, FakeModuleInfo)

        monkeypatch.setattr(task_mod.settings, "APP_INTERNAL_TOKEN_HEADER_KEY", "X-Internal-Token", raising=False)
        monkeypatch.setattr(task_mod.settings, "APP_INTERNAL_SPACE_ID_HEADER_KEY", "X-Space-Id", raising=False)
        monkeypatch.setattr(
            task_mod.settings, "APP_INTERNAL_FROM_SUPERUSER_HEADER_KEY", "X-From-Superuser", raising=False
        )

        client = TaskComponentClient(space_id=1, from_superuser=True)

        headers = client._pre_process_headers(None)
        assert headers["Content-Type"] == "application/json"
        assert headers["X-Internal-Token"] == "space_token"
        assert headers["X-Space-Id"] == "1"
        assert headers["X-From-Superuser"] == "1"

        existing = {"Authorization": "Bearer token"}
        result = client._pre_process_headers(existing)
        assert result["Authorization"] == "Bearer token"
        assert result["X-Internal-Token"] == "space_token"
        assert result["X-Space-Id"] == "1"
        assert result["X-From-Superuser"] == "1"

        # cover: space_id is None branch
        client.space_id = None
        headers = client._pre_process_headers(None)
        assert headers["X-From-Superuser"] == "1"
        assert "X-Space-Id" not in headers

        # cover: from_superuser False branch
        client.from_superuser = False
        headers = client._pre_process_headers(None)
        assert headers["X-From-Superuser"] == "0"

    def test_request_wrappers_build_url_and_method(self, monkeypatch):
        class FakeModuleInfo:
            class DoesNotExist(Exception):
                pass

        space_module = types.SimpleNamespace(token="space_token", url="http://task.space1", space_id=1)
        FakeModuleInfo.objects = mock.Mock()
        FakeModuleInfo.objects.get.return_value = space_module

        TaskComponentClient, _ = _import_task_component_client(monkeypatch, FakeModuleInfo)
        client = TaskComponentClient(space_id=1)
        client._request = mock.Mock(return_value={"result": True})

        client.task_list({"a": 1})
        client._request.assert_called_with(method="get", url="http://task.space1/task/", data={"a": 1})

        client.update_labels(2, {"label_ids": [1]})
        client._request.assert_called_with(
            method="post", url="http://task.space1/task/2/update_labels/", data={"label_ids": [1]}
        )

        client.get_task_label_ref_count(1, "1,2")
        client._request.assert_called_with(
            method="get",
            url="http://task.space1/task/get_task_label_ref_count/?space_id=1&label_ids=1,2",
            data=None,
        )

        client.delete_task_label_relation({"task_id": 1, "label_ids": [1]})
        client._request.assert_called_with(
            method="post",
            url="http://task.space1/task/delete_task_label_relation/",
            data={"task_id": 1, "label_ids": [1]},
        )

        client.create_task({"name": "t"})
        client._request.assert_called_with(method="post", url="http://task.space1/task/", data={"name": "t"})

        client.get_task_detail(3)
        client._request.assert_called_with(method="get", url="http://task.space1/task/3/", data=None)

        client.delete_task(3)
        client._request.assert_called_with(method="delete", url="http://task.space1/task/3/", data=None)

        client.get_task_states(3, {"x": 1})
        client._request.assert_called_with(method="get", url="http://task.space1/task/3/get_states/", data={"x": 1})

        client.get_task_mock_data(3)
        client._request.assert_called_with(method="get", url="http://task.space1/task/3/get_task_mock_data/", data=None)

        client.operate_task(3, "pause", {"y": 2})
        client._request.assert_called_with(method="post", url="http://task.space1/task/3/operate/pause/", data={"y": 2})

        client.get_task_node_detail(3, "node", username="admin")
        client._request.assert_called_with(
            method="get",
            url="http://task.space1/task/3/get_task_node_detail/node/?username=admin",
            data=None,
        )

        client.node_operate(3, "node", "retry", {"z": 3})
        client._request.assert_called_with(
            method="post", url="http://task.space1/task/3/node_operate/node/retry/", data={"z": 3}
        )

        client.get_task_node_log(3, "node", 1)
        client._request.assert_called_with(
            method="get", url="http://task.space1/task/3/get_task_node_log/node/1/", data=None
        )

        client.render_current_constants(3)
        client._request.assert_called_with(
            method="get", url="http://task.space1/task/3/render_current_constants/", data=None
        )

        client.render_context_with_node_outputs(3, {"a": 1})
        client._request.assert_called_with(
            method="post", url="http://task.space1/task/3/render_context_with_node_outputs/", data={"a": 1}
        )

        client.get_task_operation_record(3)
        client._request.assert_called_with(
            method="get", url="http://task.space1/task/3/get_task_operation_record/", data=None
        )

        client.get_node_snapshot_config(3)
        client._request.assert_called_with(
            method="get", url="http://task.space1/task/3/get_node_snapshot_config/", data=None
        )

        client.get_tasks_states({"task_ids": [1]})
        client._request.assert_called_with(
            method="post", url="http://task.space1/task/get_tasks_states/", data={"task_ids": [1]}
        )

        client.trigger_engine_admin_action("inst", "pause")
        client._request.assert_called_with(
            method="post",
            url="http://task.space1/task_engine_admin/api/v1/bamboo_engine/pause/inst/",
            data=None,
        )

        client.batch_delete_tasks({"task_ids": [1]})
        client._request.assert_called_with(
            method="post", url="http://task.space1/task/batch_delete_tasks/", data={"task_ids": [1]}
        )

        client.create_periodic_task({"name": "p"})
        client._request.assert_called_with(
            method="post", url="http://task.space1/task/periodic_task/", data={"name": "p"}
        )

        client.update_periodic_task({"id": 1})
        client._request.assert_called_with(
            method="post", url="http://task.space1/task/periodic_task/update/", data={"id": 1}
        )

        client.batch_delete_periodic_task({"ids": [1]})
        client._request.assert_called_with(
            method="post", url="http://task.space1/task/periodic_task/batch_delete/", data={"ids": [1]}
        )

        client.get_engine_config({"a": 1})
        client._request.assert_called_with(
            method="get", url="http://task.space1/task/get_engine_config/", data={"a": 1}
        )

        client.upsert_engine_config({"a": 1})
        client._request.assert_called_with(
            method="post", url="http://task.space1/task/upsert_engine_config/", data={"a": 1}
        )

        client.delete_engine_config({"a": 1})
        client._request.assert_called_with(
            method="delete", url="http://task.space1/task/delete_engine_config/", data={"a": 1}
        )
