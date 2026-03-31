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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from django.core.management.base import BaseCommand

logger = logging.getLogger("celery")


class Command(BaseCommand):
    help = "回填统计数据"

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            type=str,
            default="all",
            choices=["all", "template", "task", "summary"],
            help="回填类型: all/template/task/summary",
        )
        parser.add_argument(
            "--space-id",
            type=int,
            default=None,
            help="指定空间 ID（可选）",
        )
        parser.add_argument(
            "--date-start",
            type=str,
            default=None,
            help="汇总回填开始日期 (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--date-end",
            type=str,
            default=None,
            help="汇总回填结束日期 (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="每批处理数量",
        )
        parser.add_argument(
            "--parallel",
            action="store_true",
            help="使用 Celery 异步执行",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=1,
            help="本地并发线程数（不依赖 Celery，默认 1 即串行）",
        )

    def handle(self, *args, **options):
        backfill_type = options["type"]
        space_id = options.get("space_id")
        batch_size = options.get("batch_size", 100)
        use_parallel = options.get("parallel", False)
        workers = options.get("workers", 1)

        self.stdout.write(
            f"Starting backfill: type={backfill_type}, space_id={space_id}, batch_size={batch_size}, workers={workers}"
        )

        if backfill_type in ("all", "template"):
            self._backfill_templates(space_id, batch_size, use_parallel, workers)

        if backfill_type in ("all", "task"):
            self._backfill_tasks(space_id, batch_size, use_parallel, workers)

        if backfill_type in ("all", "summary"):
            date_start = options.get("date_start")
            date_end = options.get("date_end")
            self._backfill_summaries(date_start, date_end)

        self.stdout.write(self.style.SUCCESS("Backfill completed."))

    def _backfill_templates(self, space_id, batch_size, use_parallel, workers=1):
        try:
            from bkflow.template.models import Template
        except ImportError:
            self.stdout.write(self.style.WARNING("Template model not available, skipping template backfill"))
            return

        qs = Template.objects.all()
        if space_id:
            qs = qs.filter(space_id=space_id)

        total = qs.count()
        self.stdout.write(f"Backfilling {total} templates...")

        if use_parallel:
            self._backfill_templates_celery(qs, batch_size, total)
        elif workers > 1:
            self._backfill_templates_threaded(qs, batch_size, total, workers)
        else:
            self._backfill_templates_serial(qs, batch_size, total)

    def _backfill_single_template(self, template_id, snapshot_id):
        from bkflow.statistics.collectors import TemplateStatisticsCollector

        collector = TemplateStatisticsCollector(template_id=template_id, snapshot_id=snapshot_id)
        collector.collect()

    def _backfill_templates_serial(self, qs, batch_size, total):
        processed = 0
        for template in qs.iterator(chunk_size=batch_size):
            try:
                self._backfill_single_template(template.id, template.snapshot_id)
                processed += 1
                if processed % batch_size == 0:
                    self.stdout.write(f"  Templates processed: {processed}/{total}")
            except Exception as e:
                self.stderr.write(f"  Error processing template {template.id}: {e}")
        self.stdout.write(self.style.SUCCESS(f"  Templates backfill done: {processed}/{total}"))

    def _backfill_templates_celery(self, qs, batch_size, total):
        from bkflow.statistics.tasks import template_post_save_statistics_task

        processed = 0
        for template in qs.iterator(chunk_size=batch_size):
            try:
                template_post_save_statistics_task.delay(
                    template_id=template.id, old_snapshot_id=None, new_snapshot_id=template.snapshot_id
                )
                processed += 1
                if processed % batch_size == 0:
                    self.stdout.write(f"  Templates dispatched: {processed}/{total}")
            except Exception as e:
                self.stderr.write(f"  Error dispatching template {template.id}: {e}")
        self.stdout.write(self.style.SUCCESS(f"  Templates dispatched: {processed}/{total}"))

    def _backfill_templates_threaded(self, qs, batch_size, total, workers):
        processed = 0
        errors = 0
        template_ids = list(qs.values_list("id", "snapshot_id"))

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(self._backfill_single_template, tid, sid): tid for tid, sid in template_ids}
            for future in as_completed(futures):
                tid = futures[future]
                try:
                    future.result()
                    processed += 1
                    if processed % batch_size == 0:
                        self.stdout.write(f"  Templates processed: {processed}/{total}")
                except Exception as e:
                    errors += 1
                    self.stderr.write(f"  Error processing template {tid}: {e}")

        self.stdout.write(self.style.SUCCESS(f"  Templates backfill done: {processed}/{total}, errors: {errors}"))

    def _backfill_tasks(self, space_id, batch_size, use_parallel, workers=1):
        try:
            from bkflow.task.models import TaskInstance
        except ImportError:
            self.stdout.write(self.style.WARNING("TaskInstance model not available, skipping task backfill"))
            return

        qs = TaskInstance.objects.all()
        if space_id:
            qs = qs.filter(space_id=space_id)

        total = qs.count()
        self.stdout.write(f"Backfilling {total} tasks...")

        if use_parallel:
            self._backfill_tasks_celery(qs, batch_size, total)
        elif workers > 1:
            self._backfill_tasks_threaded(qs, batch_size, total, workers)
        else:
            self._backfill_tasks_serial(qs, batch_size, total)

    def _backfill_single_task(self, task_id, is_finished, is_revoked):
        from bkflow.statistics.collectors import TaskStatisticsCollector

        collector = TaskStatisticsCollector(task_id=task_id)
        collector.collect_on_create()
        if is_finished or is_revoked:
            collector.collect_on_archive()

    def _backfill_tasks_serial(self, qs, batch_size, total):
        processed = 0
        for task in qs.iterator(chunk_size=batch_size):
            try:
                self._backfill_single_task(task.id, task.is_finished, task.is_revoked)
                processed += 1
                if processed % batch_size == 0:
                    self.stdout.write(f"  Tasks processed: {processed}/{total}")
            except Exception as e:
                self.stderr.write(f"  Error processing task {task.id}: {e}")
        self.stdout.write(self.style.SUCCESS(f"  Tasks backfill done: {processed}/{total}"))

    def _backfill_tasks_celery(self, qs, batch_size, total):
        from bkflow.statistics.tasks import task_backfill_statistics_task

        processed = 0
        for task in qs.iterator(chunk_size=batch_size):
            try:
                task_backfill_statistics_task.delay(task_id=task.id)
                processed += 1
                if processed % batch_size == 0:
                    self.stdout.write(f"  Tasks dispatched: {processed}/{total}")
            except Exception as e:
                self.stderr.write(f"  Error dispatching task {task.id}: {e}")
        self.stdout.write(self.style.SUCCESS(f"  Tasks dispatched: {processed}/{total}"))

    def _backfill_tasks_threaded(self, qs, batch_size, total, workers):
        processed = 0
        errors = 0
        task_rows = list(qs.values_list("id", "is_finished", "is_revoked"))

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(self._backfill_single_task, tid, fin, rev): tid for tid, fin, rev in task_rows}
            for future in as_completed(futures):
                tid = futures[future]
                try:
                    future.result()
                    processed += 1
                    if processed % batch_size == 0:
                        self.stdout.write(f"  Tasks processed: {processed}/{total}")
                except Exception as e:
                    errors += 1
                    self.stderr.write(f"  Error processing task {tid}: {e}")

        self.stdout.write(self.style.SUCCESS(f"  Tasks backfill done: {processed}/{total}, errors: {errors}"))

    def _backfill_summaries(self, date_start_str, date_end_str):
        from bkflow.statistics.tasks.summary_tasks import (
            _generate_daily_summary,
            _generate_plugin_summary,
        )

        if date_start_str:
            start = date.fromisoformat(date_start_str)
        else:
            start = date.today() - timedelta(days=30)

        if date_end_str:
            end = date.fromisoformat(date_end_str)
        else:
            end = date.today() - timedelta(days=1)

        self.stdout.write(f"Backfilling summaries from {start} to {end}...")

        current = start
        while current <= end:
            try:
                _generate_daily_summary(current)
                _generate_plugin_summary("day", current)
                self.stdout.write(f"  Summary generated for {current}")
            except Exception as e:
                self.stderr.write(f"  Error generating summary for {current}: {e}")
            current += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS("  Summaries backfill done"))
