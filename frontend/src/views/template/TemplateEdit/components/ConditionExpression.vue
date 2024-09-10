<template>
  <div class="condition-expression">
    <template v-if="parseLang === 'MAKO'">
      <p>{{ $t('makoOperates') }}</p>
      <p>{{ $t('支持 "and、or、not、True、False" 等 MAKO 关键字语法') }}</p>
      <br>
      <p>{{ $t('支持直接引用全局变量') }}</p>
      <p>{{ $t('使用内置函数、datetime、re、hashlib、random、time、os.path模块处理全局变量') }}</p>
      <br>
      <p>{{ $t('示例：') }}</p>
      <p>{{ $t('假设 key 是值为 "3" 的全局变量') }}</p>
      <p>{{ $t('字符串比较：') }}<code class="code">key == "3"</code></p>
      <p>{{ $t('数值比较：') }}<code class="code">int(key) >= 3</code></p>
      <p>{{ $t('包含：') }}<code class="code">int(key) in (1,2,3)</code></p>
    </template>
    <template v-else-if="parseLang === 'FEEL'">
      <p>{{ $t('feelOperates') }}</p>
      <p>{{ $t('支持 "and、or、true、false" 等关键字语法') }}</p>
      <p>{{ $t('支持 FEEL (Friendly Enough Expression Language) 基础语法') }}</p>
      <br>
      <p>{{ $t('支持使用全局变量，如') }}<code class="code">${key}</code>、<code class="code">${int(key)}</code></p>
      <p>{{ $t('${}中支持使用内置函数、datetime、re、hashlib、random、time、os.path模块处理全局变量') }}</p>
      <br>
      <p>{{ $t('示例：') }}</p>
      <p>{{ $t('字符串比较：') }}<code class="code">"${key}" = "my string"</code></p>
      <p>{{ $t('数值比较：') }}<code class="code">${int(key)} >= 3</code></p>
      <p>{{ $t('包含：') }}<code class="code">list contains([1, 2, 3], ${int(key)})</code></p>
    </template>
    <template v-else>
      <p>{{ $t('makoOperates') }}</p>
      <p>{{ $t('支持 "and、or、True/true、False/false" 等关键字语法') }}</p>
      <p>
        {{ $t('表达式更多细节请参考') }}
        <bk-link
          theme="primary"
          href="https://boolrule.readthedocs.io/en/latest/expressions.html#basic-comparison-operators"
          target="_blank">
          {{ 'boolrule' }}
        </bk-link>
      </p>
      <br>
      <p>{{ $t('支持使用全局变量，如') }}<code class="code">${key}</code>、<code class="code">${int(key)}</code></p>
      <p>{{ $t('支持使用内置函数、datetime、re、hashlib、random、time、os.path模块处理全局变量') }}</p>
      <br>
      <p>{{ $t('示例：') }}</p>
      <p>{{ $t('字符串比较：') }}<code class="code">"${key}" == "my string"</code></p>
      <p>{{ $t('数值比较：') }}<code class="code">${int(key)} >= 3</code></p>
      <p>{{ $t('包含：') }}<code class="code">${key} in (1,2,3)</code></p>
    </template>
  </div>
</template>
<script>
export default {
  name: 'ConditionExpression',
  props: {
    parseLang: {
      type: String,
      default: '',
    },
  },
};
</script>
<style lang="scss" scoped>
  .condition-expression {
    font-size: 12px;
    color: #b8b8b8;
    margin-bottom: 10px;
    /deep/.bk-link {
      vertical-align: initial;
      .bk-link-text {
        font-size: 12px;
      }
    }
    .code {
      background-color: #eff1f3;
      color: #9e938a;
      border-radius: 4px;
      padding: 0 4px;
      margin: 0 2px;
      font: 0.85em/1.8 ui-monospace,SFMono-Regular,SF Mono,Menlo,Consolas,Liberation Mono,monospace;
    }
  }
</style>
