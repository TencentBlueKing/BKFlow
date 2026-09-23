"""用本地命令替身检查发布步骤，不初始化应用或连接数据库。"""

import os
import subprocess
from pathlib import Path

import pytest


def run_release(tmp_path, failed_step="", module="default", cache_table_exists=False):
    executable = tmp_path / "python"
    executable.write_text(
        "#!/bin/bash\n"
        'echo "$2" >> "$STEP_LOG"\n'
        'if [ "$2" = "createcachetable" ] && [ "$CACHE_TABLE_EXISTS" = "1" ]; then\n'
        "  echo \"Cache table 'django_cache' already exists.\" >&2\n"
        "  exit 1\n"
        "fi\n"
        'if [ "$2" = "$FAILED_STEP" ]; then exit 19; fi\n'
    )
    executable.chmod(0o755)
    log = tmp_path / "steps.log"
    result = subprocess.run(
        ["bash", str(Path(__file__).resolve().parents[2] / "bin/pre_release.sh")],
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "STEP_LOG": str(log),
            "FAILED_STEP": failed_step,
            "BKPAAS_APP_MODULE_NAME": module,
            "CACHE_TABLE_EXISTS": "1" if cache_table_exists else "",
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result, log.read_text().splitlines()


@pytest.mark.parametrize(
    "step",
    [
        "migrate",
        "createcachetable",
        "update_component_models",
        "update_variable_models",
        "sync_superuser",
        "sync_saas_apigw",
        "sync_default_module",
        "sync_webhook_events",
    ],
)
def test_required_release_failure_stops_immediately(tmp_path, step):
    """迁移或必需初始化失败时，后续成功不得掩盖失败。"""
    result, steps = run_release(tmp_path, step)
    assert result.returncode == 19
    assert steps[-1] == step


@pytest.mark.parametrize("module", ["default", "default-engine"])
def test_existing_cache_table_does_not_stop_release(tmp_path, module):
    """现网 django_cache 已存在时，跳过建表并继续后续发布步骤。"""
    result, steps = run_release(tmp_path, module=module, cache_table_exists=True)
    assert result.returncode == 0
    assert "django_cache already exists, skip createcachetable" in result.stderr
    assert steps[0] == "migrate"
    assert steps[1] == "createcachetable"
    assert "update_component_models" in steps


@pytest.mark.parametrize("module", ["default", "default-engine"])
def test_release_success_and_optional_notice_compatibility(tmp_path, module):
    """正常发布保持原有顺序，通知注册失败仍可继续且输出提示。"""
    result, steps = run_release(tmp_path, "register_bkflow_to_bknotice", module)
    assert result.returncode == 0
    expected = ["migrate", "createcachetable", "update_component_models", "update_variable_models", "sync_superuser"]
    if module == "default":
        expected += ["sync_saas_apigw", "sync_default_module", "register_bkflow_to_bknotice", "sync_webhook_events"]
        assert "optional notice registration failed" in result.stderr
    assert steps == expected
