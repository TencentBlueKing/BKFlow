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


from .apis.bk_login import CollectionsBkLogin
from .apis.bk_paas import CollectionsBkPaas
from .apis.cc import CollectionsCC
from .apis.cmsi import CollectionsCMSI
from .apis.esb import CollectionsEsb
from .apis.gse import CollectionsGSE
from .apis.itsm import CollectionsItsm
from .apis.job import CollectionsJOB
from .apis.jobv3 import CollectionsJOBV3
from .apis.monitor import CollectionsMonitor
from .apis.nodeman import CollectionsNodeMan
from .apis.sops import CollectionsSOPS
from .apis.usermanage import CollectionsUserManage

# Available components
AVAILABLE_COLLECTIONS = {
    "bk_login": CollectionsBkLogin,
    "bk_paas": CollectionsBkPaas,
    "cc": CollectionsCC,
    "cmsi": CollectionsCMSI,
    "gse": CollectionsGSE,
    "job": CollectionsJOB,
    "jobv3": CollectionsJOBV3,
    "sops": CollectionsSOPS,
    "esb": CollectionsEsb,
    "usermanage": CollectionsUserManage,
    "nodeman": CollectionsNodeMan,
    "itsm": CollectionsItsm,
    "monitor": CollectionsMonitor,
}
