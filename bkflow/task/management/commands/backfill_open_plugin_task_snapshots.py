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

from django.core.management.base import BaseCommand, CommandError

from bkflow.contrib.api.collections.interface import InterfaceModuleClient
from bkflow.plugin.services.open_plugin_detect import has_open_plugin_nodes
from bkflow.task.models import TaskInstance
from bkflow.task.open_plugin_snapshots import (
    build_engine_snapshot_request,
    has_complete_open_plugin_snapshots,
    merge_snapshot_response,
)


class Command(BaseCommand):
    help = "Backfill open plugin snapshots for Engine TaskInstance extra_info."

    def add_arguments(self, parser):
        parser.add_argument("--space-id", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true", default=False)
        parser.add_argument("--start-id", type=int, default=0)
        parser.add_argument("--batch-size", type=int, default=100)

    def handle(self, *args, **options):
        space_id = options["space_id"]
        dry_run = options["dry_run"]
        start_id = options["start_id"] or 0
        batch_size = options["batch_size"] or 100

        qs = TaskInstance.objects.filter(is_deleted=False).order_by("id")
        if space_id is not None:
            qs = qs.filter(space_id=space_id)
        if start_id:
            qs = qs.filter(id__gte=start_id)

        updated = 0
        failed = []
        processed = 0
        client = None

        for task in qs.iterator(chunk_size=batch_size):
            pipeline_tree = task.pipeline_tree or task.data
            if not has_open_plugin_nodes(pipeline_tree):
                continue
            if has_complete_open_plugin_snapshots(task.extra_info):
                continue

            processed += 1
            if client is None:
                client = InterfaceModuleClient()
            try:
                result = client.build_open_plugin_snapshots(
                    build_engine_snapshot_request(
                        space_id=task.space_id,
                        pipeline_tree=pipeline_tree,
                        extra_info=task.extra_info,
                        username=task.executor or task.creator,
                        scope_type=task.scope_type,
                        scope_id=task.scope_value,
                        mode="backfill",
                    )
                )
            except Exception as e:
                raise CommandError(str(e))

            if not result or not result.get("result"):
                failed.append((task.id, (result or {}).get("message") or "开放插件快照回填失败"))
                continue

            data = result.get("data") or {}
            if not data.get("changed"):
                continue
            if "reference_snapshot" not in data or "schema_snapshot" not in data:
                failed.append((task.id, "Interface 未返回快照字段"))
                continue
            updated += 1
            if not dry_run:
                task.refresh_from_db()
                task.extra_info = merge_snapshot_response(task.extra_info, data)
                task.save(update_fields=["extra_info"])

        mode = "dry-run" if dry_run else "apply"
        self.stdout.write(
            "open_plugin_task_snapshot_backfill mode={} updated_tasks={} processed={} failed_tasks={}".format(
                mode, updated, processed, len(failed)
            )
        )
        if failed:
            for task_id, message in failed:
                self.stderr.write("task_id={} {}".format(task_id, message))
            raise CommandError("failed_tasks={}".format(len(failed)))
