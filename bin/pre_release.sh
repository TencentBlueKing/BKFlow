#!/bin/bash
# 必需的初始化失败时立即退出；不把后续命令的成功当作迁移成功。
run_required() {
  "$@" || { status=$?; echo "required release step failed: $*" >&2; exit "$status"; }
}
run_required python manage.py migrate
run_required python manage.py createcachetable django_cache
run_required python manage.py update_component_models
run_required python manage.py update_variable_models
run_required python manage.py sync_superuser
if [ "$BKPAAS_APP_MODULE_NAME" == "default" ]; then
  run_required python manage.py sync_saas_apigw
  run_required python manage.py sync_default_module
  python manage.py register_bkflow_to_bknotice || echo "optional notice registration failed" >&2
  python manage.py sync_webhook_events . webhook_resources.yaml
else
  echo "current module is not 'default', skip interface-only release steps"
fi
