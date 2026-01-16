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

import logging
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from bkflow.statistics.conf import StatisticsConfig

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfill statistics data from existing templates and tasks"

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            choices=["template", "task", "summary", "all"],
            default="all",
            help="Type of data to backfill",
        )
        parser.add_argument(
            "--space-id",
            type=int,
            help="Limit to specific space ID",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Number of days to backfill for tasks (default: 30)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Batch size for processing (default: 100)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only show what would be done without making changes",
        )

    def handle(self, *args, **options):
        if not StatisticsConfig.is_enabled():
            self.stderr.write(self.style.ERROR("Statistics is disabled. Set STATISTICS_ENABLED=true to enable."))
            return

        backfill_type = options["type"]
        space_id = options.get("space_id")
        days = options["days"]
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))

        if backfill_type in ("template", "all"):
            self._backfill_templates(space_id, batch_size, dry_run)

        if backfill_type in ("task", "all"):
            self._backfill_tasks(space_id, days, batch_size, dry_run)

        if backfill_type in ("summary", "all"):
            self._backfill_summaries(space_id, days, dry_run)

        self.stdout.write(self.style.SUCCESS("Backfill completed"))

    def _backfill_templates(self, space_id, batch_size, dry_run):
        """回填模板统计数据"""
        self.stdout.write("Backfilling template statistics...")

        try:
            from bkflow.statistics.collectors import TemplateStatisticsCollector
            from bkflow.template.models import Template

            queryset = Template.objects.all()
            if space_id:
                queryset = queryset.filter(space_id=space_id)

            total = queryset.count()
            self.stdout.write(f"Found {total} templates to process")

            if dry_run:
                return

            success = 0
            failed = 0

            for template in queryset.iterator():
                try:
                    collector = TemplateStatisticsCollector(template_id=template.id)
                    if collector.collect():
                        success += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.exception(f"Failed to collect template {template.id}: {e}")
                    failed += 1

                if (success + failed) % batch_size == 0:
                    self.stdout.write(f"Processed {success + failed}/{total} templates...")

            self.stdout.write(self.style.SUCCESS(f"Templates: {success} success, {failed} failed"))

        except ImportError:
            self.stderr.write(self.style.WARNING("Template model not available"))

    def _backfill_tasks(self, space_id, days, batch_size, dry_run):
        """回填任务统计数据"""
        self.stdout.write(f"Backfilling task statistics (last {days} days)...")

        try:
            from django.utils import timezone

            from bkflow.statistics.collectors import TaskStatisticsCollector
            from bkflow.task.models import TaskInstance

            start_date = timezone.now() - timedelta(days=days)

            queryset = TaskInstance.objects.filter(create_time__gte=start_date)
            if space_id:
                queryset = queryset.filter(space_id=space_id)

            total = queryset.count()
            self.stdout.write(f"Found {total} tasks to process")

            if dry_run:
                return

            success = 0
            failed = 0

            for task in queryset.iterator():
                try:
                    collector = TaskStatisticsCollector(task_id=task.id)
                    if collector.collect_on_create():
                        success += 1
                        # 如果任务已完成，也采集归档统计
                        if task.is_finished or task.is_revoked:
                            collector.collect_on_archive()
                    else:
                        failed += 1
                except Exception as e:
                    logger.exception(f"Failed to collect task {task.id}: {e}")
                    failed += 1

                if (success + failed) % batch_size == 0:
                    self.stdout.write(f"Processed {success + failed}/{total} tasks...")

            self.stdout.write(self.style.SUCCESS(f"Tasks: {success} success, {failed} failed"))

        except ImportError:
            self.stderr.write(self.style.WARNING("TaskInstance model not available"))

    def _backfill_summaries(self, space_id, days, dry_run):
        """回填汇总统计数据"""
        self.stdout.write(f"Backfilling summary statistics (last {days} days)...")

        if dry_run:
            self.stdout.write(f"Would generate daily summaries for {days} days")
            return

        from bkflow.statistics.tasks.summary_tasks import (
            _generate_daily_summary,
            _generate_plugin_summary,
        )

        for i in range(days):
            summary_date = date.today() - timedelta(days=i + 1)
            try:
                _generate_daily_summary(summary_date)
                _generate_plugin_summary("day", summary_date)
                self.stdout.write(f"Generated summary for {summary_date}")
            except Exception as e:
                logger.exception(f"Failed to generate summary for {summary_date}: {e}")

        self.stdout.write(self.style.SUCCESS(f"Generated summaries for {days} days"))
