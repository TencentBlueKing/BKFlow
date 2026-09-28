PYTHON ?= python
PYTEST ?= $(PYTHON) -m pytest
PYTEST_FLAGS ?= -q -rs --strict-markers --disable-warnings --no-cov

HARNESS_P2_GATE_PATHS := \
	tests/interface/harness \
	tests/interface/permission/test_token_issuer.py \
	tests/interface/template/debug \
	tests/interface/apigw/test_harness_p0.py \
	tests/interface/apigw/test_harness_p1.py \
	tests/interface/apigw/test_harness_p2.py \
	tests/interface/apigw/test_harness_resource_contract.py \
	tests/interface/apigw/test_apply_token.py \
	tests/interface/apigw/test_token_resource_validator.py

HARNESS_P3_GATE_PATHS := \
	$(HARNESS_P2_GATE_PATHS) \
	tests/interface/apigw/test_harness_p3.py \
	tests/interface/template/services/test_release.py \
	tests/interface/task/services/test_task_creator.py \
	tests/interface/apigw/test_release_template.py \
	tests/interface/apigw/test_create_task.py \
	tests/interface/apigw/test_update_template.py \
	tests/interface/template/test_template_views.py

HARNESS_P4_GATE_PATHS := \
	$(HARNESS_P3_GATE_PATHS) \
	tests/interface/apigw/test_harness_p4.py

.PHONY: harness-p2-gate
harness-p2-gate:
	$(PYTHON) manage.py check
	$(PYTHON) manage.py makemigrations harness --check --dry-run
	unzip -t bkflow/apigw/docs/apigw-docs.zip
	$(PYTEST) $(HARNESS_P2_GATE_PATHS) $(PYTEST_FLAGS)

.PHONY: harness-p3-gate
harness-p3-gate:
	$(PYTHON) manage.py check
	$(PYTHON) manage.py makemigrations harness --check --dry-run
	unzip -t bkflow/apigw/docs/apigw-docs.zip
	$(PYTEST) $(HARNESS_P3_GATE_PATHS) $(PYTEST_FLAGS)
	git diff --check

.PHONY: harness-p4-gate
harness-p4-gate:
	$(PYTHON) manage.py check
	$(PYTHON) manage.py makemigrations harness --check --dry-run
	unzip -t bkflow/apigw/docs/apigw-docs.zip
	$(PYTEST) $(HARNESS_P4_GATE_PATHS) $(PYTEST_FLAGS)
	git diff --check
