# -*- coding: utf-8 -*-
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


import datetime
import os
import re

from django.conf import settings
from django.utils import timezone, translation
from django.utils.translation import ugettext_lazy as _
from pipeline.component_framework.component import Component
from pipeline.core.flow.activity import StaticIntervalGenerator
from pipeline.core.flow.io import BooleanItemSchema, StringItemSchema

from bkflow.pipeline_plugins.components.collections.base import BKFlowBaseService

__group_name__ = _("蓝鲸服务(BK)")


class SleepTimerService(BKFlowBaseService):
    __need_schedule__ = True
    interval = StaticIntervalGenerator(0)
    BK_TIMEMING_TICK_INTERVAL = int(os.getenv("BK_TIMEMING_TICK_INTERVAL", 60 * 60 * 24))
    #  匹配年月日 时分秒 正则 yyyy-MM-dd HH:mm:ss
    date_regex = re.compile(
        r"%s %s"
        % (
            r"^(((\d{3}[1-9]|\d{2}[1-9]\d{1}|\d{1}[1-9]\d{2}|[1-9]\d{3}))|"
            r"(29/02/((\d{2})(0[48]|[2468][048]|[13579][26])|((0[48]|[2468][048]|[3579][26])00))))-"
            r"((0[13578]|1[02])-((0[1-9]|[12]\d|3[01]))|"
            r"((0[469]|11)-(0[1-9]|[12]\d|30))|(02)-(0[1-9]|[1]\d|2[0-8]))",
            r"((0|[1])\d|2[0-3]):(0|[1-5])\d:(0|[1-5])\d$",
        )
    )

    seconds_regex = re.compile(r"^\d+$")

    def inputs_format(self):
        return [
            self.InputItem(
                name=_("定时时间"),
                key="bk_timing",
                type="string",
                schema=StringItemSchema(description=_("定时时间，格式为秒(s) 或 (%%Y-%%m-%%d %%H:%%M:%%S)")),
            ),
            self.InputItem(
                name=_("是否强制晚于当前时间"),
                key="force_check",
                type="boolean",
                schema=BooleanItemSchema(
                    description=_("用户输入日期格式时是否强制要求时间晚于当前时间，只对日期格式定时输入有效")
                ),
            ),
        ]

    def outputs_format(self):
        return []

    def plugin_execute(self, data, parent_data):
        if parent_data.get_one_of_inputs("language"):
            translation.activate(parent_data.get_one_of_inputs("language"))

        timing = data.get_one_of_inputs("bk_timing")
        force_check = data.get_one_of_inputs("force_check", True)
        # todo 需要考虑是否要支持空间的时区配置
        # 项目时区获取
        tz = timezone.pytz.timezone(settings.TIME_ZONE)
        data.outputs.business_tz = tz

        now = datetime.datetime.now(tz=tz)
        if self.date_regex.match(str(timing)):
            eta = tz.localize(datetime.datetime.strptime(timing, "%Y-%m-%d %H:%M:%S"))
            if force_check and now > eta:
                message = _("定时时间需晚于当前时间")
                data.set_outputs("ex_data", message)
                return False
        elif self.seconds_regex.match(str(timing)):
            #  如果写成+号 可以输入无限长，或考虑前端修改
            eta = now + datetime.timedelta(seconds=int(timing))
        else:
            message = _("输入参数%s不符合【秒(s) 或 时间(%%Y-%%m-%%d %%H:%%M:%%S)】格式") % timing
            data.set_outputs("ex_data", message)
            return False

        self.logger.info("planning time: {}".format(eta))
        data.outputs.timing_time = eta

        return True

    def plugin_schedule(self, data, parent_data, callback_data=None):
        timing_time = data.outputs.timing_time

        business_tz = data.outputs.business_tz

        now = datetime.datetime.now(tz=business_tz)
        t_delta = timing_time - now
        if t_delta.total_seconds() < 1:
            self.finish_schedule()

        # 如果定时时间距离当前时间的时长大于唤醒消息的有效期，则设置下一次唤醒时间为消息有效期之内的时长
        # 避免唤醒消息超过消息的有效期被清除，导致定时节点永远不会被唤醒
        if t_delta.total_seconds() > self.BK_TIMEMING_TICK_INTERVAL > 60 * 5:
            self.interval.interval = self.BK_TIMEMING_TICK_INTERVAL - 60 * 5
            wake_time = now + datetime.timedelta(seconds=self.interval.interval)
            self.logger.info("wake time: {}".format(wake_time))

            return True

        # 这里减去 0.5s 的目的是尽可能的减去 execute 执行带来的误差
        self.interval.interval = t_delta.total_seconds() - 0.5
        self.logger.info("wake time: {}".format(timing_time))
        return True


class SleepTimerComponent(Component):
    name = _("定时")
    code = "sleep_timer"
    bound_service = SleepTimerService
    form = settings.STATIC_URL + "components/sleep_time/legacy.js"
