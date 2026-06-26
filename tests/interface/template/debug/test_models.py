import pytest

from bkflow.template.models import DebugContext, DebugNodeState


@pytest.mark.django_db
class TestDebugModels:
    """DebugContext / DebugNodeState 基本约束"""

    def test_create_context_defaults(self):
        ctx = DebugContext.objects.create(template_id=1, space_id=10)
        assert ctx.status == "idle"
        assert ctx.global_vars == {}
        assert ctx.last_inputs == {}
        assert ctx.locked_by == ""

    def test_template_id_unique(self):
        DebugContext.objects.create(template_id=1, space_id=10)
        with pytest.raises(Exception):
            DebugContext.objects.create(template_id=1, space_id=10)

    def test_node_state_defaults_and_unique(self):
        ctx = DebugContext.objects.create(template_id=2, space_id=10)
        ns = DebugNodeState.objects.create(debug_context=ctx, node_id="n1")
        assert ns.execution_mode == "real"
        assert ns.mock_result == "success"
        assert ns.status == "not_run"
        with pytest.raises(Exception):
            DebugNodeState.objects.create(debug_context=ctx, node_id="n1")
