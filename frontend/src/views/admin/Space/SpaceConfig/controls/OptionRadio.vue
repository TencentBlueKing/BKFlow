<template>
  <div class="option-radio-wrap">
    <bk-radio-group
      class="option-radio"
      :value="value"
      @change="val => $emit('change', val)">
      <bk-radio
        v-for="opt in options"
        :key="opt.value"
        :value="opt.value"
        class="option-item">
        <span class="option-label">{{ opt.label }}{{ opt.desc ? ':' : '' }}</span>
        <span
          v-if="opt.desc"
          class="option-desc">{{ opt.desc }}</span>
      </bk-radio>
    </bk-radio-group>
    <transition
      name="option-guide-fade"
      mode="out-in">
      <div
        v-if="currentGuide"
        :key="value"
        class="option-guide">
        <div class="guide-card">
          <div class="guide-card-title">
            <span>{{ $t('语法要点') }} · {{ currentGuide.title }}</span>
          </div>
          <div
            v-for="(row, idx) in currentGuide.syntax"
            :key="idx"
            class="guide-syntax-row">
            <div class="guide-syntax-label">
              {{ row.label }}
            </div>
            <div class="guide-syntax-values">
              <span
                v-for="(token, tIdx) in row.tokens"
                :key="tIdx"
                class="guide-token">
                {{ token }}
              </span>
              <span
                v-if="row.text"
                class="guide-syntax-text">
                {{ row.text }}
              </span>
            </div>
          </div>
        </div>
        <div
          v-if="currentGuide.warning"
          class="guide-warning">
          <i class="bk-icon icon-exclamation-circle-shape guide-warning-icon" />
          <span class="guide-warning-text">
            <span class="guide-warning-label">{{ $t('风险提示') }}：</span>{{ currentGuide.warning }}
          </span>
        </div>
        <div
          v-if="currentGuide.examples && currentGuide.examples.length"
          class="guide-examples">
          <div class="guide-examples-title">
            {{ $t('常用示例') }}
          </div>
          <table class="guide-examples-table">
            <thead>
              <tr>
                <th class="col-scene">
                  {{ $t('场景') }}
                </th>
                <th>{{ $t('表达式') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(ex, idx) in currentGuide.examples"
                :key="idx">
                <td class="col-scene">
                  {{ ex.scene }}
                </td>
                <td>
                  {{ ex.expr }}
                </td>
              </tr>
            </tbody>
          </table>
          <p
            v-if="currentGuide.tip"
            class="guide-examples-tip">
            {{ currentGuide.tip }}
          </p>
        </div>
        <div
          class="guide-doc">
          <div class="guide-doc-title">
            {{ $t('文档') }}
          </div>
          <div class="guide-doc-content">
            <span v-if="currentGuide.title === 'MAKO'"> {{ currentGuide.docText }} </span>
            <span v-else-if="currentGuide.docLink">{{ $t('完整语法请参考') }}</span>
            <bk-link
              v-if="currentGuide.docLink"
              theme="primary"
              :href="currentGuide.docLink"
              target="_blank">
              {{ currentGuide.docText }}
            </bk-link>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script>
  const OPTION_GUIDES_BY_NAME = {
    gateway_expression: {
      boolrule: {
        title: 'Boolrule',
        syntax: [
          { label: '比较运算符', tokens: ['==', '!=', '>', '>=', '<=', 'in', 'notin'] },
          { label: '逻辑关键词', tokens: ['and', 'or', 'True / true', 'False / false'] },
          { label: '变量引用', text: '支持 ${key}、${int(key)}' },
        ],
        examples: [
          { scene: '字符串比较', expr: '"${status}" == "success"' },
          { scene: '数值比较', expr: '${int(retry)} >= 3' },
          { scene: '包含判断', expr: '"${env}" in ("prod", "stage")' },
        ],
        tip: '前提：status / retry / env 为流程全局变量。',
        docText: 'Boolrule 表达式文档',
        docLink: 'https://boolrule.readthedocs.io/en/latest/expressions.html#basic-comparison-operators',
      },
      FEEL: {
        title: 'FEEL',
        syntax: [
          { label: '比较运算符', tokens: ['=', '!=', '>', '>=', '<', '<='] },
          { label: '逻辑关键词', tokens: ['and', 'or', 'true', 'false'] },
          { label: '变量引用', tokens: ['${key}', '${int(key)}', '支持 list contains'] },
        ],
        examples: [
          { scene: '字符串比较', expr: '"${env}" = "prod"' },
          { scene: '数值比较', expr: '${int(retry)} >= 3' },
          { scene: '包含判断', expr: 'list contains([1, 2, 3], ${int(retry)})' },
        ],
        tip: '前提：字符串比较用 =, 不要写成 ==。',
        docText: 'bkflow-feel 语法文档',
        docLink: 'https://github.com/TencentBlueKing/bkflow-feel/blob/main/docs/grammer.md',
      },
      MAKO: {
        title: 'MAKO',
        syntax: [
          { label: '比较运算符', tokens: ['==', '!=', '>', '>=', '<=', 'in', 'not in'] },
          { label: '逻辑关键词', tokens: ['and', 'or', 'not', 'True', 'False'] },
          { label: '变量引用', text: '直接引用变量名 key, 不要包 ${}' },
        ],
        warning: '因 MAKO 语法限制：请勿在表达式中使用 $、{、} 字符。误用会导致分支条件解析失败。',
        examples: [
          { scene: '字符串比较', expr: 'key == "3"' },
          { scene: '数值比较', expr: 'int(key) >= 3' },
          { scene: '包含判断', expr: 'int(key) in (1,2,3)' },
        ],
        docText: 'MAKO 无独立语法站点，以本页与分支条件侧滑说明为准。',
      },
    },
  };

  export default {
    name: 'OptionRadio',
    model: {
      prop: 'value',
      event: 'change',
    },
    props: {
      value: {
        type: [String, Number, Boolean],
        default: '',
      },
      schema: {
        type: Object,
        default: () => ({}),
      },
      name: {
        type: String,
        default: '',
      },
    },
    computed: {
      options() {
        return this.schema.options || [];
      },
      guideMap() {
        return OPTION_GUIDES_BY_NAME[this.name] || null;
      },
      currentGuide() {
        if (!this.guideMap) return null;
        const key = this.value;
        return this.guideMap[key] || null;
      },
    },
  };
</script>

<style lang="scss" scoped>
  .option-radio {
    display: flex;
    flex-wrap: wrap
  }
  .option-item {
    display: flex;
    align-items: center;
    margin-right: 24px;
    margin-bottom: 8px;
    ::v-deep .bk-radio-text {
      color: #979ba5;
      font-size: 12px;
    }
  }
  .option-guide {
    margin-top: 16px;
    .guide-card {
      background: #f5f7fa;
      border-radius: 2px;
      padding: 12px 16px;
      margin-bottom: 20px;
      .guide-card-title {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;
        font-weight: 700;
        color: #313238;
        margin-bottom: 10px;
        .guide-card-title-current {
          font-size: 12px;
          font-weight: 400;
          color: #14a568;
          background: #e4faf0;
          padding: 0 6px;
          height: 20px;
          line-height: 20px;
          border-radius: 2px;
        }
      }
      .guide-syntax-row {
        display: flex;
        align-items: center;
        font-size: 12px;
        line-height: 20px;
        color: #4d4f56;
        margin-bottom: 6px;
        &:last-child {
          margin-bottom: 0;
        }
        .guide-syntax-label {
          width: 80px;
          flex-shrink: 0;
          color: #4d4f56;
        }
        .guide-syntax-values {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 6px 10px;
        }
        .guide-token {
          display: inline-block;
          padding: 0 6px;
          height: 20px;
          line-height: 20px;
          background: #ffffff;
          border: 1px solid #dcdee5;
          border-radius: 2px;
          color: #4d4f56;
        }
        .guide-syntax-text {
          color: #4d4f56;
        }
      }
    }
    .guide-warning {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      background: #faf1e3;
      border: 1px solid #f7d8ac;
      border-radius: 5px;
      padding: 8px 12px;
      color: #f08c10;
      margin-bottom: 20px;
      .guide-warning-icon {
        color: #ff9c01;
        font-size: 14px;
        line-height: 20px;
        flex-shrink: 0;
        margin-top: 1px;
      }
      .guide-warning-text {
        font-size: 12px;
        line-height: 20px;
        word-break: break-word;
      }
      .guide-warning-label {
        font-weight: 700;
      }
    }
    .guide-examples {
      margin-bottom: 20px;
      .guide-examples-title {
        font-size: 14px;
        font-weight: 700;
        color: #313238;
        margin-bottom: 8px;
      }
      .guide-examples-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
        background: #ffffff;
        th,
        td {
          border: 1px solid #dcdee5;
          padding: 8px 12px;
          text-align: left;
          vertical-align: middle;
          color: #4d4f56;
          user-select: text;
        }
        th {
          background: #fafbfd;
          font-weight: 700;
          color: #4d4f56;
        }
        .col-scene {
          width: 160px;
        }
      }
      .guide-examples-tip {
        margin-top: 8px;
        font-size: 12px;
        line-height: 20px;
        color: #979ba5;
      }
    }
    .guide-doc {
      .guide-doc-title {
        font-size: 14px;
        font-weight: 700;
        color: #313238;
        margin-bottom: 6px;
      }
      .guide-doc-content {
        font-size: 12px;
        color: #4d4f56;
        display: flex;
        align-items: center;
        gap: 4px;
        ::v-deep .bk-link {
          .bk-link-text {
            font-size: 12px;
          }
        }
      }
    }
  }
  .option-guide-fade-enter-active,
  .option-guide-fade-leave-active {
    transition: opacity 0.15s ease;
  }
  .option-guide-fade-enter,
  .option-guide-fade-leave-to {
    opacity: 0;
  }
</style>
