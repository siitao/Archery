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

/** /api/v1/authenticate/ 旧信封结果：status 0 成功；data=null 已登录，data=sessionKey 需 2FA；1 失败；3 锁定 */
export interface AuthResult extends LegacyEnvelope<string | null> {}

export function authenticate(username: string, password: string) {
  // 服务端 DRF 视图同时支持 form-encoded 与 JSON；这里沿用 form 兼容旧信封
  const form = new URLSearchParams();
  form.append("username", username);
  form.append("password", password);
  return request.post<AuthResult>("/api/v1/authenticate/", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
}

/** 退出登录（POST /api/v1/logout/，启用钉钉认证时服务端会 302） */
export function logout() {
  return request.post("/api/v1/logout/");
}

// ============ 登录页 SSO 选项（未登录态可访问） ============

export interface LoginOptions {
  auth_provider: string;
  oidc_enabled: boolean;
  dingding_enabled: boolean;
  cas_enabled: boolean;
  oidc_btn_name: string;
  oidc_login_url: string;
  dingding_login_url: string;
  cas_login_url: string;
}

/** 登录页 SSO 选项（GET /api/v1/auth/login_options/，AllowAny） */
export function fetchLoginOptions() {
  return request.get<LoginOptions>("/api/v1/auth/login_options/").then((r) => r.data);
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

// ============ 用户管理 CRUD（DRF UserList/UserDetail） ============

export interface UserRow {
  id: number;
  username: string;
  display: string;
  email: string;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  groups: number[];
  user_permissions: number[];
  resource_group: number[];
  date_joined?: string;
  last_login?: string | null;
}

export interface AuthGroupRow {
  id: number;
  name: string;
  permissions: number[];
}
export interface PermGroup {
  model: string;
  label: string;
  permissions: { id: number; codename: string; name: string }[];
}

/** 用户清单（GET /api/v1/user/） */
export function fetchUsers(params: { page?: number; size?: number; username?: string } = {}) {
  return request.get<{ count: number; results: UserRow[] }>("/api/v1/user/", { params });
}

/** 新增用户（POST /api/v1/user/） */
export function createUser(data: Record<string, unknown>) {
  return request.post("/api/v1/user/", data);
}

/** 更新用户（PUT /api/v1/user/<id>/） */
export function updateUser(id: number, data: Record<string, unknown>) {
  return request.put(`/api/v1/user/${id}/`, data);
}

/** 删除用户（DELETE /api/v1/user/<id>/） */
export function deleteUser(id: number) {
  return request.delete(`/api/v1/user/${id}/`);
}

/** 权限组清单（GET /api/v1/user/group/） */
export function fetchGroups() {
  return request
    .get<{ count: number; results: AuthGroupRow[] }>("/api/v1/user/group/", {
      params: { size: 1000 },
    })
    .then((r) => r.data.results || []);
}

/** 创建权限组（POST /api/v1/user/group/，可带 permissions） */
export function createGroup(data: { name: string; permissions?: number[] }) {
  return request.post("/api/v1/user/group/", data);
}

/** 更新权限组（PUT /api/v1/user/group/<id>/） */
export function updateGroup(id: number, data: { name?: string; permissions?: number[] }) {
  return request.put(`/api/v1/user/group/${id}/`, data);
}

/** 删除权限组（DELETE /api/v1/user/group/<id>/） */
export function deleteGroup(id: number) {
  return request.delete(`/api/v1/user/group/${id}/`);
}

/** 全部权限（GET /api/v1/user/permissions/，按模型分组） */
export function fetchPermissions() {
  return request.get<PermGroup[]>("/api/v1/user/permissions/").then((r) => r.data);
}
