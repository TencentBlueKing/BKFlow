
(function () {
    $.atoms.int = [
        {
            tag_code: "int",
            type: "int",
            attrs: {
                name: gettext("整数"),
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
