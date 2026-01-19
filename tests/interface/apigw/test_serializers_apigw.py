from unittest import mock

import pytest
from pipeline.exceptions import PipelineException
from rest_framework import serializers

from bkflow.apigw.serializers.apigw import ApigwPermissionGrantSerializer
from bkflow.apigw.serializers.task import PipelineTreeSerializer


class TestPipelineTreeSerializer:
    """测试 PipelineTreeSerializer 中的 validate_pipeline_tree 方法"""

    @mock.patch("bkflow.apigw.serializers.task.validate_web_pipeline_tree")
    @mock.patch("bkflow.apigw.serializers.task.standardize_pipeline_node_name")
    def test_validate_pipeline_tree_success(self, mock_standardize, mock_validate):
        """测试正常情况下的流程树校验"""
        pipeline_tree = {"activities": {}, "constants": {}, "outputs": []}
        serializer = PipelineTreeSerializer(data={"pipeline_tree": pipeline_tree})
        # 由于 validate_pipeline_tree 没有返回值，is_valid 会通过
        # 但这里主要测试不会抛出异常
        mock_standardize.return_value = None
        mock_validate.return_value = None
        serializer.is_valid()
        mock_standardize.assert_called_once()
        mock_validate.assert_called_once()

    @mock.patch("bkflow.apigw.serializers.task.validate_web_pipeline_tree")
    @mock.patch("bkflow.apigw.serializers.task.standardize_pipeline_node_name")
    def test_validate_pipeline_tree_exception(self, mock_standardize, mock_validate):
        """测试流程树校验抛出 PipelineException 的情况"""
        mock_standardize.return_value = None
        mock_validate.side_effect = PipelineException("流程结构无效")

        pipeline_tree = {"activities": {}, "constants": {}, "outputs": []}
        serializer = PipelineTreeSerializer(data={"pipeline_tree": pipeline_tree})

        assert not serializer.is_valid()
        assert "pipeline_tree" in serializer.errors
        assert "流程树校验失败" in str(serializer.errors["pipeline_tree"])


class TestApigwPermissionGrantSerializer:
    @mock.patch(
        "builtins.open",
        mock.mock_open(
            read_data="""
paths:
  /test/path1:
    get:
      operationId: get_resource
      x-bk-apigateway-resource:
        allowApplyPermission: true
  /test/path2:
    post:
      operationId: post_resource
      x-bk-apigateway-resource:
        allowApplyPermission: false
  /test/path3:
    put:
      operationId: put_resource
      x-bk-apigateway-resource:
        allowApplyPermission: true
"""
        ),
    )
    @mock.patch("bkflow.apigw.serializers.apigw.path")
    def test_valid_permissions(self, mock_path):
        """Test serializer with valid permissions"""
        mock_path.dirname.return_value = "/mock/dir"
        mock_path.abspath.return_value = "/mock/dir/file.py"
        mock_path.join.return_value = "/mock/dir/data/api-resources.yml"

        data = {"apps": ["app1", "app2"], "permissions": ["get_resource", "put_resource"]}

        serializer = ApigwPermissionGrantSerializer(data=data)
        assert serializer.is_valid(raise_exception=True)
        assert serializer.validated_data["permissions"] == ["get_resource", "put_resource"]

    @mock.patch(
        "builtins.open",
        mock.mock_open(
            read_data="""
paths:
  /test/path1:
    get:
      operationId: get_resource
      x-bk-apigateway-resource:
        allowApplyPermission: true
  /test/path2:
    post:
      operationId: post_resource
      x-bk-apigateway-resource:
        allowApplyPermission: false
"""
        ),
    )
    @mock.patch("bkflow.apigw.serializers.apigw.path")
    def test_invalid_permissions(self, mock_path):
        """Test serializer with invalid permissions"""
        mock_path.dirname.return_value = "/mock/dir"
        mock_path.abspath.return_value = "/mock/dir/file.py"
        mock_path.join.return_value = "/mock/dir/data/api-resources.yml"

        data = {"apps": ["app1"], "permissions": ["get_resource", "post_resource", "unknown_resource"]}

        serializer = ApigwPermissionGrantSerializer(data=data)
        with pytest.raises(serializers.ValidationError) as exc_info:
            serializer.is_valid(raise_exception=True)

        assert "exist not allowed permissions" in str(exc_info.value)

    @mock.patch(
        "builtins.open",
        mock.mock_open(
            read_data="""
paths:
  /test/path1:
    get:
      operationId: get_resource
      x-bk-apigateway-resource:
        allowApplyPermission: true
"""
        ),
    )
    @mock.patch("bkflow.apigw.serializers.apigw.path")
    def test_empty_permissions(self, mock_path):
        """Test serializer with empty permissions list"""
        mock_path.dirname.return_value = "/mock/dir"
        mock_path.abspath.return_value = "/mock/dir/file.py"
        mock_path.join.return_value = "/mock/dir/data/api-resources.yml"

        data = {"apps": ["app1"], "permissions": []}

        serializer = ApigwPermissionGrantSerializer(data=data)
        assert serializer.is_valid(raise_exception=True)
        assert serializer.validated_data["permissions"] == []

    @mock.patch(
        "builtins.open",
        mock.mock_open(
            read_data="""
paths:
  /test/path1:
    get:
      operationId: get_resource
      x-bk-apigateway-resource:
        allowApplyPermission: true
  /test/path2:
    post:
      operationId: post_resource
      x-bk-apigateway-resource:
        allowApplyPermission: true
"""
        ),
    )
    @mock.patch("bkflow.apigw.serializers.apigw.path")
    def test_all_allowed_permissions(self, mock_path):
        """Test with all permissions allowed"""
        mock_path.dirname.return_value = "/mock/dir"
        mock_path.abspath.return_value = "/mock/dir/file.py"
        mock_path.join.return_value = "/mock/dir/data/api-resources.yml"

        data = {"apps": ["app1"], "permissions": ["get_resource", "post_resource"]}

        serializer = ApigwPermissionGrantSerializer(data=data)
        assert serializer.is_valid(raise_exception=True)
