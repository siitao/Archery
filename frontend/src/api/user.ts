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

// ============ 2FA（密码校验通过后，临时会话已建立） ============

export interface TwoFaContext {
  verify_mode: "verify_only" | "verify_config";
  auth_types: { code: string; display: string }[];
  phone: string;
}

/** 2FA 验证上下文（POST /api/v1/user/2fa/context/，读临时会话 session） */
export function fetch2faContext() {
  return request
    .post<{ status: number; msg: string; data: TwoFaContext }>(
      "/api/v1/user/2fa/context/",
      {}
    )
    .then((res) => res.data.data);
}

/** 2FA 校验（POST /api/v1/user/2fa/verify/，校验通过后服务端自动 login） */
export function fetch2faVerify(params: {
  engineer: string;
  otp: string;
  auth_type: string;
  key?: string;
  phone?: string;
}) {
  return request.post<{ status: number; msg: string }>(
    "/api/v1/user/2fa/verify/",
    params
  );
}

/** 发送短信验证码（POST /api/v1/user/2fa/ enable=true, auth_type=sms） */
export function send2faSms(params: { engineer: string; phone: string }) {
  return request.post<{ status: number; msg: string }>(
    "/api/v1/user/2fa/",
    new URLSearchParams({
      engineer: params.engineer,
      enable: "true",
      auth_type: "sms",
      phone: params.phone,
    }),
    { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
  );
}
