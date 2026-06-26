"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""

from bkflow.plugin.models import OpenPluginSpaceGrant


class OpenPluginGrantService:
    @classmethod
    def is_granted(cls, space_id, source_key):
        return OpenPluginSpaceGrant.objects.filter(
            space_id=space_id,
            source_key=source_key,
            enabled=True,
        ).exists()

    @classmethod
    def granted_source_keys(cls, space_id):
        return list(
            OpenPluginSpaceGrant.objects.filter(space_id=space_id, enabled=True)
            .order_by("source_key")
            .values_list("source_key", flat=True)
        )

    @classmethod
    def grant(cls, space_id, source_key, operator=""):
        grant, _ = OpenPluginSpaceGrant.objects.update_or_create(
            space_id=space_id,
            source_key=source_key,
            defaults={"enabled": True, "operator": operator},
        )
        return grant

    @classmethod
    def revoke(cls, space_id, source_key, operator=""):
        grant, _ = OpenPluginSpaceGrant.objects.update_or_create(
            space_id=space_id,
            source_key=source_key,
            defaults={"enabled": False, "operator": operator},
        )
        return grant

    @classmethod
    def backfill_existing_sources(cls):
        from bkflow.plugin.services.open_plugin_catalog import OpenPluginCatalogService

        created = 0
        for space_id, source_key in OpenPluginCatalogService.iter_configured_sources():
            _, is_created = OpenPluginSpaceGrant.objects.get_or_create(
                space_id=space_id,
                source_key=source_key,
                defaults={"enabled": True, "operator": "migration"},
            )
            created += int(is_created)
        return created
