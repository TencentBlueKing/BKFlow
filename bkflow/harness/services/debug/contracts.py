"""Bounded data contracts returned by the Harness debug adapter."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class DebugAdapterSnapshot:
    """Current DebugService facts captured before a Harness session starts."""

    debug_context_id: int
    input_schema: List[dict]
    node_readiness: List[dict]
    tree_fingerprint: Dict[str, object]


@dataclass(frozen=True)
class DebugSessionView:
    """Model-safe start result embedded in the common Harness Envelope."""

    session_id: str
    debug_context_id: int
    template_id: int
    mode: str
    status: str
    plan_hash: str
    tree_fingerprint: Dict[str, object]
    input_schema: List[dict]
    node_readiness: List[dict]

    def as_artifact_ref(self):
        """Return an isolated JSON representation for response snapshotting."""
        return {
            "type": "debug_session",
            "session_id": self.session_id,
            "debug_context_id": self.debug_context_id,
            "template_id": self.template_id,
            "mode": self.mode,
            "status": self.status,
            "plan_hash": self.plan_hash,
            "tree_fingerprint": deepcopy(self.tree_fingerprint),
            "input_schema": deepcopy(self.input_schema),
            "node_readiness": deepcopy(self.node_readiness),
        }
