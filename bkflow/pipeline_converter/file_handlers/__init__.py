# -*- coding: utf-8 -*-
import logging
import os

from .json_handler import JsonFileHandler
from .yaml_handler import YamlFileHandler

logger = logging.getLogger(__name__)


class FileHandlerDispatcher:
    def __init__(self, file):
        self.file = file

    def dispatch(self):
        handler_map = {
            ".json": JsonFileHandler,
            ".yaml": YamlFileHandler,
        }

        try:
            _, file_ext = os.path.splitext(self.file.name)
            handler_class = handler_map[file_ext]
        except KeyError:
            logger.exception("Unsupported file type")
            raise ValueError("Unsupported file type")

        return handler_class(self.file)
