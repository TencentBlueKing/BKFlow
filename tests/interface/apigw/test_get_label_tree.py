import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from bkflow.label.models import Label, TemplateLabelRelation
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
        self.assertEqual(data["count"], 3)
        self.assertEqual(len(data["data"]), 1)

        # sorted by name, offset=1 -> root 'b'
        self.assertEqual(data["data"][0]["id"], root_b.id)
        # subtree kept intact
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

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_get_label_tree_filters_by_template(self):
        space = self.create_space()

        root = Label.objects.create(
            name="root",
            creator="tester",
            updated_by="tester",
            space_id=space.id,
            label_scope=["template"],
        )
        child = Label.objects.create(
            name="child",
            creator="tester",
            updated_by="tester",
            space_id=space.id,
            parent_id=root.id,
            label_scope=["template"],
        )

        TemplateLabelRelation.objects.create(template_id=100, label_id=child.id)

        url = f"/apigw/space/{space.id}/get_label_tree/?label_scope=template&template_ids=100"
        resp = self.client.get(path=url)
        data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["result"], True)

        # only root->child branch should remain, 'other' should be pruned
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["id"], root.id)
        self.assertEqual(len(data["data"][0]["children"]), 1)
        self.assertEqual(data["data"][0]["children"][0]["id"], child.id)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_get_label_tree_filters_by_task(self):
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

        with patch("bkflow.apigw.views.get_label_tree.TaskComponentClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.task_list.return_value = {
                "result": True,
                "data": {"results": [{"id": 200, "labels": [child.id]}]},
            }

            url = f"/apigw/space/{space.id}/get_label_tree/?label_scope=task&task_ids=200"
            resp = self.client.get(path=url)
            data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["result"], True)
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["id"], root.id)
        self.assertEqual(data["data"][0]["children"][0]["id"], child.id)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_get_label_tree_filters_by_task_and_template_union(self):
        space = self.create_space()

        root_task = Label.objects.create(
            name="root_task",
            creator="tester",
            updated_by="tester",
            space_id=space.id,
            label_scope=["task"],
        )
        task_child = Label.objects.create(
            name="task_child",
            creator="tester",
            updated_by="tester",
            space_id=space.id,
            parent_id=root_task.id,
            label_scope=["task"],
        )

        root_tpl = Label.objects.create(
            name="root_tpl",
            creator="tester",
            updated_by="tester",
            space_id=space.id,
            label_scope=["template"],
        )
        tpl_child = Label.objects.create(
            name="tpl_child",
            creator="tester",
            updated_by="tester",
            space_id=space.id,
            parent_id=root_tpl.id,
            label_scope=["template"],
        )
        TemplateLabelRelation.objects.create(template_id=300, label_id=tpl_child.id)

        with patch("bkflow.apigw.views.get_label_tree.TaskComponentClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.task_list.return_value = {
                "result": True,
                "data": {"results": [{"id": 200, "labels": [task_child.id]}]},
            }

            # no label_scope -> should include both task/template labels
            url = f"/apigw/space/{space.id}/get_label_tree/?task_ids=200&template_ids=300"
            resp = self.client.get(path=url)
            data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["result"], True)

        root_ids = {node["id"] for node in data["data"]}
        self.assertEqual(root_ids, {root_task.id, root_tpl.id})
