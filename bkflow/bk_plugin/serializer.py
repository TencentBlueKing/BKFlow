from rest_framework import serializers

from bkflow.bk_plugin.models import AuthorizeStatus, BKPlugin, BKPluginAuthentication
from bkflow.bk_plugin.utils import ALL_SPACE


class BKPluginSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True, max_length=100)
    name = serializers.CharField(required=True, max_length=255)
    tag = serializers.IntegerField(required=True)
    contact = serializers.JSONField(required=True)
    logo_url = serializers.CharField(max_length=255)
    introduction = serializers.CharField(max_length=255)
    created_time = serializers.DateTimeField()
    updated_time = serializers.DateTimeField()
    extra_info = serializers.JSONField()

    class Meta:
        model = BKPlugin
        fields = "__all__"


# 更新插件配置的序列化器，后续可在这里扩展
class UpdateAuthConfigSerializer(serializers.Serializer):
    config = serializers.JSONField(required=True)

    def validate_config(self, config_data):
        white_list = config_data.get("white_list", [])
        for space_id in white_list:
            if space_id == ALL_SPACE:
                # 如果存在 *，直接覆盖
                config_data["white_list"] = [ALL_SPACE]
                break
        return config_data

    def update(self, instance, validated_data):
        if "config" in validated_data:
            instance.config = validated_data["config"]
            instance.save()
        return instance


class BKPluginAuthSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True, max_length=100)
    name = serializers.SerializerMethodField()
    status = serializers.ChoiceField(choices=BKPluginAuthentication.AuthStatus, default=AuthorizeStatus.unauthorized)
    config = serializers.JSONField(required=True)
    operator = serializers.CharField(required=True, max_length=255, allow_blank=True)
    authorized_time = serializers.DateTimeField(allow_null=True)

    class Meta:
        model = BKPluginAuthentication
        fields = "__all__"

    def get_name(self, obj):
        try:
            bk_plugin = BKPlugin.objects.get(code=obj.code)
            return bk_plugin.name
        except BKPlugin.DoesNotExist:
            return "not exist"


class AuthQuerySerializer(serializers.Serializer):
    tag = serializers.IntegerField(required=True)
    space_id = serializers.IntegerField(required=True)
