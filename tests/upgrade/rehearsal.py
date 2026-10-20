"""Local-only upgrade probes, run in the old or new interpreter with identical storage.

Usage: python rehearsal.py seed|queue|resume|verify MANIFEST
The caller must provide an isolated settings module and start real threads workers.
"""

import datetime
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

import django
from django.conf import settings


def assert_local():
    """Refuse any database or broker outside the dedicated local rehearsal."""
    db = settings.DATABASES["default"]
    assert db["HOST"] == "127.0.0.1" and str(db["PORT"]) == "13306", db["HOST"]
    assert db["NAME"] == "bkflow_lts_engine", db["NAME"]
    broker = urlparse(settings.BROKER_URL)
    assert broker.hostname == "127.0.0.1" and broker.port == 15673
    assert settings.REDIS["host"] == "127.0.0.1" and int(settings.REDIS["port"]) == 16379
    assert settings.BKFLOW_MODULE.code == "lts"


# AppConfig.ready() may touch storage, so reject an unsafe configuration before setup.
assert_local()
django.setup()

from bamboo_engine import api  # noqa: E402
from pipeline.eri.runtime import BambooDjangoRuntime  # noqa: E402

from bkflow.task.models import (  # noqa: E402
    PeriodicTask,
    TaskFlowRelation,
    TaskInstance,
)
from bkflow.task.operations import TaskNodeOperation, TaskOperation  # noqa: E402
from bkflow.utils.pipeline import build_default_pipeline_tree  # noqa: E402


def create(name, code, values, version="legacy"):
    """Create through BKFlow snapshots and start through the normal engine API."""
    tree = build_default_pipeline_tree()
    node = next(iter(tree["activities"].values()))
    node["component"] = {
        "code": code,
        "version": version,
        "data": {key: {"value": value, "hook": False, "need_render": True} for key, value in values.items()},
    }
    return start_tree(name, tree)


def start_tree(name, tree):
    """Start a web-format BKFlow tree and retain its execution node identifiers."""
    task = TaskInstance.objects.create_instance(
        space_id=987654, name=name, pipeline_tree=tree, creator="local-rehearsal"
    )
    # Space-variable lookup is an external interface call, outside this storage/worker rehearsal.
    with patch("bkflow.task.operations.InterfaceModuleClient.get_variable", return_value={"result": True, "data": {}}):
        result = TaskOperation(task, queue="lts").start(operator="local-rehearsal")
    assert result.result, result
    return {"task_id": task.id, "root_id": task.instance_id, "node_id": next(iter(task.execution_data["activities"]))}


def state(item):
    """Read persisted state, rather than relying on worker logs."""
    runtime = BambooDjangoRuntime()
    return runtime.get_state(item["node_id"]).name


def wait_for(item, expected, seconds=45):
    """Bound the wait and include the engine error when it fails."""
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            last = state(item)
            if last == expected:
                return
        except Exception as exc:
            last = str(exc)
        time.sleep(0.25)
    raise AssertionError((item, expected, last, api.get_execution_data(BambooDjangoRuntime(), item["node_id"])))


def seed(manifest):
    """Leave callback, timer and failed tasks plus their serialized state for the next version."""
    items = {
        "callback": create("lts-callback", "pause_node", {}),
        "timer": create("lts-timer", "sleep_timer", {"bk_timing": "90", "force_check": True}),
        "retry": create(
            "lts-retry",
            "python_code",
            {"bk_python_code": "def main():\n    return 1 / 0", "bk_input_vars": {}},
            "v1.0.0",
        ),
    }
    manifest.write_text(json.dumps(items, indent=2))
    wait_for(items["callback"], "RUNNING")
    wait_for(items["timer"], "RUNNING")
    wait_for(items["retry"], "FAILED")
    # Wait until the first timer schedule has persisted its datetime/tzinfo and countdown.
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        data = api.get_execution_data(BambooDjangoRuntime(), items["timer"]["node_id"])
        outputs = data.data["outputs"] if data.result else {}
        if isinstance(outputs.get("timing_time"), datetime.datetime):
            break
        time.sleep(0.25)
    assert isinstance(outputs.get("timing_time"), datetime.datetime), data
    assert outputs["business_tz"] is not None
    periodic = PeriodicTask.objects.create_task(
        name="lts-periodic",
        template_id=987654,
        trigger_id=int(time.time()),
        cron={"minute": "17", "hour": "3", "timezone": "Asia/Shanghai"},
        config={"space_id": 987654, "tenant_id": "default"},
        creator="local-rehearsal",
        is_enabled=False,
    )
    items["periodic_id"] = periodic.id
    manifest.write_text(json.dumps(items, indent=2))
    print("SEED_OK", manifest)


def queue(manifest):
    """Publish while no worker consumes the queue; the other version must execute it."""
    items = json.loads(manifest.read_text())
    items["queued"] = create("lts-queued", "bk_display", {"bk_display_message": "queued by previous version"}, "v1.0")
    manifest.write_text(json.dumps(items, indent=2))
    print("QUEUE_OK", items["queued"])


def resume(manifest):
    """Continue an old callback and retry, and read its Python object data and beat entry."""
    items = json.loads(manifest.read_text())
    outputs = api.get_execution_data(BambooDjangoRuntime(), items["timer"]["node_id"]).data["outputs"]
    assert isinstance(outputs["timing_time"], datetime.datetime)
    assert outputs["timing_time"].tzinfo is not None and outputs["business_tz"] is not None
    periodic = PeriodicTask.objects.get(id=items["periodic_id"])
    assert periodic.celery_task.enabled is False
    assert str(periodic.celery_task.crontab.timezone) == "Asia/Shanghai"
    assert periodic.celery_task.crontab.minute == "17"
    periodic.celery_task.schedule.is_due(datetime.datetime.now(datetime.timezone.utc))
    callback = items["callback"]
    result = TaskNodeOperation(TaskInstance.objects.get(id=callback["task_id"]), callback["node_id"]).callback(
        operator="local-rehearsal",
        data={"roundtrip": "跨 Python 版本回调", "value": 42},
    )
    assert result.result, result
    retry = items["retry"]
    result = TaskNodeOperation(TaskInstance.objects.get(id=retry["task_id"]), retry["node_id"]).retry(
        operator="local-rehearsal",
        inputs={"bk_python_code": "def main():\n    return {'result': 42}", "bk_input_vars": {}},
    )
    assert result.result, result
    print("RESUME_OK", manifest)


def verify(manifest):
    """Verify each task finished in both the engine and the BKFlow task table."""
    items = json.loads(manifest.read_text())
    results = {}
    for key in ("callback", "timer", "retry", "queued"):
        item = items[key]
        wait_for(item, "FINISHED", seconds=120)
        task = TaskInstance.objects.get(id=item["task_id"])
        assert task.is_finished, (key, task.id, "engine finished but BKFlow not finished")
        results[key] = {**item, "state": state(item), "task_finished": task.is_finished}
    runtime = BambooDjangoRuntime()
    outputs = api.get_execution_data(runtime, items["callback"]["node_id"]).data["outputs"]
    assert outputs["callback_data"]["value"] == 42
    outputs = api.get_execution_data(runtime, items["retry"]["node_id"]).data["outputs"]
    assert outputs["output"] == {"result": 42}, outputs
    manifest.with_suffix(".result.json").write_text(json.dumps(results, indent=2))
    print("VERIFY_OK", json.dumps(results))


def nested_seed(manifest):
    """Stop at a callback in the first iteration of a two-iteration subcanvas."""
    tree = build_default_pipeline_tree()
    child = build_default_pipeline_tree()
    child_node = next(iter(child["activities"].values()))
    child_node["component"] = {"code": "pause_node", "version": "legacy", "data": {}}
    parent_node = next(iter(tree["activities"].values()))
    parent_node.pop("component")
    parent_node.update(
        type="SubCanvas",
        pipeline=child,
        name="lts-nested-loop",
        loop_config={"enable": True, "loop_times": 2, "retryable": True, "skippable": True},
    )
    item = start_tree("lts-nested-loop", tree)
    manifest.write_text(json.dumps(item, indent=2))
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        relation = TaskFlowRelation.objects.filter(parent_task_id=item["task_id"]).first()
        if relation:
            task = TaskInstance.objects.get(id=relation.task_id)
            child_item = {
                "task_id": task.id,
                "root_id": task.instance_id,
                "node_id": next(iter(task.execution_data["activities"])),
            }
            wait_for(child_item, "RUNNING")
            item["first_child"] = child_item
            manifest.write_text(json.dumps(item, indent=2))
            print("NESTED_SEED_OK", json.dumps(item))
            return
        time.sleep(0.25)
    raise AssertionError((item, api.get_execution_data(BambooDjangoRuntime(), item["node_id"])))


def nested_resume(manifest):
    """Resume the first child after switching and verify the next iteration and parent completion."""
    item = json.loads(manifest.read_text())
    seen = set()
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        for relation in TaskFlowRelation.objects.filter(parent_task_id=item["task_id"]):
            if relation.task_id in seen:
                continue
            task = TaskInstance.objects.get(id=relation.task_id)
            child_item = {
                "task_id": task.id,
                "root_id": task.instance_id,
                "node_id": next(iter(task.execution_data["activities"])),
            }
            wait_for(child_item, "RUNNING")
            result = TaskNodeOperation(task, child_item["node_id"]).callback(
                operator="local-rehearsal", data={"iteration": len(seen) + 1}
            )
            assert result.result, result
            seen.add(task.id)
        if len(seen) == 2:
            break
        time.sleep(0.25)
    assert len(seen) == 2, (item, seen)
    wait_for(item, "FINISHED")
    assert TaskInstance.objects.filter(id__in=seen, is_finished=True).count() == 2
    assert TaskInstance.objects.get(id=item["task_id"]).is_finished
    item["finished_children"] = sorted(seen)
    item["state"] = state(item)
    manifest.with_suffix(".result.json").write_text(json.dumps(item, indent=2))
    print("NESTED_VERIFY_OK", json.dumps(item))


def mixed(manifest):
    """Publish a batch while both versions consume the same queues."""
    items = [create("lts-mixed", "bk_display", {"bk_display_message": str(index)}, "v1.0") for index in range(20)]
    manifest.write_text(json.dumps(items, indent=2))
    for item in items:
        wait_for(item, "FINISHED")
        assert TaskInstance.objects.get(id=item["task_id"]).is_finished
    print("MIXED_BATCH_OK", len(items))


def periodic_seed(manifest):
    """Persist a due schedule for a different version's real beat and worker."""
    from django.utils import timezone

    tree = build_default_pipeline_tree()
    node = next(iter(tree["activities"].values()))
    node["component"] = {
        "code": "bk_display",
        "version": "v1.0",
        "data": {"bk_display_message": {"value": "cross-version beat", "hook": False, "need_render": True}},
    }
    name = "lts-beat-" + str(time.time_ns())
    periodic = PeriodicTask.objects.create_task(
        name=name,
        template_id=987654,
        trigger_id=int(time.time()),
        cron={"minute": "*", "hour": "*", "timezone": "Asia/Shanghai"},
        config={"space_id": 987654, "tenant_id": "default"},
        extra_info={},
        creator="local-rehearsal",
    )
    periodic.celery_task.queue = "er_execute_lts"
    periodic.celery_task.last_run_at = timezone.now() - datetime.timedelta(minutes=2)
    periodic.celery_task.save()
    manifest.write_text(json.dumps({"periodic_id": periodic.id, "name": name, "pipeline_tree": tree}, indent=2))
    print("PERIODIC_SEED_OK", periodic.id)


def periodic_verify(manifest):
    """Check the task created by beat, then disable this fixture's schedule."""
    item = json.loads(manifest.read_text())
    periodic = PeriodicTask.objects.get(id=item["periodic_id"])
    deadline = time.monotonic() + 75
    try:
        while time.monotonic() < deadline:
            tasks = TaskInstance.objects.filter(name__startswith=item["name"] + "_")
            if tasks.exists() and tasks.filter(is_finished=True).count() == tasks.count():
                break
            time.sleep(0.25)
        assert tasks.count() == 1 and tasks.get().is_finished, list(tasks.values("id", "is_finished"))
        periodic.refresh_from_db()
        assert periodic.total_run_count == 1, periodic.total_run_count
        task = tasks.get()
        result = {"periodic_id": periodic.id, "task_id": task.id, "root_id": task.instance_id}
        result["node_id"] = next(iter(task.execution_data["activities"]))
        assert state(result) == "FINISHED"
        result.update(state="FINISHED", task_finished=True, total_run_count=periodic.total_run_count)
        manifest.with_suffix(".result.json").write_text(json.dumps(result, indent=2))
        print("PERIODIC_VERIFY_OK", json.dumps(result))
    finally:
        periodic.set_enabled(False)


if __name__ == "__main__":
    phase, manifest_path = sys.argv[1:]
    {
        "seed": seed,
        "queue": queue,
        "resume": resume,
        "verify": verify,
        "nested_seed": nested_seed,
        "nested_resume": nested_resume,
        "mixed": mixed,
        "periodic_seed": periodic_seed,
        "periodic_verify": periodic_verify,
    }[phase](Path(manifest_path))
