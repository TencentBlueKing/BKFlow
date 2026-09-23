/** Build navigation only for configured absolute service URLs. */
export function buildUserNavigationActions({ iamUrl, userUrl, translate, logout }) {
  const validUrl = (value) => {
    if (typeof value !== 'string') return '';
    try {
      const url = new URL(value);
      return ['http:', 'https:'].includes(url.protocol) ? value.trim().replace(/\/+$/, '') : '';
    } catch (e) {
      return '';
    }
  };
  const actions = [];
  const iam = validUrl(iamUrl);
  const user = validUrl(userUrl);
  if (iam) actions.push({ text: translate('权限中心'), icon: 'common-icon-authority', href: iam, target: '_blank' });
  if (user) actions.push({ text: translate('个人设置'), icon: 'bk-icon icon-user', href: `${user}/personal-center`, target: '_blank' });
  actions.push({ text: translate('退出登录'), icon: 'common-icon-export', theme: 'danger', handle: logout });
  return actions;
}
