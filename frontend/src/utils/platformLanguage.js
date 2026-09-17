/** Persist the language through the API supported by the deployment platform. */
export async function updatePlatformLanguage(axios, config, language) {
  if (config.USE_APIGW) {
    const base = config.BK_USER_WEB_APIGW_URL.replace(/\/$/, '');
    const response = await axios.put(`${base}/api/v3/open-web/tenant/current-user/language/`, { language }, {
      withCredentials: true,
      headers: { 'X-Bk-Tenant-Id': config.TENANT_ID || 'default' },
    });
    if (response.data && response.data.result === false) {
      throw new Error(response.data.message || 'Unable to update language');
    }
  } else if (config.BK_PAAS_ESB_HOST) {
    await axios.jsonp(`${config.BK_PAAS_ESB_HOST}/api/c/compapi/v2/usermanage/fe_update_user_language/`, { language });
  }
}
