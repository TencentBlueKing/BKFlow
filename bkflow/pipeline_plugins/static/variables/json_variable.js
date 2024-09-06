
(function () {
    $.atoms.json_variable = [
        {
            tag_code: "json_variable",
            type: "textarea",
            attrs: {
                name: gettext("JSON 变量"),
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
