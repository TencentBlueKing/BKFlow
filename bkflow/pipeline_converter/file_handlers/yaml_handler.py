# -*- coding: utf-8 -*-

import logging

import yaml

from bkflow.pipeline_converter.file_handlers.base import BaseFileHandler

logger = logging.getLogger(__name__)


class YamlFileHandler(BaseFileHandler):
    def handle(self):
        try:
            yaml_content = yaml.safe_load(self.file)
            return yaml_content
        except yaml.YAMLError as e:
            logger.exception(f"YAML解析失败: {str(e)}")
            raise ValueError(f"YAML解析失败: {str(e)}")
