from unittest import TestCase

import pytest
from django.test import RequestFactory
from rest_framework import status

from bkflow.task.views import PeriodicTaskViewSet


@pytest.mark.django_db
class TestPeriodicTask(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = PeriodicTaskViewSet.as_view({"post": "create", "put": "update_task", "delete": "batch_delete"})

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
        request = self.factory.post("/tasks/", data=data, content_type="application/json")
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"].name, "test_periodic_task")

    def test_update_task_success(self):
        data = {
            "trigger_id": 1,
            "template_id": 1,
            "name": "test_periodic_task_name",
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
        request = self.factory.put("/tasks/update_task/", data=data, content_type="application/json")
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["name"], "test_periodic_task_name")

    def test_batch_delete_success(self):
        request = self.factory.delete(
            "/tasks/batch_delete/", data={"trigger_ids": [1]}, content_type="application/json"
        )
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
