from rest_framework import serializers

from bkflow.template.models import Trigger


class ConfigSerializer(serializers.Serializer):
    """定时触发器配置序列化器"""

    constants = serializers.JSONField(help_text="流程入参", required=True, allow_null=True)
    cron = serializers.JSONField(help_text="cron表达式", required=False)

    def validate_cron(self, cron_data):
        required_fields = ["minute", "hour", "day_of_month", "month_of_year", "day_of_week"]
        if not all(field in cron_data for field in required_fields):
            raise serializers.ValidationError("Cron expression is missing required fields")
        return cron_data


class TriggerSerializer(serializers.ModelSerializer):
    """定时触发器序列化器"""

    id = serializers.IntegerField(help_text="触发器ID", required=True, allow_null=True)
    create_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False, allow_null=True)
    update_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False, allow_null=True)
    config = ConfigSerializer(help_text="触发器配置", required=True)
    updated_by = serializers.CharField(help_text="更新人", required=False, allow_null=True)

    class Meta:
        model = Trigger
        fields = "__all__"
