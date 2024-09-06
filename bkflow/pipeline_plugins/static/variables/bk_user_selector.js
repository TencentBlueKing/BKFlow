
(function () {
    $.atoms.bk_manage_user_selector = [
        {
            tag_code: "bk_user_selector",
            type: "member_selector",
            attrs: {
                name: gettext("选择人员"),
                placeholder: gettext("多个用英文逗号 `,` 分隔"),
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
