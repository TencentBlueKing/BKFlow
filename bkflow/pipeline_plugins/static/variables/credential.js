
(function () {
    $.atoms.credential = [
        {
            tag_code: "credential_meta",
            type: "combine",
            attrs: {
                name: gettext("表格"),
                hookable: true,
                children: [
                    {
                        tag_code: "credential_type",
                        type: "select",
                        attrs: {
                            name: gettext("凭证类型"),
                            hookable: true,
                            items: [
                                {
                                    text: gettext("蓝鲸应用凭证"),
                                    value: "BK_APP"
                                },
                                {
                                    text: gettext("蓝鲸 Access Token 凭证"),
                                    value: "BK_ACCESS_TOKEN"
                                },
                                {
                                    text: gettext("Basic Auth"),
                                    value: "BASIC_AUTH"
                                },
                                {
                                    text: gettext("自定义"),
                                    value: "CUSTOM"
                                }
                            ],
                            value: "BK_APP",
                            validation: [
                                {
                                    type: "required"
                                }
                            ]
                        }
                    },
                    {
                        tag_code: "type",
                        type: "checkbox",
                        attrs: {
                            name: gettext("引用凭证"),
                            hookable: true,
                            items: [{value: "0"}],
                            value: ["0"],
                            validation: [
                                {
                                    type: "required"
                                }
                            ]
                        }
                    }
                ]
            }

        },
        {
            tag_code: "credential",
            meta_transform: function (variable) {
                let metaConfig = variable.value;
                let remote = false;
                let remote_url = "";
                let items = [];
                let placeholder = '';
                // if (metaConfig.datasource === "1") {
                //     remote_url = $.context.get('site_url') + 'api/plugin_query/variable_select_source_data_proxy/?url=' + metaConfig.items_text;
                //     remote = true;
                // }
                if (metaConfig.datasource === "0") {
                    try {
                        items = JSON.parse(metaConfig.items_text);
                    } catch (err) {
                        items = [];
                        placeholder = gettext('非法下拉框数据源，请检查您的配置');
                    }
                    if (!(items instanceof Array)) {
                        items = [];
                        placeholder = gettext('非法下拉框数据源，请检查您的配置');
                    }
                }

                let multiple = false;
                let default_val = metaConfig.default || '';

                // if (metaConfig.type === "1") {
                //     multiple = true;
                //     default_val = [];
                //     if (metaConfig.default) {
                //         let vals = metaConfig.default.split(',');
                //         for (let i in vals) {
                //             default_val.push(vals[i].trim());
                //         }
                //     }
                // }
                return {
                    tag_code: this.tag_code,
                    type: "select",
                    attrs: {
                        name: gettext("下拉框"),
                        hookable: true,
                        items: items,
                        multiple: multiple,
                        value: default_val,
                        remote: remote,
                        remote_url: remote_url,
                        placeholder: placeholder,
                        remote_data_init: function (data) {
                            return data;
                        },
                        validation: [
                            {
                                type: "required"
                            }
                        ]
                    }
                }
            }
        }
    ]
})();
