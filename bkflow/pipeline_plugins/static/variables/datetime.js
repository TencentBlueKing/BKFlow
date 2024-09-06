
(function () {
    $.atoms.datetime = [
        {
            tag_code: "datetime",
            type: "datetime",
            attrs: {
                name: gettext("日期时间"),
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
