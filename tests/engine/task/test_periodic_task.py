from unittest import TestCase

import pytest
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIRequestFactory

from bkflow.task.views import PeriodicTaskViewSet


@pytest.mark.django_db
class TestPeriodicTask(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = PeriodicTaskViewSet.as_view({"post": "create", "delete": "batch_delete"})

    def _request(self, method, path, data):
        """构造带内部调用凭证的周期任务请求。"""
        request = getattr(self.factory, method)(path, data, format="json")
        request.user = type("User", (), {"is_active": True, "is_superuser": False, "username": "admin"})()
        request.app_internal_token = settings.APP_INTERNAL_TOKEN
        return request

    def test_create_periodic_task_success(self):
        data = {
            "trigger_id": 1,
            "template_id": 1,
            "name": "test_periodic_task",
            "cron": {
                "minute": "0",
                "hour": "*",
                "day_of_week": "*",
                "day_of_month": "*",
                "month_of_year": "*",
            },
            "creator": "admin",
            "config": {},
        }
        request = self._request("post", "/task/periodic_task/", data)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"].name, "test_periodic_task")

    def test_update_task_success(self):
        data = {
            "trigger_id": 2,
            "template_id": 1,
            "name": "test_periodic_task",
            "cron": {
                "minute": "0",
                "hour": "*",
                "day_of_week": "*",
                "day_of_month": "*",
                "month_of_year": "*",
            },
            "creator": "admin",
            "config": {},
        }
        request = self._request("post", "/task/periodic_task/", data)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"].name, "test_periodic_task")

        view = PeriodicTaskViewSet.as_view({"post": "update_task"})
        data = {
            "trigger_id": 2,
            "template_id": 1,
            "name": "test_periodic_task_new",
            "cron": {
                "minute": "0",
                "hour": "*",
                "day_of_week": "*",
                "day_of_month": "*",
                "month_of_year": "*",
            },
            "creator": "admin",
            "config": {},
        }

        request = self._request("post", "/task/periodic_task/update/", data)
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["name"], "test_periodic_task_new")

    def test_batch_delete_success(self):
        data = {
            "trigger_id": 3,
            "template_id": 1,
            "name": "test_periodic_task",
            "cron": {
                "minute": "0",
                "hour": "*",
                "day_of_week": "*",
                "day_of_month": "*",
                "month_of_year": "*",
            },
            "creator": "admin",
            "config": {},
        }
        request = self._request("post", "/task/periodic_task/", data)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"].name, "test_periodic_task")

        request = self._request("delete", "/task/periodic_task/batch_delete/", {"trigger_ids": [3]})
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_periodic_task_requires_internal_permission(self):
        """普通登录用户没有内部凭证时不能创建周期任务。"""
        request = self.factory.post("/task/periodic_task/", {"trigger_id": 4}, format="json")
        request.user = type(
            "User", (), {"is_active": True, "is_authenticated": True, "is_superuser": False, "username": "user"}
        )()
        request.app_internal_token = ""

        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["result"])
        self.assertEqual(response.data["message"], "您没有执行该操作的权限。")
