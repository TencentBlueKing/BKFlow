# -*- coding: utf-8 -*-
import pytest

from bkflow.pipeline_converter.constants import DataTypes
from bkflow.pipeline_converter.converters.base import BaseConverter
from bkflow.pipeline_converter.hub import ConverterHub


class TestBaseConverter:
    source_type = DataTypes.JSON.value
    target_type = DataTypes.DATA_MODEL.value

    def test_subclass_initialization_success(self):

        class ChildConverter(BaseConverter):
            source = self.source_type
            target = self.target_type

            def convert(self):
                self.target_data = "test"

        child_converter = ChildConverter(source_data="ttt")
        child_converter.convert()
        assert child_converter.source == self.source_type
        assert child_converter.target == self.target_type
        assert child_converter.target_data == "test"

        assert len(ConverterHub.get_converters(self.source_type, self.target_type)) == 1

    def test_subclass_initialization_fail(self):
        with pytest.raises(TypeError):

            class ChildConverter(BaseConverter):
                def convert(self):
                    self.target_data = "test"
