
(function() {
    $.atoms.sleep_timer = [
        {
            tag_code: "bk_timing",
            type: "input",
            attrs: {
                name: gettext("定时时间"),
                placeholder: gettext("秒(s) 或 时间(%Y-%m-%d %H:%M:%S)"),
                hookable: true,
                validation: [
                    {
                        type: "required"
                    },
                ]
            },
        },
        {
            tag_code: "force_check",
            type: "radio",
            attrs: {
                name: gettext("强制晚于当前时间"),
                hookable: true,
                items: [
                    {value: true, name: gettext("是")},
                    {value: false, name: gettext("否")}
                ],
                default: true,
                validation: [
                    {
                        type: "required"
                    }
                ]
            }
        }
    ]
})();
