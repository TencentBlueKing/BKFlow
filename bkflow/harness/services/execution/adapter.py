"""Server-side task adapter; SDK/token modes remain unavailable in P3."""

import hashlib
import math
import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass

from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.harness.safety import is_bounded_non_secret_json, safe_opaque_identifier
from bkflow.harness.services.execution.contracts import RUNTIME_AUTHORIZATION_MODE
from bkflow.harness.services.execution.postconditions import NodeOutputEvidence
from bkflow.space.models import Credential
from bkflow.task.services.task_creator import (
    TaskCreationRejected,
    TaskCreationUncertain,
    TaskCreator,
)

_CREDENTIAL_REF = re.compile(r"^credential://id/([1-9][0-9]*)$")
_ENGINE_CREDENTIAL_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")


class CreateDispatchRejected(RuntimeError):
    pass


class CreateDispatchUncertain(RuntimeError):
    pass


class StartDispatchRejected(RuntimeError):
    pass


class StartDispatchUncertain(RuntimeError):
    pass


class ReadbackUnavailable(RuntimeError):
    pass


class TaskNotFound(RuntimeError):
    pass


class ControlDispatchUncertain(RuntimeError):
    pass


class ControlActionUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class ExecutionObservation:
    """Minimal Engine projection used by the convergence service."""

    state: str
    node_outputs: dict


@dataclass(frozen=True)
class ControlObservation:
    """Bounded root and optional runtime-node facts for one control preflight."""

    task_ref: str
    root_state: str
    action: str
    template_node_id: str = None
    runtime_node_id: str = None
    node_state: str = None
    node_version: str = None
    published_node_type: str = None
    published_retryable: bool = None
    published_skippable: bool = None


@dataclass(frozen=True)
class ControlReadbackObservation:
    """Exact post-dispatch facts without raw runtime identifiers or trees."""

    root_state: str
    template_node_id: str = None
    node_state: str = None
    node_version: str = None
    runtime_mapping_fingerprint: str = None


@dataclass(frozen=True)
class ControlDispatchReceipt:
    """Safe acknowledgement DTO; downstream body and message never cross the adapter."""

    acknowledged: bool


_WIRE_STATE_MAP = {
    "CREATED": "READY",
    "READY": "READY",
    "RUNNING": "RUNNING",
    "SUSPENDED": "SUSPENDED",
    "NODE_SUSPENDED": "SUSPENDED",
    "FINISHED": "FINISHED",
    "FAILED": "FAILED",
    "REVOKED": "REVOKED",
    "EXPIRED": "EXPIRED",
}
_MAX_ENGINE_DEPTH = 8
_MAX_ENGINE_ITEMS = 1000
_MAX_ENGINE_NODES = 4000
_MAX_ENGINE_TEXT_BYTES = 64 * 1024
_OUTPUT_READABLE_NODE_STATES = frozenset({"FINISHED", "FAILED", "REVOKED"})


def runtime_mapping_fingerprint(template_node_id, runtime_node_id):
    """Bind a trusted template node to its runtime node without persisting either mapping."""
    if safe_opaque_identifier(template_node_id) is None or safe_opaque_identifier(runtime_node_id) is None:
        raise ValueError("runtime node mapping is invalid")
    return hashlib.sha256("{}\0{}".format(template_node_id, runtime_node_id).encode("utf-8")).hexdigest()


def _within_engine_budget(value):
    """Bound traversal of non-paginated Engine responses before projection."""
    state = {"nodes": 0, "wire_bytes": 0}

    def consume_wire_bytes(amount):
        state["wire_bytes"] += amount
        return state["wire_bytes"] <= _MAX_ENGINE_TEXT_BYTES

    def visit(item, depth):
        state["nodes"] += 1
        if depth > _MAX_ENGINE_DEPTH or state["nodes"] > _MAX_ENGINE_NODES:
            return False
        if item is None:
            return consume_wire_bytes(4)
        if isinstance(item, bool):
            return consume_wire_bytes(4 if item else 5)
        if isinstance(item, int):
            bits = abs(item).bit_length()
            decimal_bytes = 1 if bits == 0 else (bits * 30103) // 100000 + 1
            return consume_wire_bytes(decimal_bytes + (1 if item < 0 else 0))
        if isinstance(item, float):
            return math.isfinite(item) and consume_wire_bytes(32)
        if isinstance(item, str):
            try:
                encoded_bytes = len(item.encode("utf-8"))
            except UnicodeError:
                return False
            return consume_wire_bytes(encoded_bytes + 2)
        if isinstance(item, Mapping):
            if len(item) > _MAX_ENGINE_ITEMS or not consume_wire_bytes(2 + len(item)):
                return False
            for key, child in item.items():
                if not isinstance(key, str):
                    return False
                try:
                    key_bytes = len(key.encode("utf-8"))
                except UnicodeError:
                    return False
                if not consume_wire_bytes(key_bytes + 3) or not visit(child, depth + 1):
                    return False
            return True
        if isinstance(item, list):
            return (
                len(item) <= _MAX_ENGINE_ITEMS
                and consume_wire_bytes(2 + len(item))
                and all(visit(child, depth + 1) for child in item)
            )
        return False

    return visit(value, 0)


class ExecutionReadAdapter:
    """Read only task state and Manifest-declared outputs through real Task APIs."""

    def __init__(self, *, space_id, client_factory=None):
        self._client = (client_factory or TaskComponentClient)(space_id=space_id)

    @staticmethod
    def _declared_nodes(pipeline_tree):
        if not isinstance(pipeline_tree, dict):
            raise ValueError("published pipeline tree is invalid")
        activities = pipeline_tree.get("activities", {})
        gateways = pipeline_tree.get("gateways", {})
        if not isinstance(activities, dict) or not isinstance(gateways, dict):
            raise ValueError("published pipeline tree is invalid")
        return set(activities) | set(gateways)

    @staticmethod
    def _declared_outputs(pipeline_tree):
        """Resolve only the published component-output declarations."""
        constants = pipeline_tree.get("constants", {})
        if not isinstance(constants, dict):
            raise ValueError("published pipeline outputs are invalid")
        declared = set()
        for constant in constants.values():
            if not isinstance(constant, dict):
                raise ValueError("published pipeline outputs are invalid")
            if constant.get("source_type") != "component_outputs":
                continue
            source_info = constant.get("source_info")
            if not isinstance(source_info, dict):
                raise ValueError("published pipeline outputs are invalid")
            for node_id, output_keys in source_info.items():
                if (
                    safe_opaque_identifier(node_id) is None
                    or not isinstance(output_keys, list)
                    or not output_keys
                    or any(safe_opaque_identifier(output_key) is None for output_key in output_keys)
                ):
                    raise ValueError("published pipeline outputs are invalid")
                declared.update((node_id, output_key) for output_key in output_keys)
        return declared

    def _task_state(self, task_ref):
        try:
            response = self._client.get_task_states(task_ref)
        except Exception:
            raise ReadbackUnavailable() from None
        if not _within_engine_budget(response) or not isinstance(response, dict) or response.get("result") is not True:
            if (
                isinstance(response, dict)
                and isinstance(response.get("http_status"), int)
                and not isinstance(response.get("http_status"), bool)
                and response["http_status"] == 404
            ):
                raise TaskNotFound()
            raise ReadbackUnavailable()
        data = response.get("data")
        wire_state = data.get("state") if isinstance(data, dict) else None
        state = _WIRE_STATE_MAP.get(wire_state)
        if state is None:
            raise ReadbackUnavailable()
        return state, data

    def _node_id_map(self, task_ref):
        try:
            response = self._client.get_node_id_map(task_ref)
        except Exception:
            return None
        if (
            not _within_engine_budget(response)
            or not isinstance(response, dict)
            or response.get("result") is not True
            or not isinstance(response.get("data"), dict)
        ):
            return None
        return response["data"]

    def _node_outputs(self, task_ref, runtime_node_id, requested_keys):
        try:
            response = self._client.get_task_node_detail(
                task_ref,
                runtime_node_id,
                data={"include_data": True},
            )
        except Exception:
            return NodeOutputEvidence.unavailable()
        if (
            not _within_engine_budget(response)
            or not isinstance(response, dict)
            or response.get("result") is not True
            or not isinstance(response.get("data"), dict)
            or not isinstance(response["data"].get("outputs"), list)
        ):
            return NodeOutputEvidence.unavailable()
        outputs = {}
        for item in response["data"]["outputs"]:
            if not isinstance(item, dict) or not isinstance(item.get("key"), str) or "value" not in item:
                continue
            key = item["key"]
            if key not in requested_keys:
                continue
            if key in outputs or not is_bounded_non_secret_json(item["value"]):
                return NodeOutputEvidence.unavailable("node_output_unsafe")
            outputs[key] = item["value"]
        return NodeOutputEvidence.available(outputs)

    @staticmethod
    def _runtime_node_facts(state_tree, runtime_node_id):
        """Find one bounded runtime node state/version without retaining the tree."""
        pending = [state_tree]
        visited = 0
        while pending:
            current = pending.pop()
            visited += 1
            if visited > _MAX_ENGINE_NODES or not isinstance(current, dict):
                return None
            if current.get("id") == runtime_node_id:
                state = current.get("state")
                version = current.get("version")
                if not isinstance(state, str) or (version is not None and safe_opaque_identifier(version) is None):
                    return None
                return state, version
            children = current.get("children", {})
            if not isinstance(children, dict):
                return None
            pending.extend(children.values())
        return None

    @classmethod
    def _runtime_node_state(cls, state_tree, runtime_node_id):
        facts = cls._runtime_node_facts(state_tree, runtime_node_id)
        return facts[0] if facts is not None else None

    def observe(self, task_ref, pipeline_tree, required_outputs):
        """Return a bounded projection; never expose full states or node detail."""
        declared_nodes = self._declared_nodes(pipeline_tree)
        declared_outputs = self._declared_outputs(pipeline_tree)
        requested = {}
        for node_id, output_key in tuple(required_outputs):
            if node_id not in declared_nodes:
                raise ValueError("postcondition node is not declared by the published snapshot")
            if (node_id, output_key) not in declared_outputs:
                raise ValueError("postcondition output is not declared by the published snapshot")
            requested.setdefault(node_id, set()).add(output_key)
        state, state_tree = self._task_state(task_ref)
        if state != "FINISHED" or not requested:
            return ExecutionObservation(state=state, node_outputs={})
        node_map = self._node_id_map(task_ref)
        if node_map is None:
            return ExecutionObservation(
                state=state,
                node_outputs={node_id: NodeOutputEvidence.unavailable("node_map_unavailable") for node_id in requested},
            )
        projections = {}
        for node_id, output_keys in sorted(requested.items()):
            runtime_node_id = node_map.get(node_id)
            if safe_opaque_identifier(runtime_node_id) is None:
                projections[node_id] = NodeOutputEvidence.unavailable("node_mapping_unavailable")
                continue
            node_state = self._runtime_node_state(state_tree, runtime_node_id)
            if node_state is None:
                projections[node_id] = NodeOutputEvidence.unavailable("node_state_unavailable")
                continue
            if node_state not in _OUTPUT_READABLE_NODE_STATES:
                projections[node_id] = NodeOutputEvidence.unavailable("node_not_executed")
                continue
            projections[node_id] = self._node_outputs(task_ref, runtime_node_id, output_keys)
        return ExecutionObservation(state=state, node_outputs=projections)

    def observe_control(self, task_ref, pipeline_tree, *, template_node_id=None):
        """Read exact bounded task/node facts for one durable control attempt."""
        normalized_state, state_tree = self._task_state(task_ref)
        root_state = state_tree.get("state")
        if root_state not in _WIRE_STATE_MAP or _WIRE_STATE_MAP[root_state] != normalized_state:
            raise ReadbackUnavailable()
        if template_node_id is None:
            return ControlReadbackObservation(root_state=root_state)
        if safe_opaque_identifier(template_node_id) is None or template_node_id not in self._declared_nodes(
            pipeline_tree
        ):
            raise ReadbackUnavailable()
        node_map = self._node_id_map(task_ref)
        if node_map is None:
            raise ReadbackUnavailable()
        runtime_node_id = node_map.get(template_node_id)
        if safe_opaque_identifier(runtime_node_id) is None:
            raise ReadbackUnavailable()
        facts = self._runtime_node_facts(state_tree, runtime_node_id)
        if facts is None or safe_opaque_identifier(facts[1]) is None:
            raise ReadbackUnavailable()
        return ControlReadbackObservation(
            root_state=root_state,
            template_node_id=template_node_id,
            node_state=facts[0],
            node_version=facts[1],
            runtime_mapping_fingerprint=runtime_mapping_fingerprint(template_node_id, runtime_node_id),
        )


class BoundCredentialResolver:
    """Resolve only immutable binding refs after fresh scope authorization."""

    @staticmethod
    def _binding_and_capability(item):
        if not isinstance(item, dict) or set(item) != {"binding", "capability"}:
            raise ValueError("resolved capability binding is invalid")
        return item["binding"], item["capability"]

    def resolve(self, resolved_bindings, *, space_id, scope_type, scope_value):
        resolved = {}
        refs_by_key = {}
        credentials_by_ref = {}
        for item in resolved_bindings:
            binding, capability = self._binding_and_capability(item)
            if binding.credential_ref is None:
                continue
            if (
                capability.capability_ref != binding.capability_ref
                or capability.resolved_version != binding.resolved_version
                or capability.schema_hash != binding.schema_hash
                or capability.conversion_fingerprint != binding.conversion_fingerprint
                or capability.risk_level != binding.risk
            ):
                raise ValueError("capability binding is stale")
            metadata = capability.conversion_metadata
            if (
                capability.plugin_type != "uniform_api"
                or not isinstance(metadata, dict)
                or metadata.get("kind") != "uniform_api"
            ):
                raise ValueError("bound credentials require an exact uniform API capability")
            credential_key = metadata.get("credential_key")
            if not isinstance(credential_key, str) or _ENGINE_CREDENTIAL_KEY.fullmatch(credential_key) is None:
                raise ValueError("uniform API credential key is invalid")
            match = _CREDENTIAL_REF.fullmatch(binding.credential_ref)
            if match is None:
                raise ValueError("bound credential reference is invalid")
            credential_id = int(match.group(1))
            existing_ref = refs_by_key.get(credential_key)
            if existing_ref is not None and existing_ref != credential_id:
                raise ValueError("conflicting credential bindings")
            refs_by_key[credential_key] = credential_id
            credential = credentials_by_ref.get(credential_id)
            if credential is None:
                credential = Credential.objects.filter(id=credential_id, space_id=space_id, is_deleted=False).first()
                if credential is None or not credential.can_use_in_scope(scope_type, scope_value):
                    raise ValueError("bound credential is unavailable")
                credentials_by_ref[credential_id] = credential
            resolved[credential_key] = credential.value
        return resolved


class ApplicationTaskAdapter:
    """Use the server-side application domain service and never expose secrets."""

    CONTROL_TASK_ACTIONS = frozenset({"pause", "resume", "revoke"})
    CONTROL_NODE_ACTIONS = frozenset({"retry", "skip", "forced_fail"})
    CONTROL_TASK_SOURCE_STATES = {
        "pause": frozenset({"RUNNING"}),
        "resume": frozenset({"SUSPENDED"}),
        "revoke": frozenset({"RUNNING", "SUSPENDED", "FAILED", "NODE_SUSPENDED"}),
    }
    CONTROL_NODE_SOURCE_STATES = {
        "retry": frozenset({"FAILED"}),
        "skip": frozenset({"FAILED"}),
        "forced_fail": frozenset({"RUNNING"}),
    }
    CONTROL_NODE_ROOT_SOURCE_STATES = {
        "retry": frozenset({"FAILED"}),
        "skip": frozenset({"FAILED"}),
        "forced_fail": frozenset({"RUNNING"}),
    }

    def __init__(
        self,
        *,
        runtime_authorization_mode=RUNTIME_AUTHORIZATION_MODE,
        space_id=None,
        actor=None,
        task_creator=None,
        client_factory=None,
    ):
        if runtime_authorization_mode != RUNTIME_AUTHORIZATION_MODE:
            raise ValueError("runtime authorization mode is unavailable")
        if isinstance(space_id, bool) or not isinstance(space_id, int) or space_id <= 0:
            raise ValueError("runtime space is unavailable")
        if not isinstance(actor, str) or not actor:
            raise ValueError("runtime actor is unavailable")
        self._client_factory = client_factory or TaskComponentClient
        self._space_id = space_id
        self._actor = actor
        self._task_creator = task_creator or TaskCreator(client_factory=self._client_factory)

    @staticmethod
    def _safe_control_response(response):
        return _within_engine_budget(response) and isinstance(response, dict) and response.get("result") is True

    @staticmethod
    def _published_activity(pipeline_tree, template_node_id):
        required_sections = {"activities", "gateways", "flows"}
        if not isinstance(pipeline_tree, dict) or not required_sections <= set(pipeline_tree):
            raise ControlActionUnavailable("published control target is unavailable")
        activities = pipeline_tree.get("activities")
        if not isinstance(activities, dict):
            raise ControlActionUnavailable("published control target is unavailable")
        node = activities.get(template_node_id)
        if not isinstance(node, dict) or node.get("id") != template_node_id:
            raise ControlActionUnavailable("published control target is unavailable")
        return node

    @staticmethod
    def _published_capability_facts(node):
        node_type = node.get("type")
        if safe_opaque_identifier(node_type) is None:
            raise ControlActionUnavailable("published node type is unavailable")
        retryable = node.get("retryable")
        skippable = node.get("skippable")
        return (
            node_type,
            retryable if isinstance(retryable, bool) else None,
            skippable if isinstance(skippable, bool) else None,
        )

    @classmethod
    def _validate_node_capability(cls, request, node, node_state):
        if node_state not in cls.CONTROL_NODE_SOURCE_STATES[request.action]:
            raise ControlActionUnavailable("control source state is unavailable")
        if request.action == "retry" and node.get("retryable") is not True:
            raise ControlActionUnavailable("published retry capability is unavailable")
        if request.action == "skip" and node.get("skippable") is not True:
            raise ControlActionUnavailable("published skip capability is unavailable")
        if request.action in {"retry", "skip"} and request.loop is not False:
            # Current Task APIs expose no trustworthy loop/sleep provenance.
            raise ControlActionUnavailable("loop control provenance is unavailable")
        if request.action == "forced_fail" and node.get("type") != "ServiceActivity":
            raise ControlActionUnavailable("forced fail target is unavailable")

    def control_preflight(self, task_ref, request, pipeline_tree=None):
        """Return exact bounded wire facts, mapping only server-owned template node IDs."""
        if request.action not in self.CONTROL_TASK_ACTIONS | self.CONTROL_NODE_ACTIONS:
            raise ControlActionUnavailable("control action is unavailable")
        if request.action == "retry" and request.inputs is not None:
            # No current domain service exposes an immutable capability input
            # schema that can authorize caller-provided retry values.
            raise ControlActionUnavailable("retry inputs are unavailable")
        if safe_opaque_identifier(task_ref) is None:
            raise ControlActionUnavailable("task reference is unavailable")
        try:
            client = self._client_factory(space_id=self._space_id)
            states = client.get_task_states(task_ref)
        except Exception:
            raise ReadbackUnavailable() from None
        if not self._safe_control_response(states) or not isinstance(states.get("data"), dict):
            if (
                isinstance(states, dict)
                and isinstance(states.get("http_status"), int)
                and not isinstance(states.get("http_status"), bool)
                and states["http_status"] == 404
            ):
                raise TaskNotFound()
            raise ReadbackUnavailable()
        root = states["data"]
        root_state = root.get("state")
        if root_state not in _WIRE_STATE_MAP:
            raise ReadbackUnavailable()
        if request.action in self.CONTROL_TASK_ACTIONS:
            if root_state not in self.CONTROL_TASK_SOURCE_STATES[request.action]:
                raise ControlActionUnavailable("control source state is unavailable")
            return ControlObservation(task_ref=task_ref, root_state=root_state, action=request.action)
        if root_state not in self.CONTROL_NODE_ROOT_SOURCE_STATES[request.action]:
            raise ControlActionUnavailable("control root source state is unavailable")
        node = self._published_activity(pipeline_tree, request.template_node_id)
        published_facts = self._published_capability_facts(node)
        try:
            node_map = client.get_node_id_map(task_ref)
        except Exception:
            raise ReadbackUnavailable() from None
        if not self._safe_control_response(node_map) or not isinstance(node_map.get("data"), dict):
            raise ReadbackUnavailable()
        runtime_node_id = node_map["data"].get(request.template_node_id)
        if safe_opaque_identifier(runtime_node_id) is None:
            raise ReadbackUnavailable()
        facts = ExecutionReadAdapter._runtime_node_facts(root, runtime_node_id)
        if facts is None or safe_opaque_identifier(facts[1]) is None:
            raise ReadbackUnavailable()
        self._validate_node_capability(request, node, facts[0])
        return ControlObservation(
            task_ref=task_ref,
            root_state=root_state,
            action=request.action,
            template_node_id=request.template_node_id,
            runtime_node_id=runtime_node_id,
            node_state=facts[0],
            node_version=facts[1],
            published_node_type=published_facts[0],
            published_retryable=published_facts[1],
            published_skippable=published_facts[2],
        )

    def _validate_control_observation(self, task_ref, request, observation, pipeline_tree):
        if not isinstance(observation, ControlObservation):
            raise ControlActionUnavailable("control preflight is unavailable")
        if safe_opaque_identifier(task_ref) is None or observation.task_ref != task_ref:
            raise ControlActionUnavailable("control preflight does not match task")
        if observation.action != request.action or observation.root_state not in _WIRE_STATE_MAP:
            raise ControlActionUnavailable("control preflight does not match request")
        if request.action in self.CONTROL_TASK_ACTIONS:
            empty_node_facts = (
                observation.template_node_id,
                observation.runtime_node_id,
                observation.node_state,
                observation.node_version,
                observation.published_node_type,
                observation.published_retryable,
                observation.published_skippable,
            )
            if any(value is not None for value in empty_node_facts):
                raise ControlActionUnavailable("task control preflight contains node facts")
            if observation.root_state not in self.CONTROL_TASK_SOURCE_STATES[request.action]:
                raise ControlActionUnavailable("control source state is unavailable")
            return
        if (
            observation.template_node_id != request.template_node_id
            or observation.root_state not in self.CONTROL_NODE_ROOT_SOURCE_STATES[request.action]
            or safe_opaque_identifier(observation.runtime_node_id) is None
            or observation.node_state not in self.CONTROL_NODE_SOURCE_STATES[request.action]
            or safe_opaque_identifier(observation.node_version) is None
        ):
            raise ControlActionUnavailable("node control preflight is unavailable")
        node = self._published_activity(pipeline_tree, request.template_node_id)
        if self._published_capability_facts(node) != (
            observation.published_node_type,
            observation.published_retryable,
            observation.published_skippable,
        ):
            raise ControlActionUnavailable("published control capability has changed")
        self._validate_node_capability(request, node, observation.node_state)

    @staticmethod
    def _same_control_observation(expected, actual):
        return isinstance(actual, ControlObservation) and actual == expected

    def control_dispatch(self, task_ref, request, observation, pipeline_tree=None):
        """Dispatch one normalized action and discard every downstream response field."""
        if request.action not in self.CONTROL_TASK_ACTIONS | self.CONTROL_NODE_ACTIONS:
            raise ControlActionUnavailable("control action is unavailable")
        self._validate_control_observation(task_ref, request, observation, pipeline_tree)
        fresh_observation = self.control_preflight(task_ref, request, pipeline_tree)
        if not self._same_control_observation(observation, fresh_observation):
            raise ControlActionUnavailable("control preflight facts have changed")
        try:
            client = self._client_factory(space_id=self._space_id)
            if request.action in self.CONTROL_TASK_ACTIONS:
                response = client.operate_task(task_ref, request.action, {"operator": self._actor})
            else:
                if safe_opaque_identifier(observation.runtime_node_id) is None:
                    raise ControlDispatchUncertain()
                data = {"operator": self._actor}
                if request.action == "retry":
                    data["loop"] = request.loop
                    if request.inputs is not None:
                        data["inputs"] = deepcopy(request.inputs)
                elif request.action == "skip":
                    data["loop"] = request.loop
                response = client.node_operate(
                    task_ref,
                    observation.runtime_node_id,
                    request.action,
                    data,
                )
        except ControlDispatchUncertain:
            raise
        except Exception:
            raise ControlDispatchUncertain() from None
        if not self._safe_control_response(response):
            raise ControlDispatchUncertain()
        return ControlDispatchReceipt(acknowledged=True)

    def create(self, *, publication, request, credentials):
        try:
            receipt = self._task_creator.create_from_publication(
                publication=publication,
                request_data={
                    "template_id": publication.published_template_id,
                    "name": request.name,
                    "creator": publication.manifest.run.actor,
                    "constants": request.constants,
                    "credentials": credentials,
                },
                actor=publication.manifest.run.actor,
            )
        except TaskCreationRejected:
            raise CreateDispatchRejected() from None
        except TaskCreationUncertain:
            raise CreateDispatchUncertain() from None
        except Exception:
            raise CreateDispatchUncertain() from None
        return receipt

    def start(self, task_ref):
        try:
            result = self._client_factory(space_id=self._space_id).operate_task(
                task_ref, "start", {"operator": self._actor}
            )
        except Exception:
            raise StartDispatchUncertain() from None
        if not isinstance(result, dict):
            raise StartDispatchUncertain()
        if result.get("result") is not True:
            raise StartDispatchUncertain()

    def read_state(self, task_ref):
        try:
            result = self._client_factory(space_id=self._space_id).get_task_states(task_ref)
        except Exception:
            raise ReadbackUnavailable() from None
        if not isinstance(result, dict) or result.get("result") is not True or not isinstance(result.get("data"), dict):
            raise ReadbackUnavailable()
        state = result["data"].get("state")
        if not isinstance(state, str) or not state:
            raise ReadbackUnavailable()
        return state


__all__ = [
    "ApplicationTaskAdapter",
    "BoundCredentialResolver",
    "ControlActionUnavailable",
    "ControlDispatchReceipt",
    "ControlDispatchUncertain",
    "ControlObservation",
    "ControlReadbackObservation",
    "CreateDispatchRejected",
    "CreateDispatchUncertain",
    "ExecutionObservation",
    "ExecutionReadAdapter",
    "ReadbackUnavailable",
    "StartDispatchRejected",
    "StartDispatchUncertain",
    "TaskNotFound",
    "runtime_mapping_fingerprint",
]
