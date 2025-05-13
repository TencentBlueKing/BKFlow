# -*- coding: utf-8 -*-
import os

from .json_handler import JsonFileHandler
from .yaml_handler import YamlFileHandler


class FileHandlerDispatcher:
    def __init__(self, file):
        self.file = file

    def dispatch(self):
        handler_map = {
            ".json": JsonFileHandler,
            ".yaml": YamlFileHandler,
        }

        try:
            file_ext = os.path.splitext(self.file.name)[1]
            handler_class = handler_map[file_ext]
            return handler_class(self.file)
        except KeyError:
            raise ValueError("Unsupported file type")
