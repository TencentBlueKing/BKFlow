(function () {
    $.atoms.bk_notify = [
        {
            tag_code: "bk_notify_types",
            type: "checkbox",
            attrs: {
                name: gettext("通知方式"),
                hookable: true,
                items: [],
                default: [],
                validation: [
                    {
                        type: "required"
                    }
                ]
            },
            methods: {
                _tag_init: function () {
                    let self = this;
                    let url = $.context.get('site_url') + 'get_msg_types/';
                    $.ajax({
                        url: url,
                        type: 'GET',
                        dataType: 'json',
                        success: function (resp) {
                            if (!resp.result) {
                                show_msg(resp.message, 'error');
                            } else {
                                let data = resp.data.filter(function (item) {
                                    return item.is_active
                                });
                                let items = data.map(function (item) {
                                    return {"name": item.label, "value": item.type}
                                });
                                if (items.length > 0) {
                                    self.items = items;
                                }
                            }
                        },
                        error: function (resp) {
                            show_msg(resp.message, 'error');
                        }
                    })
                }
            }
        },
        {
            tag_code: "bk_notify_receivers",
            type: "member_selector",
            attrs: {
                name: gettext("选择人员"),
                placeholder: gettext("多个用英文逗号 `,` 分隔"),
                hookable: true,
                validation: [
                    {
                        type: "required"
                    }
                ],
                hookable: true,
            }
        },
        {
            tag_code: "notify_executor",
            type: "radio",
            attrs: {
                name: gettext("通知执行人"),
                items: [
                    {value: true, name: gettext("是")},
                    {value: false, name: gettext("否")},
                ],
                default: false,
                hookable: true,
            }
        },
        {
            tag_code: "bk_notify_title",
            type: "input",
            attrs: {
                name: gettext("通知主题"),
                hookable: true,
                validation: [
                    {
                        type: "required"
                    }
                ]
            }
        },
        {
            tag_code: "bk_notify_content",
            type: "textarea",
            attrs: {
                name: gettext("通知内容"),
                hookable: true,
                validation: [
                    {
                        type: "required"
                    }
                ]
            }
        }
    ]
})();
