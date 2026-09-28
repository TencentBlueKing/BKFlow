"""APIGW explicit template release compatibility."""

import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from bkflow.constants import TemplateOperationSource, TemplateOperationType
from bkflow.space.configs import FlowVersioning
from bkflow.space.models import Space, SpaceConfig
from bkflow.template.models import Template, TemplateOperationRecord, TemplateSnapshot
from bkflow.template.services.release import TemplateReleaseService


class TestReleaseTemplate(TestCase):
    """Keep the historical APIGW response while routing publication through the domain service."""

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True,
        MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",),
    )
    @patch("bkflow.apigw.views.release_template.TemplateReleaseService.release", wraps=TemplateReleaseService.release)
    def test_explicit_release_uses_app_source_and_preserves_response(self, release):
        """APIGW explicit release remains an app-source operation with its existing JSON response."""
        space = Space.objects.create(name="release-apigw", app_code="test", platform_url="")
        SpaceConfig.objects.create(
            space_id=space.id,
            name=FlowVersioning.name,
            value_type="TEXT",
            text_value="true",
        )
        draft = TemplateSnapshot.objects.create(
            draft=True,
            data={"id": "tree", "activities": {}, "gateways": {}, "flows": {}, "constants": {}, "outputs": []},
            md5sum="a" * 32,
            creator="username",
            operator="username",
        )
        template = Template.objects.create(name="release", space_id=space.id, snapshot_id=draft.id)
        draft.template_id = template.id
        draft.save(update_fields=["template_id"])

        response = self.client.post(
            "/apigw/space/{}/template/{}/release_template/".format(space.id, template.id),
            data=json.dumps({"version": "1.0.0", "desc": "release"}),
            content_type="application/json",
        )
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["result"])
        self.assertEqual(body["data"]["version"], "1.0.0")
        release.assert_called_once()
        self.assertEqual(release.call_args.kwargs["source"], TemplateOperationSource.app.name)
        self.assertTrue(release.call_args.kwargs["emit_webhook"])
        self.assertEqual(
            TemplateOperationRecord.objects.get(instance_id=template.id).operate_type,
            TemplateOperationType.release.name,
        )
