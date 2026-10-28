"""Django 4.2 routes for django-bkvision 1.2.0.

The SDK still imports the removed django.conf.urls.url. Keep its public paths
and original decorated views here, without patching Django globally.
"""

from django.urls import re_path
from django_bkvision import views

urlpatterns = (
    re_path(r"^api/v1/datasource/query/$", views.query_datasource),
    re_path(r"^api/v1/dataset/query/$", views.query_dataset),
    re_path(r"^api/v1/field/(?P<uid>\w+)/preview_data/$", views.preview_field_data),
    re_path(r"^api/v1/meta/query/$", views.query_meta),
    re_path(r"^api/v1/variable/query/$", views.query_variable),
    re_path(r"^api/v1/variable/test/$", views.test_variable),
    re_path(r"^api/v1/panel/$", views.get_panel),
    re_path(r"^api/v1/panel/get_child_panels/$", views.get_child_panels),
    re_path(r"^bkcdn/(?P<path>.*)", views.proxy_bkcdn),
    re_path(r"^api/v1/ai/session/batch_delete/$", views.batch_delete_session),
    re_path(r"^api/v1/ai/session/(?P<session_code>[\w-]+)/ai_rename/$", views.rename_session),
    re_path(r"^api/v1/ai/session/(?P<session_code>[\w-]+)/$", views.session_instance_handler),
    re_path(r"^api/v1/ai/session/$", views.session_handler),
    re_path(r"^api/v1/ai/session_content/content/$", views.get_session_content),
    re_path(r"^api/v1/ai/session_content/batch_delete/$", views.batch_delete_session_content),
    re_path(r"^api/v1/ai/session_content/(?P<content_id>\w+)/$", views.session_content_instance_handler),
    re_path(r"^api/v1/ai/session_content/$", views.create_session_content),
    re_path(r"^api/v1/ai/chat_completion/$", views.create_chat_completion),
    re_path(r"^api/v1/ai/agent/info/$", views.get_agent_info),
)
