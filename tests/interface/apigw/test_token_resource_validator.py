from unittest.mock import patch

from bkflow.apigw.serializers.token import TokenResourceValidator


class TestTokenResourceValidator:
    @patch("bkflow.apigw.serializers.token.TaskComponentClient")
    def test_task_exists_accepts_debug_task_in_same_space(self, mock_client_cls):
        client = mock_client_cls.return_value
        client.task_list.return_value = {
            "result": True,
            "data": {"count": 0, "results": []},
            "code": "0",
            "message": "",
        }
        client.get_task_detail.return_value = {
            "result": True,
            "data": {"id": 40, "space_id": 205, "create_method": "DEBUG"},
            "code": "0",
            "message": "",
        }

        validator = TokenResourceValidator(space_id=205, resource_type="TASK", resource_id="40")

        assert validator.task_exists("40") is True

    @patch("bkflow.apigw.serializers.token.TaskComponentClient")
    def test_task_exists_rejects_task_from_other_space(self, mock_client_cls):
        mock_client_cls.return_value.get_task_detail.return_value = {
            "result": True,
            "data": {"id": 40, "space_id": 206, "create_method": "DEBUG"},
            "code": "0",
            "message": "",
        }

        validator = TokenResourceValidator(space_id=205, resource_type="TASK", resource_id="40")

        assert validator.task_exists("40") is False

    @patch("bkflow.apigw.serializers.token.TaskComponentClient")
    def test_task_exists_rejects_mismatched_task_id(self, mock_client_cls):
        mock_client_cls.return_value.get_task_detail.return_value = {
            "result": True,
            "data": {"id": 41, "space_id": 205, "create_method": "DEBUG"},
            "code": "0",
            "message": "",
        }

        validator = TokenResourceValidator(space_id=205, resource_type="TASK", resource_id="40")

        assert validator.task_exists("40") is False

    @patch("bkflow.apigw.serializers.token.TaskComponentClient")
    def test_task_exists_rejects_failed_lookup(self, mock_client_cls):
        mock_client_cls.return_value.get_task_detail.return_value = {
            "result": False,
            "data": None,
            "code": "404",
            "message": "not found",
        }

        validator = TokenResourceValidator(space_id=205, resource_type="TASK", resource_id="40")

        assert validator.task_exists("40") is False
