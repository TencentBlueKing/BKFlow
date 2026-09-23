from django.core.management.base import BaseCommand

from bkflow.plugin.services.open_plugin_snapshot import OpenPluginSnapshotService
from bkflow.template.models import Template


class Command(BaseCommand):
    help = "Backfill open plugin snapshots for templates. Task snapshots are backfilled on Engine."

    def add_arguments(self, parser):
        parser.add_argument("--space-id", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **options):
        space_id = options["space_id"]
        dry_run = options["dry_run"]

        updated_templates = self._backfill_templates(space_id=space_id, dry_run=dry_run)

        mode = "dry-run" if dry_run else "apply"
        self.stdout.write("open_plugin_snapshot_backfill mode={} updated_templates={}".format(mode, updated_templates))

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
