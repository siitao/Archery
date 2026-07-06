import request from "@/utils/request";

/** 外部认证方式取值 */
export type AuthProvider = "local" | "ldap" | "oidc" | "dingding" | "cas";

/** 各方式的参数集合（运行时由后端返回全部 key，前端按需取用） */
export interface AuthConfig {
  auth_provider: AuthProvider | string;
  // LDAP
  auth_ldap_server_uri?: string;
  auth_ldap_bind_dn?: string;
  auth_ldap_bind_password?: string;
  auth_ldap_user_dn_template?: string;
  auth_ldap_user_search_base?: string;
  auth_ldap_user_search_filter?: string;
  auth_ldap_user_attr_map?: string;
  // OIDC
  oidc_rp_wellknown_url?: string;
  oidc_rp_client_id?: string;
  oidc_rp_client_secret?: string;
  oidc_rp_scopes?: string;
  oidc_rp_sign_algo?: string;
  oidc_user_attr_map?: string;
  // 钉钉
  ding_app_key?: string;
  ding_app_secret?: string;
  ding_callback_url?: string;
  // CAS
  cas_server_url?: string;
  cas_version?: string;
  cas_verify_ssl_certificate?: string;
  [key: string]: string | undefined;
}

interface ApiResult {
  status: number;
  msg: string;
}

/** 读取当前认证配置（GET /api/v1/auth_config/） */
export function fetchAuthConfig() {
  return request.get<AuthConfig>("/api/v1/auth_config/").then((r) => r.data);
}

/** 保存认证配置（POST /api/v1/auth_config/）。
 * provider 选定的方式；params 仅含该方式相关参数；reload=true 保存后立即重载生效。 */
export function saveAuthConfig(
  provider: AuthProvider | string,
  params: Record<string, string>,
  reload = false
) {
  return request
    .post<ApiResult>("/api/v1/auth_config/", {
      auth_provider: provider,
      params,
      reload,
    })
    .then((res) => {
      if (res.data.status !== 0) {
        throw new Error(res.data.msg || "保存失败");
      }
      return res.data;
    });
}

/** 单独触发重载（POST /api/v1/auth_config/reload/） */
export function reloadAuthConfig() {
  return request
    .post<ApiResult>("/api/v1/auth_config/reload/")
    .then((res) => {
      if (res.data.status !== 0) {
        throw new Error(res.data.msg || "重载失败");
      }
      return res.data;
    });
}

/** 测试连接（POST /api/v1/auth_config/test/）。provider + 当前表单输入值。 */
export function testAuthConnection(
  provider: AuthProvider | string,
  params: Record<string, string>
) {
  return request
    .post<ApiResult>("/api/v1/auth_config/test/", { provider, ...params })
    .then((res) => {
      if (res.data.status !== 0) {
        throw new Error(res.data.msg || "测试失败");
      }
      return res.data;
    });
}
