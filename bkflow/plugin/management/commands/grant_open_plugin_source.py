from django.core.management.base import BaseCommand

from bkflow.plugin.services.open_plugin_grant import OpenPluginGrantService


class Command(BaseCommand):
    help = "Grant or revoke open plugin source access for spaces."

    def add_arguments(self, parser):
        parser.add_argument("--space-id", dest="space_ids", type=int, action="append", required=True)
        parser.add_argument("--source-key", required=True)
        parser.add_argument("--operator", default="")
        parser.add_argument("--revoke", action="store_true", default=False)

    def handle(self, *args, **options):
        source_key = options["source_key"]
        operator = options["operator"]
        space_ids = options["space_ids"]
        revoke = options["revoke"]

        for space_id in space_ids:
            if revoke:
                OpenPluginGrantService.revoke(space_id=space_id, source_key=source_key, operator=operator)
            else:
                OpenPluginGrantService.grant(space_id=space_id, source_key=source_key, operator=operator)

        if revoke:
            self.stdout.write("open_plugin_source_grant source_key={} revoked={}".format(source_key, len(space_ids)))
            return
        self.stdout.write("open_plugin_source_grant source_key={} granted={}".format(source_key, len(space_ids)))
