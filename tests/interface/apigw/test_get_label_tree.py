import json

from django.test import TestCase, override_settings

from bkflow.label.models import Label
from bkflow.space.models import Space


class TestGetLabelTree(TestCase):
    def create_space(self):
        return Space.objects.create(app_code="test", platform_url="http://test.com", name="space_tree")

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_get_label_tree_paginates_roots_only(self):
        space = self.create_space()

        root_a = Label.objects.create(
            name="a",
            creator="tester",
            updated_by="tester",
            space_id=space.id,
            label_scope=["task"],
        )
        Label.objects.create(
            name="a_child",
            creator="tester",
            updated_by="tester",
            space_id=space.id,
            parent_id=root_a.id,
            label_scope=["task"],
        )

        root_b = Label.objects.create(
            name="b",
            creator="tester",
            updated_by="tester",
            space_id=space.id,
            label_scope=["task"],
        )
        Label.objects.create(
            name="b_child",
            creator="tester",
            updated_by="tester",
            space_id=space.id,
            parent_id=root_b.id,
            label_scope=["task"],
        )

        url = f"/apigw/space/{space.id}/get_label_tree/?label_scope=task&offset=1&limit=1"
        resp = self.client.get(path=url)
        data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["result"], True)
        self.assertEqual(data["count"], 2)
        self.assertEqual(len(data["data"]), 1)

        self.assertEqual(data["data"][0]["id"], root_b.id)
        self.assertTrue(data["data"][0]["has_children"])
        self.assertEqual(len(data["data"][0]["children"]), 1)
        self.assertEqual(data["data"][0]["children"][0]["name"], "b_child")

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_get_label_tree_returns_full_tree(self):
        space = self.create_space()

        root = Label.objects.create(
            name="root",
            creator="tester",
            updated_by="tester",
            space_id=space.id,
            label_scope=["task"],
        )
        child = Label.objects.create(
            name="child",
            creator="tester",
            updated_by="tester",
            space_id=space.id,
            parent_id=root.id,
            label_scope=["task"],
        )

        url = f"/apigw/space/{space.id}/get_label_tree/?label_scope=task"
        resp = self.client.get(path=url)
        data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["result"], True)
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["id"], root.id)
        self.assertTrue(data["data"][0]["has_children"])
        self.assertEqual(data["data"][0]["children"][0]["id"], child.id)
