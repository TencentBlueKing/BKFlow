#!/bin/bash
python manage.py migrate
python manage.py createcachetable django_cache
python manage.py update_component_models
python manage.py update_variable_models
if [ "$BKPAAS_APP_MODULE_NAME" == "default" ]; then
  python manage.py sync_saas_apigw
  python manage.py sync_superuser
  python manage.py sync_default_module
  python manage.py register_bkflow_to_bknotice
  python manage.py sync_webhook_events . webhook_resources.yaml
else
  echo "current module is not 'default', skip sync_saas_apigw"
fi