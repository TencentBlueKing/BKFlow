(function () {
    $.atoms.python_code = [
        {
            tag_code: "bk_input_vars",
            type: "field_mappings",
            attrs: {
                name: gettext("输入变量"),
                hookable: false,
                default: {
                    arg1: "",
                    arg2: ""
                }
            }
        },
        {
            tag_code: "bk_python_code",
            type: "code_editor",
            attrs: {
                name: gettext("Python代码"),
                default: gettext('"""\n函数说明：\n1. 必须定义 main 函数，函数签名可以根据实际需要自定义参数\n2. 函数返回值将作为节点的输出结果\n\n- 代码执行有超时限制（默认10秒）\n- 只能使用安全的Python内置函数\n"""\n\ndef main(arg1: str, arg2: str):\n    # 在这里编写你的代码逻辑\n    result = arg1 + arg2\n    \n    # 返回结果\n    return {\n        "result": result\n    }'),
                hookable: false,
                language: "python",
                height: "400px",
                showLanguageSwitch: false,
                validation: [
                    {
                        type: "required"
                    }
                ]
            }
        },
    ]
})();
