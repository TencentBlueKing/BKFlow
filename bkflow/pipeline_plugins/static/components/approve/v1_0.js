
(function () {
    $.atoms.bk_approve = [
        {
            tag_code: "bk_verifier",
            type: "input",
            attrs: {
                name: gettext("审核人"),
                hookable: true,
                placeholder: gettext("多个审核人，请用英文`,`分隔"),
                validation: [
                    {
                        type: "required"
                    }
                ]
            }
        },
        {
            tag_code: "bk_approve_title",
            type: "input",
            attrs: {
                name: gettext("审核标题"),
                hookable: true,
                validation: [
                    {
                        type: "required"
                    }
                ]
            }
        },
        {
            tag_code: "bk_approve_content",
            type: "textarea",
            attrs: {
                name: gettext("审核内容"),
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
