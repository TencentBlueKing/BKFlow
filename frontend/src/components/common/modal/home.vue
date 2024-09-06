<template>
  <div class="app-home">
    <div class="content-wrap">
      <img
        class="image1"
        :src="image1"
        alt="">
      <img
        class="image2"
        :src="image2"
        alt="">
      <img
        class="image3"
        :src="image3"
        alt="">
      <img
        class="image4"
        :src="image4"
        alt="">
      <p class="project-presentation">
        <i18n tag="div" path="projectPresentationTips">
          <span class="highlight">{{ $t('高效') }}</span>
          <span class="highlight">{{ $t('灵活') }}</span>
          <span class="highlight">{{ $t('流程执行') }}</span>
        </i18n>
      </p>
      <div class="button-wrap">
        <bk-button
          :theme="'primary'"
          @click="$router.push({ name: 'spaceAdmin' })">
          {{ $t('立即体验') }}
        </bk-button>
        <bk-button
          :theme="'primary'"
          outline
          @click="goToHelpDoc">
          {{ $t('产品文档') }}
        </bk-button>
      </div>
      <p class="module-title">
        {{ $t('核心功能') }}
      </p>
      <ul class="function-wrap">
        <div class="function-item">
          <img
            class="image6"
            :src="image6"
            alt="">
          <i class="icon common-icon-node2" />
          <span class="name">{{ $t('流程编排和画布嵌入') }}</span>
          <span class="desc">{{ $t('直观地创建、编辑和管理流程，支持自定义权限控制。') }}</span>
        </div>
        <div class="function-item">
          <img
            class="image7"
            :src="image7"
            alt="">
          <i class="icon common-icon-api" />
          <span class="name">{{ $t('流程任务执行能力') }}</span>
          <span class="desc">{{ $t('通过 API 实现流程任务的创建、执行和控制。') }}</span>
        </div>
        <div class="function-item">
          <img
            class="image8"
            :src="image8"
            alt="">
          <i class="icon common-icon-decision-menu" />
          <span class="name">{{ $t('决策引擎能力') }}</span>
          <span class="desc">{{ $t('可在流程中进行规则管理和决策。') }}</span>
        </div>
      </ul>
      <p class="module-title access-title">
        {{ $t('便捷接入 & 集成') }}
      </p>
      <div class="access-wrap">
        <img
          class="image9"
          :src="image9"
          alt="">
        <img
          class="image9-right"
          :src="image9"
          alt="">
        <ul class="mode-list">
          <li>
            <span />
            <span>{{ $t('多种接入方式：') }}</span>
            <span>{{ $t('支持不同的接入方式，满足不同系统的接入需求。') }}</span>
          </li>
          <li>
            <span />
            <span>{{ $t('多种集成方式：') }}</span>
            <span>{{ $t('支持 Web 服务集成和 SDK 集成，方便接入平台灵活集成。') }}</span>
          </li>
        </ul>
        <ul class="sdk-list">
          <li>
            <span />
            <span>{{ $t('流程引擎：') }}</span>
            <span><a
              href="https://github.com/TencentBlueKing/bamboo-engine"
              target="_blank">{{ 'bkflow-engine' }}</a></span>
          </li>
          <li>
            <span />
            <span>{{ $t('决策引擎：') }}</span>
            <span><a
              href="https://github.com/TencentBlueKing/bkflow-dmn"
              target="_blank">{{ 'bkflow-dmn' }}</a></span>
          </li>
          <li>
            <span />
            <span>{{ $t('FEEL 表达式解析器：') }}</span>
            <span><a
              href="https://github.com/TencentBlueKing/bkflow-feel"
              target="_blank">{{ 'bkflow-feel' }}</a></span>
          </li>
        </ul>
        <div class="access-container">
          <img
            class="image10"
            :src="image10"
            alt="">
          <img
            class="image11"
            :src="isEnglish ? image16 : image11"
            alt="">
        </div>
      </div>
      <p class="module-title expand-title">
        {{ $t('接入平台扩展 & 管理') }}
      </p>
      <ul class="expand-wrap">
        <li>
          <p>{{ $t('高度可扩展&自定义能力') }}</p>
          <p>{{ $t('支持蓝鲸插件和 API 插件，') }}</p>
          <p>{{ $t('满足各种接入平台业务场景上的自定义需求。') }}</p>
          <img
            :src="image12"
            alt="">
        </li>
        <li>
          <p>{{ $t('数据管理能力') }}</p>
          <p>{{ $t('提供空间数据管理端，') }}</p>
          <p>{{ $t('接入平台管理员可基于空间视图进行资源数据管理和操作。') }}</p>
          <img
            :src="image15"
            alt="">
        </li>
        <li>
          <p>{{ $t('支持 Webhook 订阅机制') }}</p>
          <p>{{ $t('接入平台可以轻松感知，') }}</p>
          <p>{{ $t('流程任务事件并进行自动化扩展。') }}</p>
          <img
            :src="image13"
            alt="">
        </li>
        <li>
          <p>{{ $t('支持计算和存储资源隔离') }}</p>
          <p>{{ $t('任务执行和数据可与其他接入空间隔离。') }}</p>
          <img
            :src="image14"
            alt="">
        </li>
      </ul>
    </div>
  </div>
</template>

<script>
  export default {
    name: 'Home',
    data() {
      return {
        image1: require('@/assets/images/home/title-bg-blue.png'),
        image2: require('@/assets/images/home/title-bg-orange.png'),
        image3: require('@/assets/images/home/bk-flow.png'),
        image4: require('@/assets/images/home/illustration-1.png'),
        image5: require('@/assets/images/home/function-bg.png'),
        image6: require('@/assets/images/home/function-1.png'),
        image7: require('@/assets/images/home/function-2.png'),
        image8: require('@/assets/images/home/function-3.png'),
        image9: require('@/assets/images/home/access-bg.png'),
        image10: require('@/assets/images/home/illustration-2.png'),
        image11: require('@/assets/images/home/access-title.png'),
        image12: require('@/assets/images/home/plugin-1.png'),
        image13: require('@/assets/images/home/plugin-2.png'),
        image14: require('@/assets/images/home/plugin-3.png'),
        image15: require('@/assets/images/home/plugin-4.png'),
        image16: require('@/assets/images/home/access-title-en.png'),
        isEnglish: false,
      };
    },
    created() {
      this.isEnglish = window.getCookie('blueking_language') === 'en';
    },
    methods: {
      goToHelpDoc() {
        window.open(window.BK_DOC_URL, '_blank');
      },
    },
  };
</script>

<style lang="scss" scoped>
  .app-home {
    position: relative;
    height: 100%;
    width: 100%;
    min-width: 1280px;
    padding-bottom: 140px;
    background: #ffffff;
    overflow-x: hidden;
    .content-wrap {
      position: relative;
      width: 1280px;
      margin: 0 auto;
      padding-top: 128px;
      color: #313238;
      > * {
        position: relative;
        z-index: 2;
      }
      img {
        user-select: none;
        -webkit-user-drag: none;
      }
    }
    .image1 {
      position: absolute;
      top: 0;
      left: -600px;
      z-index: 1;
    }
    .image2 {
      position: absolute;
      top: 0;
      right: -690px;
    }
    .image3 {
      position: absolute;
      left: -72px;
      z-index: 1;
    }
    .image4 {
      position: absolute;
      top: 87px;
      right: -289px;
    }
    .project-presentation {
      width: 358px;
      font-size: 22px;
      line-height: 40px;
      margin: 150px 0 40px  0;
      .highlight {
        color: #3a84ff;
      }
    }
    .button-wrap {
      display: flex;
      margin-bottom: 378px;
      button {
        min-width: 168px;
        height: 48px;
        margin-right: 16px;
        font-size: 18px;
        border-radius: 28px;
      }
    }
    .module-title {
      position: relative;
      display: inline-block;
      left: 50%;
      transform: translateX(calc(-50% + 5px));
      margin-bottom: 37px;
      font-size: 40px;
      &::after {
        content: '';
        display: inline-block;
        position: absolute;
        top: 26px;
        left: 0;
        z-index: -1;
        width: 100%;
        height: 39px;
        background: #ffe8c3;
        border-radius: 20px;
      }
    }
    .function-wrap {
      display: flex;
      height: 354px;
      width: 1220px;
      padding-top: 22px;
      margin: 0 0 142px 16px;
      background-image: url('~@/assets/images/home/function-bg.png');
      background-repeat: no-repeat;
      .function-item {
        display: flex;
        flex-direction: column;
        text-align: left;
        img {
          width: 102px;
          height: 79px;
        }
        .icon {
          position: relative;
          width: 64px;
          height: 64px;
          background: #3a84ff;
          text-align: center;
          line-height: 64px;
          top: -32px;
          font-size: 40px;
          color: #fff;
          border-radius: 50%;
        }
        .name {
          font-size: 24px;
          line-height: 32px;
          margin: -16px 0 20px 0;
        }
        .desc {
          font-size: 18px;
          line-height: 32px;
        }
        &:first-child {
          margin-right: 295px;
          transform: translateX(-16px);
          img {
            margin-left: 50px;
          }
          .icon {
            margin-left: 69px;
          };
          .desc {
            width: 252px;
          }
        }
        &:nth-child(2) {
          img {
            margin-left: 30px;
          }
          .icon {
            margin-left: 50px;
          }
          .desc {
            width: 215px;
            word-break: break-all;
          }
        }
        &:last-child {
          transform: translateX(41px);
          margin-left: 260px;
          img {
            margin-left: 16px;
          }
          .icon {
            margin-left: 43px;
          };
          .desc {
            width: 215px;
          }
        }
      }
    }
    .access-title {
      left: 0;
      transform: translateX(0);
      margin-bottom: 34px;
      z-index: 3;
    }
    .access-wrap {
      position: relative;
      margin-bottom: 166px;
      .image9 {
        position: absolute;
        top: -168px;
        left: -908px;
        z-index: -1;
      }
      .image9-right {
        position: absolute;
        top: 172px;
        right: -100%;
        transform: translateX(370px);
        z-index: -1;
      }
      .mode-list,
      .sdk-list {
        display: inline-block;
        vertical-align: top;
        li {
          display: flex;
          align-items: center;
          line-height: 32px;
          margin-bottom: 13px;
          font-weight: Bold;
          font-size: 18px;
          color: #313238;
          span:first-child {
            width: 12px;
            height: 12px;
            margin-right: 12px;
            background: #d62929;
            border: 2px solid #d62929;
            border-radius: 50%;
          }
          span:last-child {
            margin-left: 8px;
            font-weight: normal;
          }
          &:last-child {
            margin-bottom: 0;
          }
        }
      }
      .mode-list {
        margin-bottom: 107px;
      }
      .sdk-list {
        position: absolute;
        top: 0;
        right: 0;
        width: 554px;
        padding: 20px 28px;
        background: #f0f1f5;
        border-radius: 16px;
        li {
          line-height: 24px !important;
          margin-bottom: 16px !important;
          font-weight: normal !important;
          span:first-child {
            background: #fff;
          }
          span:last-child {
            a {
              color: #3a84ff;
              text-decoration: underline;
            }
          }
          &:last-child {
            margin-bottom: 0 !important;
          }
        }
        &::after {
          content: '';
          display: inline-block;
          position: absolute;
          left: -24px;
          top: 0;
          height: 100%;
          width: 2px;
          background-image: linear-gradient(#d62929 35%, rgba(255, 255, 255, 0) 0%);
          background-position: left;
          background-size: 1px 12px;
          background-repeat: repeat-y;
        }
      }
      .access-container {
        position: relative;
        width: 1032px;
        height: 706px;
        margin-left: auto;
        padding: 16px;
        background: #FFFFFF;
        box-shadow: 0 6px 20px 0 #0000001f;
        border-radius: 14px;
        .image10 {
          position: absolute;
          top: -91px;
          left: -192px;
          z-index: 2;
        }
        .image11 {
          width: 100%;
        }
      }
    }
    .expand-title {
      margin-bottom: 83px;
      &::after {
        left: 0;
        z-index: -1;
        width: 100%;
      }
    }
    .expand-wrap {
      display: grid;
      grid-gap: 40px;
      grid-template-columns: 620px 620px;
      grid-template-rows: 258px 258px;
      li {
        position: relative;
        padding: 40px;
        line-height: 32px;
        font-size: 18px;
        background-image: linear-gradient(180deg, #F7F8FA 0%, #FFFFFF 98%);
        border-radius: 8px;
        p {
          position: relative;
          z-index: 1;
          &:first-child {
            font-size: 24px;
            margin-bottom: 19px;
          }
        }
        img {
          position: absolute;
          right: 0;
          bottom: -35px;
        }
        &:nth-child(2n) {
          img {
            right: 12px;
          }
        }
        &::before {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          height: 8px;
          width: 100%;
          background: #3a84ff;
          border-radius: 8px 8px 0 0;
        }
      }
    }
  }
</style>
