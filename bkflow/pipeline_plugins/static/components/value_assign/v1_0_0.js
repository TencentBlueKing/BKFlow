
(function () {
    $.atoms.value_assign = [
        {
            tag_code: "bk_assignment_list",
            type: "datatable",
            attrs: {
                pagination: true,
                name: gettext("赋值变量或常量与被赋值变量列表"),
                hookable: true,
                add_btn: true,
                empty_text: gettext("赋值变量或常量与被赋值变量的映射列表，一行填写一个映射"),
                columns: [
                    {
                        tag_code: "bk_assign_source_var",
                        type: "textarea",
                        attrs: {
                            name: gettext("赋值变量或常量"),
                        }
                    },
                    {
                        tag_code: "bk_assgin_target_var",
                        type: "textarea",
                        attrs: {
                            name: gettext("被赋值变量"),
                        }
                    },
                ]
            }
        }
    ]
})();