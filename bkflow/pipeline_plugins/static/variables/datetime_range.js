
(function () {
    $.atoms.datetime_range = [
        {
            tag_code: "datetime_range",
            type: "datetime_range",
            attrs: {
                name: gettext("日期时间范围"),
                hookable: true,
                validation: [
                    {
                        type: "required"
                    }
                ]
            }
        },
    ]
})();
