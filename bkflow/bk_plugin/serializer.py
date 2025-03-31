from datetime import datetime

from rest_framework import serializers

from bkflow.bk_plugin.models import (
    AuthStatus,
    BKPlugin,
    BKPluginAuthorization,
    get_default_config,
)
from bkflow.constants import ALL_SPACE, WHITE_LIST


class BKPluginSerializer(serializers.ModelSerializer):
    class Meta:
        model = BKPlugin
        fields = "__all__"


class BKPluginAuthSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True, max_length=100)
    status = serializers.IntegerField()
    config = serializers.JSONField(default=get_default_config())
    operator = serializers.CharField(read_only=True, max_length=255, allow_blank=True)

    def update(self, instance, validated_data):
        update_fields = []
        if "config" in validated_data:
            white_list = validated_data["config"].get(WHITE_LIST, [])
            if not white_list:
                raise serializers.ValidationError(f"白名单{WHITE_LIST}不能为空")
            for space_id in white_list:
                if space_id == ALL_SPACE:
                    # 如果存在 *，直接覆盖
                    instance.config[WHITE_LIST] = white_list
                    break
            update_fields.append("config")
        if "status" in validated_data:
            instance.status = validated_data["status"]
            if instance.status == AuthStatus.authorized:
                instance.authorized_time = datetime.now()
                instance.operator = self.context.get("username", "")
            update_fields.extend(["status", "operator", "authorized_time"])
        instance.save(update_fields=update_fields)
        return instance

    def validate_status(self, value):
        if value not in [AuthStatus.authorized, AuthStatus.unauthorized]:
            raise serializers.ValidationError(f"status must be {AuthStatus.authorized} or {AuthStatus.unauthorized}")
        return value

    class Meta:
        model = BKPluginAuthorization
        fields = "__all__"


class AuthQuerySerializer(serializers.Serializer):
    tag = serializers.IntegerField(required=True)
    space_id = serializers.IntegerField(required=True)


class AuthListSerializer(serializers.Serializer):
    code = serializers.CharField(read_only=True, max_length=100)
    name = serializers.CharField(max_length=100)
    manager = serializers.CharField(max_length=255)
    authorization = serializers.SerializerMethodField()

    class Meta:
        model = BKPlugin
        fields = "code,name,manager"

    def get_authorization(self, obj):
        authorization = BKPluginAuthorization.objects.filter(code=obj.code).first()
        if not authorization:
            return BKPluginAuthorization(code=obj.code).to_json()
        return authorization.to_json()
