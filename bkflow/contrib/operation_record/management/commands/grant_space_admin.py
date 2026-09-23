"""将已登录用户授权为同租户空间管理员，不授予 Django 超管身份。"""

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bkflow.space.models import Space, SpaceConfig


class Command(BaseCommand):
    def add_arguments(self, parser):
        """显式绑定用户、租户和空间。"""
        parser.add_argument("--username", required=True)
        parser.add_argument("--tenant-id", required=True)
        parser.add_argument("--space-id", type=int, required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        """先验证全部归属，再幂等追加空间管理员。"""
        User = apps.get_model("account", "User")
        tenant_id = options["tenant_id"]
        if not settings.ENABLE_MULTI_TENANT_MODE and tenant_id != "default":
            raise CommandError("Single-tenant administrators must belong to the default tenant")
        user = User.objects.select_for_update().filter(username=options["username"], is_active=True).first()
        space = Space.objects.select_for_update().filter(pk=options["space_id"], is_deleted=False).first()
        if user is None or space is None:
            raise CommandError("User and space must already exist")
        if space.tenant_id != tenant_id or (settings.ENABLE_MULTI_TENANT_MODE and user.tenant_id != tenant_id):
            raise CommandError("User and space must belong to the requested tenant")
        administrators = list(SpaceConfig.get_config(space.id, "superusers"))
        if user.username not in administrators:
            administrators.append(user.username)
            SpaceConfig.objects.batch_update(space.id, {"superusers": administrators})
        self.stdout.write(self.style.SUCCESS("Space administrator granted"))
