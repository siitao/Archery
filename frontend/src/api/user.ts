import request, { type LegacyEnvelope } from "@/utils/request";

export interface CurrentUser {
  id: number;
  username: string;
  display: string;
  email: string;
  is_superuser: boolean;
  is_staff: boolean;
  resource_group: number[];
  permissions: string[];
}

/** 当前登录用户信息 + 权限位（菜单/路由守卫依据） */
export function fetchCurrentUser() {
  return request.get<CurrentUser>("/api/v1/user/me/");
}

/** /authenticate/ 旧信封结果：status 0 成功；data=null 已登录，data=sessionKey 需 2FA；1 失败；3 锁定 */
export interface AuthResult extends LegacyEnvelope<string | null> {}

export function authenticate(username: string, password: string) {
  // 服务端用 request.POST 读取，需表单编码
  const form = new URLSearchParams();
  form.append("username", username);
  form.append("password", password);
  return request.post<AuthResult>("/authenticate/", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
}

/** 退出登录（服务端 sign_out 会 302，忽略响应体即可） */
export function logout() {
  return request.post("/logout/");
}
