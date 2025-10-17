# -*- coding: utf-8 -*-
import abc


class BaseFileHandler(abc.ABC):

    def __init__(self, file):
        self.file = file

    @abc.abstractmethod
    def handle(self):
        raise NotImplementedError
