
(function () {
    $.atoms.bk_http_request = [
        {
            tag_code: "bk_http_request_method",
            type: "select",
            attrs: {
                name: gettext("请求方式"),
                hookable: true,
                items: [
                    { text: "GET", value: "GET" },
                    { text: "POST", value: "POST" },
                    { text: "PUT", value: "PUT" },
                    { text: "DELETE", value: "DELETE" },
                    { text: "PATCH", value: "PATCH" },
                    { text: "HEAD", value: "HEAD" },
                    { text: "CONNECT", value: "CONNECT" },
                    { text: "OPTIONS", value: "OPTIONS" },
                    { text: "TRACE", value: "TRACE" },
                ],
                default: "GET"
            },
        },
        {
            tag_code: "bk_http_request_url",
            type: "input",
            attrs: {
                name: "URL",
                hookable: true,
                validation: [
                    {
                        type: "required"
                    }
                ]
            }
        },
        {
            tag_code: "bk_http_request_header",
            type: "datatable",
            attrs: {
                pagination: true,
                name: "Header",
                hookable: true,
                add_btn: true,
                empty_text: gettext("请求头，一行填写一个头部的信息"),
                columns: [
                    {
                        tag_code: "name",
                        type: "textarea",
                        attrs: {
                            name: "Header",
                        }
                    },
                    {
                        tag_code: "value",
                        type: "textarea",
                        attrs: {
                            name: "Value",
                        }
                    },
                ]
            }
        },
        {
            tag_code: "bk_http_request_body",
            type: "textarea",
            attrs: {
                name: "Body",
                hookable: true
            }
        },
        {
            tag_code: "bk_http_timeout",
            type: "int",
            attrs: {
                name: gettext("超时时间"),
                hookable: true,
                placeholder: gettext("请求超时时间"),
                min: 0,
                max: 60,
                default: 5
            }
        },
        {
            tag_code: "bk_http_success_exp",
            type: "textarea",
            attrs: {
                name: gettext("成功条件"),
                hookable: true,
                placeholder: gettext("根据返回的 JSON 的数据来控制节点的成功或失败，使用 resp 引用返回的 JSON 对象，例 resp.result==True")
            }
        }
    ]
})();
