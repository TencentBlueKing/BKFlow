from django.contrib import admin

from bkflow.bk_plugin.models import BKPlugin, BKPluginAuthorization


# Register your models here.
@admin.register(BKPlugin)
class BKPluginAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "tag",
        "logo_url",
        "introduction",
        "created_time",
        "updated_time",
        "manager",
        "extra_info",
    )
    search_fields = ("code", "name", "tag")
    list_filter = ("code",)
    ordering = ("code",)


@admin.register(BKPluginAuthorization)
class BKPluginAuthenticationAdmin(admin.ModelAdmin):
    list_display = ("code", "status", "config", "authorized_time", "operator")
    search_fields = ("code", "operator")
    list_filter = ("code", "operator", "status")
    ordering = ("code",)
