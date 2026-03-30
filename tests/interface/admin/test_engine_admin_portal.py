import pytest
from django.template import Context, Template

from bkflow.admin.models import ModuleInfo


@pytest.mark.django_db
class TestGetEngineModulesTag:
    def test_returns_empty_list_when_no_modules(self):
        template = Template("{% load engine_admin_tags %}{% get_engine_modules as modules %}{{ modules|length }}")
        result = template.render(Context())
        assert result.strip() == "0"

    def test_returns_modules_with_admin_url(self):
        ModuleInfo.objects.create(
            space_id=0,
            code="default",
            url="http://engine-default.example.com",
            token="test_token",
            type="TASK",
            isolation_level="all_resource",
        )
        template = Template(
            "{% load engine_admin_tags %}"
            "{% get_engine_modules as modules %}"
            "{{ modules.0.code }}|{{ modules.0.admin_url }}"
        )
        result = template.render(Context())
        assert "default" in result
        assert "http://engine-default.example.com/bkflow_admin/" in result

    def test_strips_trailing_slash_from_url(self):
        ModuleInfo.objects.create(
            space_id=1,
            code="engine-a",
            url="http://engine-a.example.com/",
            token="test_token",
            type="TASK",
            isolation_level="all_resource",
        )
        template = Template(
            "{% load engine_admin_tags %}" "{% get_engine_modules as modules %}" "{{ modules.0.admin_url }}"
        )
        result = template.render(Context())
        assert "http://engine-a.example.com/bkflow_admin/" in result
        assert "//bkflow_admin" not in result


class TestAdminSiteConfig:
    def test_index_template_is_set(self):
        from django.contrib import admin

        assert admin.site.index_template == "admin/bkflow_index.html"

    def test_site_header_is_set(self):
        from django.contrib import admin

        assert admin.site.site_header == "BKFlow 管理后台"


@pytest.mark.django_db
class TestModuleInfoAdminLink:
    def test_admin_link_with_url(self):
        from bkflow.admin.admin import ModuleInfoAdmin

        module = ModuleInfo(
            space_id=0,
            code="default",
            url="http://engine.example.com",
            token="t",
            type="TASK",
            isolation_level="all_resource",
        )
        admin_instance = ModuleInfoAdmin(ModuleInfo, None)
        result = admin_instance.admin_link(module)
        assert "http://engine.example.com/bkflow_admin/" in result
        assert 'target="_blank"' in result

    def test_admin_link_with_trailing_slash(self):
        from bkflow.admin.admin import ModuleInfoAdmin

        module = ModuleInfo(
            space_id=0,
            code="default",
            url="http://engine.example.com/",
            token="t",
            type="TASK",
            isolation_level="all_resource",
        )
        admin_instance = ModuleInfoAdmin(ModuleInfo, None)
        result = admin_instance.admin_link(module)
        assert "http://engine.example.com/bkflow_admin/" in result
        assert "//bkflow_admin" not in result

    def test_admin_link_without_url(self):
        from bkflow.admin.admin import ModuleInfoAdmin

        module = ModuleInfo(
            space_id=0,
            code="default",
            url="",
            token="t",
            type="TASK",
            isolation_level="all_resource",
        )
        admin_instance = ModuleInfoAdmin(ModuleInfo, None)
        result = admin_instance.admin_link(module)
        assert result == "-"
