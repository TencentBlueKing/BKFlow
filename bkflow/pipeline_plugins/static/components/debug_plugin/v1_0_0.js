
(function () {
    $.atoms.debug_plugin = [
        {
            tag_code: "string_input",
            type: "input",
            attrs: {
                name: "string_input",
                hookable: true,
            }
        },
        {
            tag_code: "int_input",
            type: "int",
            attrs: {
                name: "int_input",
                hookable: true,
            }
        },
        {
            tag_code: "boolean_input",
            type: "radio",
            attrs: {
                name: "boolean_input",
                hookable: true,
                items: [
                    {value: true, name: "true"},
                    {value: false, name: "false"}
                ],
                default: true,
                validation: [
                    {
                        type: "required"
                    }
                ]
            }
        },
        {
            tag_code: "object_input",
            type: "code_editor",
            attrs: {
                name: "object_input",
                hookable: true,
                height: "400px",
                language: "json",
                default: "{}"
            }
        },
    ]
})();
