from unittest import mock

import pytest
from rest_framework import serializers

from bkflow.apigw.serializers.apigw import ApigwPermissionGrantSerializer


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
