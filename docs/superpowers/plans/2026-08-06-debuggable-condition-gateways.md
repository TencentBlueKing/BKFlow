# Debuggable Conditional Gateways Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent debug status and synchronous path evaluation for conditional gateways while removing non-debuggable control nodes from the debug panel.

**Architecture:** A focused gateway evaluator renders conditions with the same template and expression functions used by the engine. `DebugService` includes only activity nodes plus condition-bearing gateways in `DebugNodeState`, dispatches gateway step calls to the synchronous evaluator, and stores selected paths in the existing `outputs` JSON field.

**Tech Stack:** Python 3.10, Django, Django REST Framework, bamboo-pipeline 3.29.9, pytest.

## Global Constraints

- Gateway single-step evaluation must not create an engine task or execute downstream nodes.
- Only `ExclusiveGateway` and `ConditionalParallelGateway` are debuggable gateways.
- Gateways always use real mode and never support mock.
- Start, end, parallel, and converge control nodes must not appear in `debug_context.nodes`.
- Do not add a database migration; persist branch results in `DebugNodeState.outputs`.

---

### Task 1: Gateway Evaluation Unit

**Files:**
- Create: `bkflow/template/debug/gateway.py`
- Create: `tests/interface/template/debug/test_gateway.py`

**Interfaces:**
- Produces: `DEBUGGABLE_GATEWAY_TYPES`, `GatewayEvaluationError`, `gateway_missing_vars(pipeline_tree, gateway_id, values)`, and `evaluate_gateway(pipeline_tree, gateway_id, values)`.
- `evaluate_gateway` returns `{"selected_flow_ids": list[str], "condition_results": list[dict]}`.

- [ ] **Step 1: Write failing evaluator tests**

Cover exclusive single selection, exclusive default selection, exclusive multiple-match failure, conditional-parallel multi-selection, missing produced variables, and malformed expressions.

- [ ] **Step 2: Run the evaluator tests and verify they fail**

Run: `PYENV_VERSION=3.10.6 pytest tests/interface/template/debug/test_gateway.py -q`

Expected: collection fails because `bkflow.template.debug.gateway` does not exist.

- [ ] **Step 3: Implement the gateway evaluator**

Render condition expressions using `bamboo_engine.template.Template`, evaluate them using `bkflow.utils.pipeline.pipeline_gateway_expr_func`, preserve flow IDs, and raise `GatewayEvaluationError` with user-facing details for invalid selection.

- [ ] **Step 4: Run evaluator tests**

Run: `PYENV_VERSION=3.10.6 pytest tests/interface/template/debug/test_gateway.py -q`

Expected: all evaluator tests pass.

### Task 2: Context Node Selection And Capabilities

**Files:**
- Modify: `bkflow/template/debug/service.py`
- Modify: `tests/interface/template/debug/test_service_context.py`

**Interfaces:**
- `sync_node_states()` creates states for activities plus gateways whose type is in `DEBUGGABLE_GATEWAY_TYPES`.
- `build_context_view()` returns `supports_mock`, `selected_flow_ids`, and `condition_results`.
- `compute_can_step()` supports condition expressions as well as activity inputs.

- [ ] **Step 1: Add failing context tests**

Build a tree containing an activity, both conditional gateways, a parallel gateway, and a converge gateway. Assert that context contains only the activity and two conditional gateways, and that gateway capability/result fields have the documented values.

- [ ] **Step 2: Run context tests and verify failure**

Run: `PYENV_VERSION=3.10.6 pytest tests/interface/template/debug/test_service_context.py -q`

- [ ] **Step 3: Implement node selection and response fields**

Build a merged debug-node mapping, restrict legacy mock initialization to activities, and map gateway `outputs` to the explicit branch-result fields.

- [ ] **Step 4: Run context tests**

Run: `PYENV_VERSION=3.10.6 pytest tests/interface/template/debug/test_service_context.py -q`

Expected: all context tests pass.

### Task 3: Gateway Step Execution And Global Synchronization

**Files:**
- Modify: `bkflow/template/debug/service.py`
- Modify: `tests/interface/template/debug/test_step_run.py`
- Modify: `tests/interface/template/debug/test_service_sync.py`
- Modify: `tests/interface/template/debug/test_views_run_ops.py`

**Interfaces:**
- `step_run()` dispatches debuggable gateways to `_step_run_gateway()`.
- `_step_run_gateway()` synchronously persists `finished` or `failed` and returns branch results without a task ID.
- `node_mock()` and `step_run(mode="mock")` reject gateways.
- `sync_from_debug_task()` persists gateway runtime state and branch results during global runs.

- [ ] **Step 1: Add failing service and view tests**

Assert synchronous successful gateway steps, failed expression state, mock rejection, lock release, no task-client calls, and successful/failed global gateway synchronization.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `PYENV_VERSION=3.10.6 pytest tests/interface/template/debug/test_step_run.py tests/interface/template/debug/test_service_sync.py tests/interface/template/debug/test_views_run_ops.py -q`

- [ ] **Step 3: Implement gateway step and synchronization**

Acquire/release the existing debug lock around direct evaluation, persist results in `outputs`, update context last-run fields, and reuse the evaluator after a globally executed gateway reaches `FINISHED`.

- [ ] **Step 4: Run focused tests**

Run: `PYENV_VERSION=3.10.6 pytest tests/interface/template/debug/test_step_run.py tests/interface/template/debug/test_service_sync.py tests/interface/template/debug/test_views_run_ops.py -q`

Expected: all focused tests pass.

### Task 4: Contract Documentation And Regression

**Files:**
- Modify: `bkflow/apigw/docs/zh/sdk_debug_context.md`
- Modify: `bkflow/apigw/docs/zh/sdk_debug_step_run.md`
- Modify: `bkflow/apigw/docs/zh/sdk_debug_node_mock.md`

**Interfaces:**
- Documents capability fields, selected flow IDs, synchronous gateway step responses, and gateway mock rejection.

- [ ] **Step 1: Update API examples and field descriptions**

Document both activity and gateway nodes without changing route names.

- [ ] **Step 2: Run the complete debug test suite**

Run: `PYENV_VERSION=3.10.6 pytest tests/interface/template/debug -q`

Expected: all debug tests pass.

- [ ] **Step 3: Run formatting and static checks on changed Python files**

Run: `PYENV_VERSION=3.10.6 black --check bkflow/template/debug tests/interface/template/debug`

Run: `PYENV_VERSION=3.10.6 flake8 bkflow/template/debug tests/interface/template/debug`

Expected: both commands exit 0.
