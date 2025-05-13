# -*- coding: utf-8 -*-

import yaml

from bkflow.pipeline_converter.file_handlers.base import BaseFileHandler


class YamlFileHandler(BaseFileHandler):
    def handle(self):
        try:
            yaml_content = yaml.safe_load(self.file)
            return yaml_content
        except yaml.YAMLError as e:
            raise ValueError(f"YAML解析失败: {str(e)}")
        except Exception as e:
            raise ValueError(f"处理YAML文件时出错: {str(e)}")
