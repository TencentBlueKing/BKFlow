#!/bin/bash
# 必需的初始化失败时立即退出；不把后续命令的成功当作迁移成功。
run_required() {
  "$@" || { status=$?; echo "required release step failed: $*" >&2; exit "$status"; }
}
run_cache_table() {
  # Django 在表已存在时以失败退出。首次发布仍要建表，重复发布跳过这一步。
  output=$(python manage.py createcachetable django_cache 2>&1)
  status=$?
  if [ -n "$output" ]; then
    printf '%s\n' "$output" >&2
  fi
  if [ "$status" -eq 0 ]; then
    return 0
  fi
  case "$output" in
    *"Cache table 'django_cache' already exists."*)
      echo "django_cache already exists, skip createcachetable" >&2
      return 0
      ;;
  esac
  echo "required release step failed: python manage.py createcachetable django_cache" >&2
  exit "$status"
}
run_required python manage.py migrate
run_cache_table
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
