from pathlib import Path
import re


ROOT = Path("prototypes")
TASK_DETAIL = ROOT / "masters" / "task-detail"
STATES = TASK_DETAIL / "states"
ASSETS = ROOT / "assets"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_section(html: str, section_id: str) -> str:
    match = re.search(
        rf'<section[^>]*id="{re.escape(section_id)}"[^>]*>(.*?)</section>',
        html,
        re.DOTALL,
    )
    assert match, section_id
    return match.group(1)


def test_task_detail_master_files_exist():
    required = [
        TASK_DETAIL / "README.md",
        TASK_DETAIL / "template.html",
        STATES / "complete.html",
        STATES / "failed.html",
        STATES / "empty-log.html",
    ]

    for path in required:
        assert path.is_file(), path


def test_task_detail_readme_describes_execution_audit_surface_and_flow_editor_boundary():
    text = read_text(TASK_DETAIL / "README.md")

    for token in [
        "execution detail route",
        "read-only execution canvas",
        "single-click node detail opening",
        "configuration snapshot captured at execution time",
        "distinct from `flow-editor/`",
        "no save / publish / debug header actions",
    ]:
        assert token in text


def test_task_detail_template_covers_execution_header_backlink_read_only_canvas_and_observation_tabs():
    template = read_text(TASK_DETAIL / "template.html")

    for token in [
        "任务执行",
        "audit-deep-dive-20260420_调试任务_20260420203821",
        "完成",
        "/template/view/2166/",
        "源模板",
        "执行画布",
        "只读观察",
        "节点详情",
        "执行记录",
        "配置快照",
        "操作历史",
        "调用日志",
        "开始节点 / 消息展示 / 结束节点",
        "异常信息",
        "执行信息",
        "输入参数",
        "输出参数",
        "标准插件",
        "插件版本",
        "节点名称",
        "失败处理",
        "暂无数据",
        "pipeline trace",
        "line-numbers",
        'data-node-select="task-detail-main"',
        'data-node-open="#task-detail-panel"',
        'data-node-detail-source="',
        'data-detail-source-group="task-detail-panel"',
        'data-detail-source-id="',
        'data-tab-group="task-detail-panel"',
        'data-tab-target="task-detail-records"',
        'data-tab-target="task-detail-snapshot"',
        'data-tab-target="task-detail-history"',
        'data-tab-target="task-detail-call-log"',
    ]:
        assert token in template

    for forbidden in [
        ">保存</button>",
        ">发布</button>",
        ">调试</button>",
        "节点悬浮工具条",
        "data-dblopen",
        ">复制</button>",
        ">连线</button>",
        ">删除</button>",
    ]:
        assert forbidden not in template

    node_sources = set(re.findall(r'data-node-detail-source="([^"]+)"', template))
    panel_sources = set(re.findall(r'data-detail-source-id="([^"]+)"', template))

    assert len(node_sources) >= 2
    assert node_sources == panel_sources
    assert 'data-node-status="未执行"' in template
    assert "bk-task-status is-neutral" in template

    records_panel = extract_section(template, "task-detail-records")
    call_log_panel = extract_section(template, "task-detail-call-log")

    assert "bk-log-viewer" not in records_panel
    assert "bk-log-viewer" in call_log_panel


def test_task_detail_state_pages_cover_complete_failed_and_empty_log_audit_semantics():
    complete = read_text(STATES / "complete.html")
    failed = read_text(STATES / "failed.html")
    empty_log = read_text(STATES / "empty-log.html")

    for token in [
        "完成",
        "bk-task-status is-success",
        "暂无异常",
        "调用日志",
    ]:
        assert token in complete

    complete_records = extract_section(complete, "task-detail-records")
    complete_call_log = extract_section(complete, "task-detail-call-log")
    assert "bk-log-viewer" not in complete_records
    assert "bk-log-viewer" in complete_call_log

    for token in [
        "失败",
        "bk-task-status is-failed",
        "异常信息",
        "Traceback",
        "ValueError",
        "失败原因",
        "调用日志",
    ]:
        assert token in failed

    failed_records = extract_section(failed, "task-detail-records")
    failed_call_log = extract_section(failed, "task-detail-call-log")
    assert "bk-log-viewer" not in failed_records
    assert "bk-log-viewer" in failed_call_log

    for token in [
        "调用日志",
        "暂无调用日志",
        "日志查看器",
        "bk-log-empty",
    ]:
        assert token in empty_log


def test_shared_assets_expose_minimal_task_detail_hooks():
    css = read_text(ASSETS / "bkflow-prototype.css")
    js = read_text(ASSETS / "bkflow-prototype.js")

    for token in [
        ".bk-task-detail",
        ".bk-task-detail-header",
        ".bk-task-detail-panel",
        ".bk-task-status",
        ".bk-task-detail-node-trail",
        ".bk-task-detail-section",
        ".bk-log-viewer",
        ".bk-log-empty",
        ".bk-task-status.is-neutral",
    ]:
        assert token in css

    for token in [
        "data-node-open",
        "data-node-detail-source",
        "data-detail-source-group",
        "data-detail-source-id",
        "data-tab-group",
        "data-tab-target",
        "statusClassMap",
        "is-neutral",
        '[data-tab-group="',
        'panel.classList.add("is-open")',
        "hidden = panel.id !== targetId",
    ]:
        assert token in js
