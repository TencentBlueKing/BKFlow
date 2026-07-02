from django.core.management.base import BaseCommand
from django.db import OperationalError, ProgrammingError

from bkflow.plugin.services.open_plugin_snapshot import OpenPluginSnapshotService
from bkflow.template.models import Template


class Command(BaseCommand):
    help = "Backfill open plugin snapshots for templates and tasks."

    def add_arguments(self, parser):
        parser.add_argument("--space-id", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **options):
        space_id = options["space_id"]
        dry_run = options["dry_run"]

        updated_templates = self._backfill_templates(space_id=space_id, dry_run=dry_run)
        updated_tasks = self._backfill_tasks(space_id=space_id, dry_run=dry_run)

        mode = "dry-run" if dry_run else "apply"
        self.stdout.write(
            "open_plugin_snapshot_backfill mode={} updated_templates={} updated_tasks={}".format(
                mode, updated_templates, updated_tasks
            )
        )

    def _backfill_templates(self, space_id=None, dry_run=False):
        qs = Template.objects.all().order_by("id")
        if space_id is not None:
            qs = qs.filter(space_id=space_id)

        updated = 0
        for template in qs.iterator():
            extra_info, changed = OpenPluginSnapshotService.backfill_extra_info(
                space_id=template.space_id,
                pipeline_tree=template.pipeline_tree,
                extra_info=template.extra_info,
                username=template.updated_by or template.creator,
                scope_type=template.scope_type,
                scope_id=template.scope_value,
            )
            if not changed:
                continue
            updated += 1
            if not dry_run:
                template.extra_info = extra_info
                template.save(update_fields=["extra_info"])
        return updated

    def _backfill_tasks(self, space_id=None, dry_run=False):
        try:
            from bkflow.task.models import TaskInstance
        except Exception as e:
            self.stdout.write("skip task backfill: {}".format(e))
            return 0

        qs = TaskInstance.objects.all().order_by("id")
        if space_id is not None:
            qs = qs.filter(space_id=space_id)

        try:
            task_iter = qs.iterator()
        except (OperationalError, ProgrammingError) as e:
            self.stdout.write("skip task backfill: {}".format(e))
            return 0

        updated = 0
        try:
            for task in task_iter:
                extra_info, changed = OpenPluginSnapshotService.backfill_extra_info(
                    space_id=task.space_id,
                    pipeline_tree=task.execution_data or task.data,
                    extra_info=task.extra_info,
                    username=task.executor or task.creator,
                    scope_type=task.scope_type,
                    scope_id=task.scope_value,
                )
                if not changed:
                    continue
                updated += 1
                if not dry_run:
                    task.extra_info = extra_info
                    task.save(update_fields=["extra_info"])
        except (OperationalError, ProgrammingError) as e:
            self.stdout.write("skip task backfill: {}".format(e))
            return 0
        return updated
