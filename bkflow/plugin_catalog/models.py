"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from bkflow.contrib.operation_record.models import BaseOperateRecord
from bkflow.utils.models import CommonModel


class PluginType:
    """
    统一插件类型口径：builtin/bk_plugin/api 三类，与 PluginSchemaService 内部的
    component/remote_plugin/uniform_api 口径存在映射关系。

    注意：uniform_api（API 插件）内部存在 V2/V3/旧协议 与 V4（wrapper_version=="v4.0.0"）
    两种协议世代，但统一用 API 这一个 plugin_type 值表示，不按协议版本拆分类型。两者的区别
    只影响"画布展示时走缓存读还是现场请求"（见 bkflow/pipeline_plugins/query/uniform_api/
    uniform_api.py 的 catalog_mode 分支），**不影响**是否能被本插件目录精细化管理——
    PluginCatalogSyncService.sync_api 通过 OpenPluginCatalogService.fetch_all_source_plugins
    现场拉取每个来源的完整插件清单（不按 wrapper_version 过滤），统一为 V2/V3/V4 生成
    SpacePluginCatalogEntry 记录。
    """

    BUILTIN = "builtin"
    BK_PLUGIN = "bk_plugin"
    API = "api"

    CHOICES = (
        (BUILTIN, _("内置插件")),
        (BK_PLUGIN, _("蓝鲸插件")),
        (API, _("API 插件")),
    )


class PluginCatalogStatus:
    """
    插件目录状态机（六态）：待审核 / 启用 / 已停用 / 已下架 / 已失效 / 未启用(不启用)。
    流转规则由各处服务层按场景校验（编辑、停用、下架、失效分别对应不同入口）。
    """

    REVIEW = "review"
    VISIBLE = "visible"
    DISABLED = "disabled"
    OFFLINE = "offline"
    INVALID = "invalid"
    NOT_ENABLED = "not_enabled"

    CHOICES = (
        (REVIEW, _("待审核")),
        (VISIBLE, _("启用")),
        (DISABLED, _("已停用")),
        (OFFLINE, _("已下架")),
        (INVALID, _("已失效")),
        (NOT_ENABLED, _("未启用(不启用)")),
    )

    # 未启用大 Tab 下聚合的三个子状态，供列表/查询层复用
    UNUSED_GROUP = (DISABLED, OFFLINE, NOT_ENABLED)


class TemplatePluginReferenceRole:
    PUBLISHED = "published"
    DRAFT = "draft"

    CHOICES = (
        (PUBLISHED, _("线上版")),
        (DRAFT, _("草稿")),
    )


class PluginDirectory(models.Model):
    """
    空间插件目录（分类树），空间内最多两级。
    一级目录 parent 为空；二级目录的 parent 指向所属一级目录，且不可再有子级。
    "未分类/全部/空间推荐" 为前端虚拟节点，不在本表中落库，
    SpacePluginCatalogEntry.directory 为空即表示未分类。
    不继承 CommonModel：目录是纯结构数据，删除为真实 DELETE，不保留软删痕迹，
    具体删除策略（提升子目录/并入其他一级目录/全部回到未分类）见目录管理服务。
    """

    space_id = models.IntegerField(_("空间ID"), db_index=True)
    parent = models.ForeignKey(
        "self",
        verbose_name=_("父级目录"),
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    name = models.CharField(_("目录名称"), max_length=64)
    desc = models.CharField(_("目录描述"), max_length=256, blank=True, default="")
    order = models.IntegerField(_("同级排序"), default=0)
    bindings = models.JSONField(
        _("绑定来源"),
        default=list,
        blank=True,
        help_text=_(
            "仅一级目录可绑定来源 source_key 列表；该来源下未单独指定分类的插件自动归入本目录；"
            "同一来源在同一空间内只能绑定一个一级目录"
        ),
    )
    create_time = models.DateTimeField(_("创建时间"), auto_now_add=True)
    update_time = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("空间插件目录")
        verbose_name_plural = _("空间插件目录")
        app_label = "plugin_catalog"
        unique_together = ("space_id", "parent", "name")
        ordering = ["space_id", "parent_id", "order", "id"]
        indexes = [
            models.Index(fields=["space_id", "parent"]),
        ]

    def __str__(self):
        return f"{self.space_id}:{self.name}"


class SpacePluginCatalogEntry(CommonModel):
    """
    空间插件目录条目：某个插件在某个空间内的统一管理身份卡片，
    覆盖 builtin/bk_plugin/api 三类 plugin_type；api 类型统一覆盖 Uniform API 的
    V2/V3/V4 全部协议版本（来源现场拉取，不经过只服务画布展示缓存的 OpenPluginCatalogIndex），
    承载分类、状态机、推荐与停用/下架/失效信息。

    插件身份三元组 (space_id, plugin_type, source_key, plugin_code) 唯一。
    对外展示的 refCount/nodeCount 等引用统计不落在本表，查询时聚合 TemplatePluginReference。
    """

    space_id = models.IntegerField(_("空间ID"), db_index=True)
    plugin_type = models.CharField(_("插件类型"), max_length=32, choices=PluginType.CHOICES)
    source_key = models.CharField(_("来源标识"), max_length=64, blank=True, default="")
    plugin_code = models.CharField(_("插件标识"), max_length=128)

    directory = models.ForeignKey(
        PluginDirectory,
        verbose_name=_("所属目录"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="entries",
        help_text=_("为空表示未分类"),
    )

    status = models.CharField(
        _("状态"),
        max_length=16,
        choices=PluginCatalogStatus.CHOICES,
        default=PluginCatalogStatus.REVIEW,
        db_index=True,
    )

    recommended = models.BooleanField(_("是否空间推荐"), default=False)
    recommend_order = models.IntegerField(_("推荐顺序"), null=True, blank=True)

    disable_config = models.JSONField(
        _("停用提示配置"),
        default=dict,
        blank=True,
        help_text=_("停用提示文案/联系方式等自定义内容，内部约定字段放在 _meta 命名空间下，如 _meta.pre_invalid_status"),
    )

    replace_plugin = models.ForeignKey(
        "self",
        verbose_name=_("建议替换插件"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replaced_by_set",
    )
    offline_reason = models.CharField(_("下架原因"), max_length=512, blank=True, default="")
    offline_by = models.CharField(_("下架操作人"), max_length=32, blank=True, default="")
    offline_time = models.DateTimeField(_("下架时间"), null=True, blank=True)

    invalid_reason = models.CharField(_("失效原因"), max_length=512, blank=True, default="")
    found_time = models.DateTimeField(_("失效发现时间"), null=True, blank=True)

    source_valid = models.BooleanField(_("来源当前是否仍存在"), default=True)
    last_synced_at = models.DateTimeField(_("最近一次来源同步时间"), null=True, blank=True)
    ever_enabled = models.BooleanField(_("是否曾经进入过可用状态"), default=False)

    class Meta:
        verbose_name = _("空间插件目录条目")
        verbose_name_plural = _("空间插件目录条目")
        app_label = "plugin_catalog"
        unique_together = ("space_id", "plugin_type", "source_key", "plugin_code")
        indexes = [
            models.Index(fields=["space_id", "status"]),
            models.Index(fields=["space_id", "directory"]),
            models.Index(fields=["space_id", "recommended", "recommend_order"]),
        ]

    def __str__(self):
        return f"{self.space_id}:{self.plugin_type}:{self.source_key}:{self.plugin_code}"


class TemplatePluginReference(models.Model):
    """
    流程当前引用插件记录：某个流程的某个节点，在线上版/草稿版里引用了哪个插件身份。
    随流程保存/发布/回滚/删除，在 Interface 同一数据库事务内按 (space_id, template_id, role)
    全量重算（先删后插），不走异步统计任务，避免「流程保存成功但引用没更新」。

    resolved=False 即"无法识别的 API 节点"（旧版 API 插件、身份解析失败），独立展示，
    不计入插件引用计数。
    """

    space_id = models.IntegerField(_("空间ID"), db_index=True)
    template_id = models.BigIntegerField(_("流程模板ID"), db_index=True)
    role = models.CharField(_("版本角色"), max_length=16, choices=TemplatePluginReferenceRole.CHOICES)

    plugin_type = models.CharField(_("插件类型"), max_length=32, choices=PluginType.CHOICES, blank=True, default="")
    source_key = models.CharField(_("来源标识"), max_length=64, blank=True, default="")
    plugin_code = models.CharField(_("插件标识"), max_length=128, blank=True, default="")
    plugin_version = models.CharField(_("插件版本"), max_length=64, blank=True, default="")

    node_id = models.CharField(_("节点ID"), max_length=64)
    node_name = models.CharField(_("节点名称"), max_length=256, blank=True, default="")

    resolved = models.BooleanField(_("是否成功解析插件身份"), default=True)
    unresolved_reason = models.CharField(_("无法识别原因"), max_length=512, blank=True, default="")

    create_time = models.DateTimeField(_("创建时间"), auto_now_add=True)
    update_time = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("流程插件当前引用")
        verbose_name_plural = _("流程插件当前引用")
        app_label = "plugin_catalog"
        unique_together = ("space_id", "template_id", "role", "node_id")
        indexes = [
            models.Index(fields=["space_id", "plugin_type", "source_key", "plugin_code"]),
            models.Index(fields=["space_id", "template_id"]),
        ]

    def __str__(self):
        return f"{self.template_id}:{self.role}:{self.node_id}"


class CatalogChangeType:
    """插件目录变更记录的操作类型。"""

    INITIALIZE = "initialize"
    UPDATE_ENTRY = "update_entry"
    TRANSITION_STATUS = "transition_status"
    UPDATE_DISABLE_CONFIG = "update_disable_config"
    BATCH_CATEGORY = "batch_category"
    BATCH_STATUS = "batch_status"
    BATCH_CLEAN = "batch_clean"
    RECOMMEND = "recommend"
    CANCEL_RECOMMEND = "cancel_recommend"
    DIRECTORY_SAVE = "directory_save"
    DIRECTORY_DELETE = "directory_delete"

    CHOICES = (
        (INITIALIZE, _("初始化插件目录")),
        (UPDATE_ENTRY, _("编辑插件条目")),
        (TRANSITION_STATUS, _("插件状态流转")),
        (UPDATE_DISABLE_CONFIG, _("编辑停用提示配置")),
        (BATCH_CATEGORY, _("批量归类")),
        (BATCH_STATUS, _("批量状态流转")),
        (BATCH_CLEAN, _("批量清理失效记录")),
        (RECOMMEND, _("设为空间推荐")),
        (CANCEL_RECOMMEND, _("取消空间推荐")),
        (DIRECTORY_SAVE, _("保存目录")),
        (DIRECTORY_DELETE, _("删除目录")),
    )


class CatalogChangeSource:
    """变更记录的操作来源：区分人工操作与系统命令，回退核对时便于区分责任。"""

    WEB = "web"
    APIGW = "apigw"
    COMMAND = "command"

    CHOICES = (
        (WEB, _("管理前端")),
        (APIGW, _("对外网关")),
        (COMMAND, _("初始化命令")),
    )


class CatalogChangeRecord(BaseOperateRecord):
    """
    插件目录变更记录：谁在什么时候把什么改成了什么。

    按设计文档要求「只写不读」：本期不提供查询接口、不新增审计页面
    （文档明确"不新增审计页面"），数据用于排障追溯与上线回退时的差异核对，可直接查表消费。

    与 `SpacePluginCatalogEntry` 上的 `updated_by` / `offline_by` 的区别：那些字段只保留
    **最后一次**修改者，这里保留**每一次**变更的前后值（before_value / after_value）。
    """

    operate_type = models.CharField(_("操作类型"), max_length=64, choices=CatalogChangeType.CHOICES)
    operate_source = models.CharField(_("操作来源"), max_length=64, choices=CatalogChangeSource.CHOICES)

    space_id = models.IntegerField(_("空间ID"), db_index=True)

    before_value = models.JSONField(_("变更前值"), default=dict, blank=True, null=True)
    after_value = models.JSONField(_("变更后值"), default=dict, blank=True, null=True)

    method = models.CharField(_("操作方法"), max_length=128, blank=True, default="")
    reason = models.CharField(_("变更原因"), max_length=512, blank=True, default="")
    request_id = models.CharField(_("请求ID"), max_length=128, blank=True, default="")

    class Meta:
        verbose_name = _("插件目录变更记录")
        verbose_name_plural = _("插件目录变更记录")
        app_label = "plugin_catalog"
        indexes = [
            models.Index(fields=["space_id", "instance_id", "operate_date"]),
        ]

    def __str__(self):
        return f"{self.space_id}:{self.operate_type}:{self.instance_id}:{self.operator}"
