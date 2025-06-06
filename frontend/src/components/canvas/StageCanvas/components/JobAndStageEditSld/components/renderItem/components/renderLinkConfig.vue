<template>
  <div class="render-link-config">
    <bk-form
      ref="configForm"
      :model="renderDataSync"
      :rules="rules">
      <bk-form-item
        property="url"
        label="超链接"
        required>
        <bk-input
          v-model="currentUrlSuffix"
          style="margin-top: 8px;"
          :clearable="false"
          :font-size="'medium'"
          :disabled="!editable">
          <bk-dropdown-menu
            ref="dropdown"
            slot="prepend"
            class="group-text"
            :font-size="'medium'"

            @show="dropdownShowToggle(true)"
            @hide="dropdownShowToggle(false)">
            <bk-button
              slot="dropdown-trigger"
              type="primary"
              :disabled="!editable">
              <span style="width: 50px;display: block;text-align: right;">{{ currentUrlPrefix }}</span>
              <i :class="['bk-icon icon-angle-down',{'icon-flip': isDropdownShow}]" />
            </bk-button>
            <ul
              slot="dropdown-content"
              class="bk-dropdown-list">
              <li
                v-for="item in linkUrlPrefixConfig"
                :key="item.value"
                class="prefix-config-item"
                :class="{
                  disabled:!editable
                }"
                @click="editable&&toggleUrlPrefix(item.value)">
                <span>
                  {{ item.value }}
                </span>
              </li>
            </ul>
          </bk-dropdown-menu>
        </bk-input>
      </bk-form-item>
    </bk-form>
  </div>
</template>

<script>
export default {
    name: 'RenderLinkConfig',
    props: {
        renderData: {
            type: Object,
            required: true,
        },
        editable: {
          type: Boolean,
          default: false,
      },
    },
    data() {
        return {
            isDropdownShow: false,
            linkUrlPrefixConfig: [
                {
                    value: 'http://',
                },
                {
                    value: 'https://',
                },
            ],
            rules: {
              url: [
                  {
                    trigger: 'blur',
                    message: '请输入有效的链接',
                    validator: () => !!this.currentUrlSuffix,
                  },
                ],
            },
        };
    },
    computed: {
        renderDataSync: {
            get() {
                return this.renderData;
            },
            set(value) {
                this.$emit('update:renderData', value);
            },
        },
        currentUrlPrefix: {
            get() {
                return this.getUrlPrefix(this.renderDataSync.url) || this.linkUrlPrefixConfig[0].value;
            },
            set(value) {
                this.renderDataSync.url = this.replaceUrlPrefix(this.renderDataSync.url, value);
            },
        },
        currentUrlSuffix: {
            get() {
                return this.getUrlSuffix(this.renderDataSync.url);
            },
            set(value) {
                this.renderDataSync.url = this.currentUrlPrefix + value;
            },
        },
    },
    created() {
        if (!this.renderDataSync.url) {
            this.$set(this.renderDataSync, 'url', this.linkUrlPrefixConfig[0].value);
        }
    },
    methods: {
        async validate() {
            return await this.$refs.configForm.validate();
        },
        dropdownShowToggle(value) {
            this.isDropdownShow = value;
        },
        getUrlPrefixRegex() {
            // 根据配置动态生成正则表达式
            const prefixPatterns = this.linkUrlPrefixConfig.map(item => item.value.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&')).join('|');
            return new RegExp(`^(${prefixPatterns})`, 'i');
        },
        getUrlPrefix(url) {
          const regex = this.getUrlPrefixRegex();
          const match = url.match(regex);

          return match ? match[0] : null;
        },
        replaceUrlPrefix(url, newPrefix) {
          const regex = this.getUrlPrefixRegex();
          console.log('renderLinkConfig.vue_Line:117', regex.test(url), newPrefix, url.replace(regex, newPrefix));
          // 检查URL是否匹配任一前缀
          if (!regex.test(url)) {
            return url.replace('', newPrefix); // 如果不匹配任何前缀，则前插前缀
          }
          // 替换前缀
          return url.replace(regex, newPrefix);
        },
        toggleUrlPrefix(newPrefix) {
           this.currentUrlPrefix = newPrefix;
           this.$refs.dropdown.hide();
        },
        getUrlSuffix(url) {
          const lowerUrl = url.toLowerCase();
          // 没有匹配的前缀，返回原始内容
          return this.linkUrlPrefixConfig.reduce((res, item) => {
            const lowerPrefix = item.value.toLowerCase();
            if (lowerUrl.startsWith(lowerPrefix)) {
              return url.slice(item.value.length);
            }
                return res;
          }, null) ?? url;
        },

    },
};
</script>

<style lang="scss" scoped>
.render-link-config {
    .bk-dropdown-list{
        .prefix-config-item{
            line-height: 36px;
            padding: 0px 16px;
            cursor: pointer;
            &.disabled{
              cursor: not-allowed;
            }
            &:hover{
                background-color: #f0f1f5;
                color: #3A83FF;
            }
        }
    }
}
</style>
