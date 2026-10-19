from bkflow.pipeline_plugins.query.utils import QueryResponseError, query_response_handler


def test_query_response_handler_serializes_structured_error():
    """结构化业务错误应返回稳定错误码和上下文。"""

    @query_response_handler
    def view():
        raise QueryResponseError(
            "插件详情不可用",
            error_code="PLUGIN_DETAIL_UNAVAILABLE",
        )

    response = view()

    assert response.data == {
        "result": False,
        "message": "插件详情不可用",
        "data": None,
        "error_code": "PLUGIN_DETAIL_UNAVAILABLE",
    }


def test_query_response_handler_keeps_legacy_error_envelope():
    """普通异常应保持原有三字段失败响应。"""

    @query_response_handler
    def view():
        raise ValueError("legacy failure")

    response = view()

    assert response.data == {"result": False, "message": "legacy failure", "data": None}
