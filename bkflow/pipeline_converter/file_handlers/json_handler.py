# -*- coding: utf-8 -*-
import json
import logging

from bkflow.pipeline_converter.file_handlers.base import BaseFileHandler

logger = logging.getLogger(__name__)


class JsonFileHandler(BaseFileHandler):
    def handle(self):
        try:
            # 假设self.file是文件对象，读取内容并解析为JSON
            json_str = self.file.read().decode("utf-8")
            data = json.loads(json_str)
            return data
        except json.JSONDecodeError as e:
            # 处理JSON解析错误
            logger.exception(f"JSON解析失败: {str(e)}")
            raise ValueError(f"JSON解析失败: {str(e)}")
