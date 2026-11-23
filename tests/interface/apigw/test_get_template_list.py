import json

from django.test import TestCase, override_settings

from bkflow.space.models import Space
from bkflow.template.models import Template, TemplateSnapshot


class TestGetTemplateList(TestCase):
    """模板列表网关接口测试。"""

    def setUp(self):
        self.space = Space.objects.create(app_code="test", platform_url="http://test.com", name="test_space")

    def create_template(self, name, creator, updated_by):
        snapshot = TemplateSnapshot.create_snapshot(pipeline_tree={}, username=creator, version="1.0.0")
        template = Template.objects.create(
            name=name,
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator=creator,
            updated_by=updated_by,
        )
        snapshot.template_id = template.id
        snapshot.save(update_fields=["template_id"])
        return template

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_get_template_list_filters_users_by_substring(self):
        """创建人和更新人搜索使用包含匹配，并与名称条件取交集。"""
        expected = self.create_template("数据库故障诊断", "alice", "ops_admin")
        self.create_template("数据库故障诊断", "bob", "ops_admin")
        self.create_template("数据库故障诊断", "alice", "other")

        response = self.client.get(
            "/apigw/space/{}/get_template_list/?name=%E6%95%B0%E6%8D%AE%E5%BA%93&creator=lic&updated_by=admin".format(
                self.space.id
            )
        )

        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["result"])
        self.assertEqual(data["count"], 1)
        self.assertEqual([item["id"] for item in data["data"]], [expected.id])
