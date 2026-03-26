from datetime import timedelta
from unittest.mock import MagicMock, PropertyMock, patch

from django.test import TestCase
from django.utils import timezone

from bkflow.statistics.collectors.task_collector import TaskStatisticsCollector
from bkflow.statistics.models import TaskflowExecutedNodeStatistics, TaskflowStatistics


class TestTaskStatisticsCollector(TestCase):
    def _make_mock_task(self, task_id=1, create_method="API"):
        mock = MagicMock()
        mock.id = task_id
        mock.instance_id = "inst_001"
        mock.template_id = 10
        mock.space_id = 100
        mock.scope_type = "project"
        mock.scope_value = "proj_1"
        mock.creator = "admin"
        mock.executor = "admin"
        mock.create_time = timezone.now()
        mock.start_time = None
        mock.finish_time = None
        mock.is_started = False
        mock.is_finished = False
        mock.is_revoked = False
        mock.create_method = create_method
        mock.trigger_method = "manual"
        mock.execution_data = {
            "activities": {
                "act1": {
                    "type": "ServiceActivity",
                    "id": "act1",
                    "name": "HTTP",
                    "component": {"code": "bk_http", "version": "v1"},
                },
            },
            "gateways": {},
        }
        return mock

    def _make_bamboo_status_tree(self, root_id="inst_001"):
        """构造 bamboo_engine.api.get_pipeline_states 的真实返回结构"""
        now = timezone.now()
        return {
            root_id: {
                "id": root_id,
                "state": "FINISHED",
                "root_id:": root_id,
                "parent_id": root_id,
                "version": "v1",
                "loop": 1,
                "retry": 0,
                "skip": False,
                "error_ignorable": False,
                "error_ignored": False,
                "created_time": now - timedelta(minutes=10),
                "started_time": now - timedelta(minutes=10),
                "archived_time": now,
                "children": {
                    "act1": {
                        "id": "act1",
                        "state": "FINISHED",
                        "root_id:": root_id,
                        "parent_id": root_id,
                        "version": "v1",
                        "loop": 1,
                        "retry": 0,
                        "skip": False,
                        "error_ignorable": False,
                        "error_ignored": False,
                        "created_time": now - timedelta(minutes=5),
                        "started_time": now - timedelta(minutes=5),
                        "archived_time": now - timedelta(minutes=2),
                        "children": {},
                    },
                },
            }
        }

    @patch("bkflow.statistics.collectors.task_collector.TaskStatisticsCollector.task", new_callable=PropertyMock)
    def test_collect_on_create(self, mock_task_prop):
        mock_task_prop.return_value = self._make_mock_task()
        collector = TaskStatisticsCollector(task_id=1)
        result = collector.collect_on_create()
        assert result is True
        assert TaskflowStatistics.objects.filter(task_id=1).exists()
        stat = TaskflowStatistics.objects.get(task_id=1)
        assert stat.final_state == "CREATED"
        assert stat.atom_total == 1

    @patch("bkflow.statistics.collectors.task_collector.TaskStatisticsCollector.task", new_callable=PropertyMock)
    def test_collect_on_create_skips_mock(self, mock_task_prop):
        mock_task_prop.return_value = self._make_mock_task(create_method="MOCK")
        collector = TaskStatisticsCollector(task_id=1)
        result = collector.collect_on_create()
        assert result is False
        assert not TaskflowStatistics.objects.filter(task_id=1).exists()

    @patch("bkflow.statistics.collectors.task_collector.TaskStatisticsCollector.task", new_callable=PropertyMock)
    def test_collect_on_create_returns_false_no_task(self, mock_task_prop):
        mock_task_prop.return_value = None
        collector = TaskStatisticsCollector(task_id=999)
        result = collector.collect_on_create()
        assert result is False

    @patch("bkflow.statistics.collectors.task_collector.TaskStatisticsCollector.task", new_callable=PropertyMock)
    def test_collect_on_create_idempotent(self, mock_task_prop):
        mock_task_prop.return_value = self._make_mock_task()
        collector = TaskStatisticsCollector(task_id=1)
        collector.collect_on_create()
        collector.collect_on_create()
        assert TaskflowStatistics.objects.filter(task_id=1).count() == 1

    @patch("bkflow.statistics.collectors.task_collector.TaskStatisticsCollector.task", new_callable=PropertyMock)
    def test_update_task_statistics_finished(self, mock_task_prop):
        mock_task = self._make_mock_task()
        mock_task_prop.return_value = mock_task
        collector = TaskStatisticsCollector(task_id=1)
        collector.collect_on_create()

        now = timezone.now()
        mock_task.is_started = True
        mock_task.is_finished = True
        mock_task.is_revoked = False
        mock_task.start_time = now
        mock_task.finish_time = now
        collector._update_task_statistics()

        stat = TaskflowStatistics.objects.get(task_id=1)
        assert stat.final_state == "FINISHED"
        assert stat.is_finished is True

    @patch("bkflow.statistics.collectors.task_collector.TaskStatisticsCollector.task", new_callable=PropertyMock)
    def test_update_task_statistics_revoked(self, mock_task_prop):
        mock_task = self._make_mock_task()
        mock_task_prop.return_value = mock_task
        collector = TaskStatisticsCollector(task_id=1)
        collector.collect_on_create()

        mock_task.is_started = True
        mock_task.is_finished = False
        mock_task.is_revoked = True
        mock_task.start_time = timezone.now()
        mock_task.finish_time = timezone.now()
        collector._update_task_statistics()

        stat = TaskflowStatistics.objects.get(task_id=1)
        assert stat.final_state == "REVOKED"

    @patch("bkflow.statistics.collectors.task_collector.TaskStatisticsCollector.task", new_callable=PropertyMock)
    def test_extract_executed_nodes_with_bamboo_status_tree(self, mock_task_prop):
        """验证 _extract_executed_nodes 能正确解析 get_pipeline_states 的返回结构

        get_pipeline_states 返回 {root_id: {children: {...}}}，顶层 key 是 root_id。
        _collect_node_statistics 需要先解包到根节点层级，再传给 _extract_executed_nodes。
        """
        mock_task_prop.return_value = self._make_mock_task()
        collector = TaskStatisticsCollector(task_id=1)

        status_tree = self._make_bamboo_status_tree(root_id="inst_001")
        pipeline_tree = collector.task.execution_data

        # 模拟当前 bug：直接把 get_pipeline_states 的返回传给 _extract_executed_nodes
        nodes = collector._extract_executed_nodes(pipeline_tree, status_tree)
        assert len(nodes) == 0, "Bug: top-level key is root_id, not 'children', so nothing matches"

        # 正确用法：先解包到根节点
        root_data = status_tree.get("inst_001", {})
        nodes = collector._extract_executed_nodes(pipeline_tree, root_data)
        assert len(nodes) == 1, f"After unwrapping, should find 1 node, got {len(nodes)}"
        assert nodes[0].component_code == "bk_http"

    @patch("bamboo_engine.api.get_pipeline_states")
    @patch("pipeline.eri.runtime.BambooDjangoRuntime")
    @patch("bkflow.statistics.collectors.task_collector.TaskStatisticsCollector.task", new_callable=PropertyMock)
    def test_collect_node_statistics_end_to_end(self, mock_task_prop, mock_runtime_cls, mock_get_states):
        """端到端验证 _collect_node_statistics 能写入 TaskflowExecutedNodeStatistics"""
        mock_task = self._make_mock_task()
        mock_task.is_finished = True
        mock_task_prop.return_value = mock_task

        status_tree = self._make_bamboo_status_tree(root_id="inst_001")
        mock_result = MagicMock()
        mock_result.result = True
        mock_result.data = status_tree
        mock_get_states.return_value = mock_result

        collector = TaskStatisticsCollector(task_id=1)
        collector._collect_node_statistics()

        node_stats = TaskflowExecutedNodeStatistics.objects.filter(task_id=1)
        assert node_stats.count() == 1, f"Expected 1 node stat, got {node_stats.count()}"
        node = node_stats.first()
        assert node.component_code == "bk_http"
        assert node.node_id == "act1"
        assert node.status is True

    @patch("bkflow.statistics.collectors.task_collector.TaskStatisticsCollector.task", new_callable=PropertyMock)
    def test_create_node_statistics_time_fields(self, mock_task_prop):
        """验证 _create_node_statistics 正确映射 bamboo_engine 的时间字段名

        bamboo_engine 返回 started_time/archived_time，不是 start_time/finish_time。
        """
        mock_task_prop.return_value = self._make_mock_task()
        collector = TaskStatisticsCollector(task_id=1)

        now = timezone.now()
        started = now - timedelta(minutes=5)
        archived = now - timedelta(minutes=2)

        activity = {
            "type": "ServiceActivity",
            "id": "act1",
            "component": {"code": "bk_http", "version": "v1"},
        }
        status = {
            "state": "FINISHED",
            "started_time": started,
            "archived_time": archived,
            "retry": 0,
            "skip": False,
        }

        node = collector._create_node_statistics(activity, status, [], False)
        assert node is not None
        assert node.started_time == started, f"started_time mismatch: expected {started}, got {node.started_time}"
        assert node.archived_time == archived, f"archived_time mismatch: expected {archived}, got {node.archived_time}"
        assert node.elapsed_time == 180, f"elapsed_time should be 180s, got {node.elapsed_time}"
