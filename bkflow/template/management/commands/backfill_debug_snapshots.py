"""预览或分批回填存量调试快照，仅在 Interface 模块执行。"""

import json
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bkflow.template.debug.backfill import backfill_context
from bkflow.template.models import DebugContext


class Command(BaseCommand):
    help = "回填可核实的存量调试快照，默认只预览；不会启动任务或修改当前节点状态。"

    def add_arguments(self, parser):
        """显式限定处理范围，支持分页续跑和预览。"""
        parser.add_argument("--space-id", type=int, action="append", help="空间 ID，可重复传入")
        parser.add_argument("--template-id", type=int, action="append", help="模板 ID，可重复传入")
        parser.add_argument("--all", action="store_true", help="扫描全部调试上下文")
        parser.add_argument("--batch-size", type=int, default=100, help="每批读取的上下文数，1 至 1000")
        parser.add_argument("--limit", type=int, default=1000, help="本次最多扫描的上下文数")
        parser.add_argument("--after-id", type=int, default=0, help="从此 DebugContext ID 之后续跑")
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--apply", action="store_true", help="实际回填；省略时只预览")
        mode.add_argument("--dry-run", action="store_true", help="只预览（默认）")

    def handle(self, *args, **options):
        """按主键分批扫描并输出不含输入输出、节点名称或凭证的 JSON 行报告。"""
        if settings.BKFLOW_MODULE.type != "interface":
            raise CommandError("请在 Interface 模块使用对应环境的配置执行")
        if not (options["space_id"] or options["template_id"] or options["all"]):
            raise CommandError("请指定 --space-id、--template-id 或 --all")
        if options["all"] and (options["space_id"] or options["template_id"]):
            raise CommandError("--all 不能和空间或模板筛选同时使用")
        if (
            not 1 <= options["batch_size"] <= 1000
            or options["limit"] <= 0
            or options["after_id"] < 0
            or any(i <= 0 for i in (options["space_id"] or []) + (options["template_id"] or []))
        ):
            raise CommandError("筛选 ID、limit 必须为正数，after-id 非负，batch-size 为 1 至 1000")
        query = DebugContext.objects.order_by("id")
        if options["space_id"]:
            query = query.filter(space_id__in=options["space_id"])
        if options["template_id"]:
            query = query.filter(template_id__in=options["template_id"])
        upper_id = query.values_list("id", flat=True).last() or 0
        after_id, scanned = options["after_id"], 0
        counts, reasons = Counter(), Counter()
        while scanned < options["limit"]:
            rows = list(
                query.filter(id__gt=after_id, id__lte=upper_id).values("id", "space_id", "template_id")[
                    : min(options["batch_size"], options["limit"] - scanned)
                ]
            )
            if not rows:
                break
            after_id = rows[-1]["id"]
            for row in rows:
                result = backfill_context(row["id"], apply=options["apply"])
                counts[result["outcome"]] += 1
                if "reason" in result:
                    reasons[result["reason"]] += 1
                self.stdout.write(json.dumps({**row, **result}, ensure_ascii=False))
            scanned += len(rows)
        self.stdout.write(
            json.dumps(
                {
                    "mode": "apply" if options["apply"] else "dry_run",
                    "scanned": scanned,
                    "counts": dict(counts),
                    "reasons": dict(reasons),
                    "next_after_id": after_id,
                    "has_more": query.filter(id__gt=after_id, id__lte=upper_id).exists(),
                },
                ensure_ascii=False,
            )
        )
        if counts["error"]:
            raise CommandError("部分历史任务读取失败，详见 JSON 报告；失败记录未写入，可按模板重试")
