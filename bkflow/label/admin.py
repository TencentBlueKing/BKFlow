from django.contrib import admin
from .models import Label, TemplateLabelRelation


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    """Admin configuration for Label model."""

    list_display = (
        "id",
        "name",
        "space_id",
        "parent_label",
        "is_default",
        "color",
        "full_path",
        "created_at",
        "updated_at",
    )
    list_filter = ("space_id", "is_default")
    search_fields = ("name", "creator", "updated_by", "description")
    readonly_fields = ("created_at", "updated_at", "full_path")
    ordering = ("space_id", "parent_id", "name")
    list_per_page = 50

    def parent_label(self, obj):
        """Show parent label name in list_display."""
        parent = obj.get_parent_label()
        return parent.name if parent else "-"

    parent_label.short_description = "Parent label"


@admin.register(TemplateLabelRelation)
class TemplateLabelRelationAdmin(admin.ModelAdmin):
    """Admin for template-label relations."""

    list_display = ("id", "template_id", "label_id", "label_name")
    list_filter = ("template_id",)
    search_fields = ("template_id", "label_id")
    list_per_page = 50

    def label_name(self, obj):
        """Resolve label name from label_id."""
        try:
            label = Label.objects.get(id=obj.label_id)
            return label.name
        except Label.DoesNotExist:
            return "-"

    label_name.short_description = "Label"
