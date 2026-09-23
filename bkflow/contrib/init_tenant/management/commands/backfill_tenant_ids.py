"""按已核实的空间归属回填租户；分别在 Interface 和每个 Engine 执行。"""

import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q


class Command(BaseCommand):
    help = "预览或回填历史空间、任务和周期配置的租户。默认只预览，不改写 Pipeline 上下文。"

    def add_arguments(self, parser):
        parser.add_argument("--mapping", required=True, help='JSON 文件，例如 {"1": "tenant-a", "2": "tenant-b"}')
        parser.add_argument("--module", required=True, choices=("interface", "engine"))
        parser.add_argument("--apply", action="store_true", help="实际执行，需先停止创建任务和周期触发")

    def handle(self, *args, **options):
        module = options["module"]
        if settings.BKFLOW_MODULE.type != module:
            raise CommandError("--module 与当前进程模块不一致，请使用对应模块的数据库配置")
        try:
            with open(options["mapping"], encoding="utf-8") as source:
                raw_mapping = json.load(source)
            if not isinstance(raw_mapping, dict) or not raw_mapping:
                raise ValueError("映射必须是非空对象")
            mapping = {}
            for space_id, tenant_id in raw_mapping.items():
                if not str(space_id).isdigit() or int(space_id) <= 0:
                    raise ValueError("空间 ID 必须为正整数")
                if not isinstance(tenant_id, str) or not tenant_id.strip() or len(tenant_id) > 32:
                    raise ValueError("租户 ID 必须为 1 至 32 位非空字符串")
                if tenant_id != tenant_id.strip() or int(space_id) in mapping:
                    raise ValueError("映射包含空白租户 ID 或重复空间 ID")
                mapping[int(space_id)] = tenant_id
        except (OSError, ValueError, TypeError) as exc:
            raise CommandError(f"无法读取租户映射: {exc}") from exc

        # 先检查全部映射，避免发现归属冲突前已修改一部分空间。
        for space_id, tenant_id in mapping.items():
            self._process_space(module, space_id, tenant_id, apply=False)
        for space_id, tenant_id in mapping.items():
            counts = self._process_space(module, space_id, tenant_id, apply=options["apply"])
            self.stdout.write(json.dumps({"space_id": space_id, "tenant_id": tenant_id, **counts}, ensure_ascii=False))
        self.stdout.write("APPLIED" if options["apply"] else "DRY RUN: 未修改数据；确认映射和停写后使用 --apply")

    def _process_space(self, module, space_id, tenant_id, apply):
        """仅修改映射中的空间；事务内复查，拒绝覆盖已有非 default 归属。"""
        with transaction.atomic():
            if module == "interface":
                from bkflow.space.models import Space

                qs = Space.objects.filter(pk=space_id)
                rows = (
                    list(qs.select_for_update().values_list("tenant_id", flat=True))
                    if apply
                    else list(qs.values_list("tenant_id", flat=True))
                )
                if not rows:
                    raise CommandError(f"空间 {space_id} 在当前 Interface 中不存在")
                if any(value not in ("default", tenant_id) for value in rows):
                    raise CommandError(f"空间 {space_id} 已有其他租户归属，拒绝覆盖")
                pending = qs.filter(tenant_id="default").exclude(tenant_id=tenant_id)
                count = pending.count()
                if apply:
                    pending.update(tenant_id=tenant_id)
                return {"spaces": count}

            from bkflow.task.models import PeriodicTask, TaskInstance

            tasks = TaskInstance.objects.filter(space_id=space_id)
            if tasks.exclude(tenant_id__in=("default", tenant_id)).exists():
                raise CommandError(f"空间 {space_id} 的任务已有其他租户归属，拒绝覆盖")
            periodic_tasks = PeriodicTask.objects.filter(
                Q(config__space_id=space_id) | Q(config__space_id=str(space_id))
            )
            if apply:
                periodic_tasks = periodic_tasks.select_for_update()
            periodic_count = 0
            for periodic_task in periodic_tasks.iterator():
                current_tenant = periodic_task.config.get("tenant_id")
                if current_tenant == tenant_id:
                    continue
                if current_tenant not in (None, "", "default"):
                    raise CommandError(f"周期任务 {periodic_task.id} 已有其他租户归属，拒绝覆盖")
                periodic_count += 1
                if apply:
                    periodic_task.config = {**periodic_task.config, "tenant_id": tenant_id}
                    periodic_task.save(update_fields=["config"])
            pending = tasks.filter(tenant_id="default").exclude(tenant_id=tenant_id)
            count = pending.count()
            if apply:
                pending.update(tenant_id=tenant_id)
            return {"tasks": count, "periodic_configs": periodic_count}
