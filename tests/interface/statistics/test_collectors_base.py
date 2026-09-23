from bkflow.statistics.collectors.base import BaseStatisticsCollector


class TestCountPipelineTreeNodes:
    def test_simple_tree(self):
        tree = {
            "activities": {
                "act1": {"type": "ServiceActivity"},
                "act2": {"type": "ServiceActivity"},
                "act3": {"type": "SubProcess", "pipeline": {"activities": {}, "gateways": {}}},
            },
            "gateways": {"gw1": {}},
        }
        atom, sub, gw = BaseStatisticsCollector.count_pipeline_tree_nodes(tree)
        assert atom == 2
        assert sub == 1
        assert gw == 1

    def test_recursive_subprocess(self):
        tree = {
            "activities": {
                "sub1": {
                    "type": "SubProcess",
                    "pipeline": {
                        "activities": {
                            "act_inner": {"type": "ServiceActivity"},
                            "sub_inner": {
                                "type": "SubProcess",
                                "pipeline": {
                                    "activities": {"deep_act": {"type": "ServiceActivity"}},
                                    "gateways": {"deep_gw": {}},
                                },
                            },
                        },
                        "gateways": {"inner_gw": {}},
                    },
                },
            },
            "gateways": {"top_gw": {}},
        }
        atom, sub, gw = BaseStatisticsCollector.count_pipeline_tree_nodes(tree)
        assert atom == 2
        assert sub == 2
        assert gw == 3

    def test_empty_tree(self):
        atom, sub, gw = BaseStatisticsCollector.count_pipeline_tree_nodes({})
        assert atom == 0
        assert sub == 0
        assert gw == 0


class TestParseDatetime:
    def test_none_input(self):
        assert BaseStatisticsCollector.parse_datetime(None) is None

    def test_empty_string(self):
        assert BaseStatisticsCollector.parse_datetime("") is None

    def test_iso_format(self):
        result = BaseStatisticsCollector.parse_datetime("2026-01-15T13:00:00+08:00")
        assert result is not None

    def test_datetime_passthrough(self):
        from django.utils import timezone

        now = timezone.now()
        assert BaseStatisticsCollector.parse_datetime(now) is now
