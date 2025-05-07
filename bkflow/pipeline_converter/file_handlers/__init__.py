# -*- coding: utf-8 -*-

from .json_handler import JsonFileHandler


class FileHandlerDispatcher:
    def __init__(self, file):
        self.file = file

    def dispatch(self):
        if self.file.name.endswith(".json"):
            handler = JsonFileHandler(self.file)
        else:
            raise ValueError("Unsupported file type")
        return handler
