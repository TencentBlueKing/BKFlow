(function () {
    $.atoms.password = [
        {
            tag_code: "password",
            type: "password",
            attrs: {
                name: gettext("密码"),
                hookable: true,
                // TODO 如果是 false，应该是允许输密码？
                canUseVar: false,
                validation: [
                    {
                        type: "required"
                    }
                ]
            }
        },
    ];
})();