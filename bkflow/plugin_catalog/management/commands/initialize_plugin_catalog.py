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

from bkflow.plugin_catalog.services.migration_service import PluginCatalogMigrationService
from bkflow.space.models import Space


class Command(BaseCommand):
    help = (
        "预览/执行空间插件目录的存量初始化迁移。"
        "单空间失败不影响其他空间；已 ready=True 的空间重跑直接跳过。"
        "加 --backfill-references 可只补写存量流程的插件引用记录（不改目录与就绪状态）。"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--space-id",
            type=int,
            action="append",
            default=None,
            help="仅初始化指定空间，可重复传入多个（--space-id 1 --space-id 2）",
        )
        parser.add_argument("--all-spaces", action="store_true", default=False, help="初始化全部空间")
        parser.add_argument("--dry-run", action="store_true", default=False, help="只打印将要生成的条数与分类分布，不写库")
        parser.add_argument(
            "--backfill-references",
            action="store_true",
            default=False,
            help=(
                "只补写存量流程的插件引用记录（不改目录条目与就绪状态），"
                "用于已初始化空间补跑；要求空间已 ready，未就绪空间自动跳过"
            ),
        )

    def handle(self, *args, **options):
        space_ids = options["space_id"] or []
        all_spaces = options["all_spaces"]
        dry_run = options["dry_run"]
        backfill = options["backfill_references"]

        if not space_ids and not all_spaces:
            raise CommandError("必须指定 --space-id 或 --all-spaces 之一")
        if space_ids and all_spaces:
            raise CommandError("--space-id 与 --all-spaces 不能同时指定")

        if all_spaces:
            space_ids = list(Space.objects.filter(is_deleted=False).values_list("id", flat=True))
        else:
            # 允许 --space-id 重复传入，去重并保持传入顺序
            space_ids = list(dict.fromkeys(space_ids))

        mode = "dry-run" if dry_run else "apply"
        if backfill:
            mode = f"{mode}-backfill-refs"
        succeeded, failed, skipped = 0, 0, 0
        for sid in space_ids:
            try:
                if backfill:
                    result = PluginCatalogMigrationService.backfill_references(
                        space_id=sid, operator="admin", dry_run=dry_run
                    )
                else:
                    result = PluginCatalogMigrationService.initialize_space(
                        space_id=sid, operator="admin", dry_run=dry_run
                    )
            except Exception as exc:  # noqa: BLE001 单空间失败不影响其他空间继续执行
                failed += 1
                self.stderr.write(f"[{mode}] space_id={sid} FAILED: {exc}")
                continue

            if backfill:
                if result.get("skipped"):
                    skipped += 1
                    self.stdout.write(f"[{mode}] space_id={sid} SKIPPED({result.get('reason')})")
                    continue
            elif result.get("already_migrated"):
                skipped += 1
                self.stdout.write(f"[{mode}] space_id={sid} SKIPPED(already ready)")
                continue

            succeeded += 1
            self.stdout.write(f"[{mode}] space_id={sid} OK result={result}")

        self.stdout.write(
            f"initialize_plugin_catalog mode={mode} total={len(space_ids)} "
            f"succeeded={succeeded} skipped={skipped} failed={failed}"
        )
        if failed:
            # 汇总失败必须以非零码退出，便于发布流水线/巡检判定本次初始化未全部成功
            raise CommandError(
                f"{failed} 个空间初始化失败，详见上方 FAILED 行；"
                "修正后可用相同命令重跑（已成功的空间会自动跳过）"
            )
