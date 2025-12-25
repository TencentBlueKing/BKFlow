from bkflow.utils.err_code import ERROR, SUCCESS, VALIDATION_ERROR, ErrorCode


class TestErrorCode:
    def test_error_code(self):
        """Test ErrorCode initialization and constants"""
        # Initialization
        err = ErrorCode(code="100", description="Test Error")
        assert err.code == 100
        assert err.description == "Test Error"

        err = ErrorCode(code=200, description="Success")
        assert err.code == 200

        # Constants
        assert SUCCESS.code == 0
        assert SUCCESS.description == "success"
        assert VALIDATION_ERROR.code == 400
        assert VALIDATION_ERROR.description == "validation error"
        assert ERROR.code == 500
        assert ERROR.description == "unknow error"

        # Comparison
        err1 = ErrorCode(code="200", description="OK")
        err2 = ErrorCode(code=200, description="Success")
        assert err1.code == err2.code
