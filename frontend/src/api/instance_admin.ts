import request from "@/utils/request";
import { ElMessage } from "element-plus";

/**
 * 旧 JSON 接口信封归一化工具（实例管理 5 子页共用）。
 * 旧接口有 4 种返回形态：{status,msg,rows} / {status,msg,data} / {total,rows} / 裸数组。
 */

/** 旧信封 status≠0 时抛错并提示，返回原信封（由调用方取 rows/data） */
function checkStatus<T extends { status?: number; msg?: string }>(env: T): T {
  if (env.status !== 0) {
    ElMessage.error(env.msg || "操作失败");
    throw new Error(env.msg || "operation failed");
  }
  return env;
}

// ============ 会话诊断 db_diagnostic ============

export interface ProcessRow {
  [key: string]: unknown;
}

/** 进程列表（POST /api/v1/diagnostic/process/，{status,msg,rows}） */
export function fetchProcess(params: {
  instance_name: string;
  command_type?: string;
} & Record<string, unknown>) {
  return request
    .post<{ status: number; msg: string; rows?: ProcessRow[] }>(
      "/api/v1/diagnostic/process/",
      params,
    )
    .then((res) => checkStatus(res.data).rows || []);
}

/** Top 表空间（POST /api/v1/diagnostic/tablespace/，{status,msg,rows,total}） */
export function fetchTablespace(params: {
  instance_name: string;
  offset?: number;
  limit?: number;
  schema_search?: string;
}) {
  return request
    .post<{
      status: number;
      msg: string;
      rows?: ProcessRow[];
      total?: number;
    }>("/api/v1/diagnostic/tablespace/", params)
    .then((res) => {
      const e = checkStatus(res.data);
      return { rows: e.rows || [], total: e.total || 0 };
    });
}

/** 事务信息（POST /api/v1/diagnostic/innodb_trx/，{status,msg,rows}） */
export function fetchInnodbTrx(instance_name: string) {
  return request
    .post<{ status: number; msg: string; rows?: ProcessRow[] }>(
      "/api/v1/diagnostic/innodb_trx/",
      { instance_name },
    )
    .then((res) => checkStatus(res.data).rows || []);
}

/** 锁信息（POST /api/v1/diagnostic/trxandlocks/，{status,msg,rows}） */
export function fetchTrxAndLocks(instance_name: string) {
  return request
    .post<{ status: number; msg: string; rows?: ProcessRow[] }>(
      "/api/v1/diagnostic/trxandlocks/",
      { instance_name },
    )
    .then((res) => checkStatus(res.data).rows || []);
}

/** 第一步：构造 kill 语句（确认线程存活，返回 kill SQL） */
export function createKillSession(params: {
  instance_name: string;
  ThreadIDs: (string | number)[];
}) {
  return request
    .post<{ status: number; msg: string; data?: unknown }>(
      "/api/v1/diagnostic/create_kill/",
      { instance_name: params.instance_name, ThreadIDs: params.ThreadIDs },
    )
    .then((res) => checkStatus(res.data).data);
}

/** 第二步：执行 kill */
export function killSession(params: {
  instance_name: string;
  ThreadIDs: (string | number)[];
}) {
  return request
    .post<{ status: number; msg: string; data?: unknown }>(
      "/api/v1/diagnostic/kill/",
      { instance_name: params.instance_name, ThreadIDs: params.ThreadIDs },
    )
    .then((res) => checkStatus(res.data).data);
}

// ============ 数据库管理 instance_database ============

export interface DatabaseRow {
  db_name: string;
  owner: string;
  remark: string;
  saved?: boolean;
  [key: string]: unknown;
}

/** 库列表（POST /api/v1/instance/databases/，{status,msg,rows}） */
export function fetchDatabases(instance_id: number, saved = 0) {
  return request
    .post<{ status: number; msg: string; rows?: DatabaseRow[] }>(
      "/api/v1/instance/databases/",
      { instance_id, saved: String(saved) },
    )
    .then((res) => checkStatus(res.data).rows || []);
}

export function createDatabase(params: {
  instance_id: number;
  db_name: string;
  owner: string;
  remark?: string;
}) {
  return request
    .post<{ status: number; msg: string; data?: unknown }>(
      "/api/v1/instance/databases/create/",
      params,
    )
    .then((res) => checkStatus(res.data).data);
}

export function editDatabase(params: {
  instance_id: number;
  db_name: string;
  owner: string;
  remark?: string;
}) {
  return request
    .post<{ status: number; msg: string; data?: unknown }>(
      "/api/v1/instance/databases/edit/",
      params,
    )
    .then((res) => checkStatus(res.data).data);
}

// ============ 账号管理 instance_account ============

export interface AccountRow {
  user: string;
  host: string;
  user_host?: string;
  db_name?: string;
  remark?: string;
  is_locked?: string;
  saved?: boolean;
  [key: string]: unknown;
}

/** 帐号列表（POST /api/v1/instance/accounts/，{status,msg,rows}） */
export function fetchUsers(instance_id: number, saved = 0) {
  return request
    .post<{ status: number; msg: string; rows?: AccountRow[] }>(
      "/api/v1/instance/accounts/",
      { instance_id, saved: String(saved) },
    )
    .then((res) => checkStatus(res.data).rows || []);
}

export function createAccount(params: {
  instance_id: number;
  user: string;
  host: string;
  password1: string;
  password2: string;
  db_name?: string;
  remark?: string;
}) {
  return request
    .post<{ status: number; msg: string; data?: unknown }>(
      "/api/v1/instance/accounts/create/",
      params,
    )
    .then((res) => checkStatus(res.data).data);
}

export function editAccount(params: {
  instance_id: number;
  user: string;
  host: string;
  password?: string;
  remark?: string;
}) {
  return request
    .post<{ status: number; msg: string; data?: unknown }>(
      "/api/v1/instance/accounts/edit/",
      params,
    )
    .then((res) => checkStatus(res.data).data);
}

/** 授权/回收（op_type 0=GRANT/1=REVOKE；priv_type 0全局/1库/2表/3列） */
export function grantAccount(params: {
  instance_id: number;
  user_host: string;
  op_type: 0 | 1;
  priv_type: 0 | 1 | 2 | 3;
  privs: string[];
  db_name?: string[];
  tb_name?: string[];
  col_name?: string[];
}) {
  return request
    .post<{ status: number; msg: string; data?: unknown }>(
      "/api/v1/instance/accounts/grant/",
      params,
    )
    .then((res) => checkStatus(res.data).data);
}

/** Mongo 内置角色（db.createUser/updateUser roles） */
export const MONGO_ROLES = [
  "read", "readWrite", "dbAdmin", "dbOwner", "userAdmin",
  "clusterAdmin", "clusterManager", "clusterMonitor", "hostManager",
  "readAnyDatabase", "readWriteAnyDatabase", "userAdminAnyDatabase",
  "dbAdminAnyDatabase", "root",
];

/** Mongo 账号授权（POST /api/v1/instance/accounts/grant/，db_name_user=db.user + roles[]） */
export function grantMongoAccount(params: {
  instance_id: number;
  db_name_user: string;
  roles: string[];
}) {
  // Mongo roles 需要 POST 数组重复键，用 URLSearchParams 传 form
  const f = new URLSearchParams();
  f.append("instance_id", String(params.instance_id));
  f.append("db_name_user", params.db_name_user);
  params.roles.forEach((r) => f.append("roles[]", r));
  return request
    .post<{ status: number; msg: string; data?: unknown }>(
      "/api/v1/instance/accounts/grant/",
      f,
    )
    .then((res) => checkStatus(res.data).data);
}

export function resetPwd(params: {
  instance_id: number;
  user_host: string;
  reset_pwd1: string;
  reset_pwd2: string;
}) {
  return request
    .post<{ status: number; msg: string; data?: unknown }>(
      "/api/v1/instance/accounts/reset_pwd/",
      params,
    )
    .then((res) => checkStatus(res.data).data);
}

/** is_locked: "Y" 锁定 / "N" 解锁（仅 mysql） */
export function lockAccount(params: {
  instance_id: number;
  user_host: string;
  is_locked: "Y" | "N";
}) {
  return request
    .post<{ status: number; msg: string; data?: unknown }>(
      "/api/v1/instance/accounts/lock/",
      params,
    )
    .then((res) => checkStatus(res.data).data);
}

export function deleteAccount(params: {
  instance_id: number;
  user_host: string;
}) {
  return request
    .post<{ status: number; msg: string; data?: unknown }>(
      "/api/v1/instance/accounts/delete/",
      params,
    )
    .then((res) => checkStatus(res.data).data);
}

// ============ 参数 instance.py ============

export interface ParamRow {
  variable_name: string;
  runtime_value?: string;
  editable?: boolean;
  default_value?: string;
  description?: string;
  [key: string]: unknown;
}

/**
 * 参数列表（POST /api/v1/instance/params/）。
 * 成功返回**裸数组**，失败返回 {status,msg,data}。需按返回类型分支。
 */
export async function fetchParamList(params: {
  instance_id: number;
  editable?: number;
  search?: string;
}): Promise<ParamRow[]> {
  const { data } = await request.post<unknown>("/api/v1/instance/params/", params);
  if (Array.isArray(data)) return data as ParamRow[];
  // 失败信封
  const env = data as { status?: number; msg?: string };
  if (env.status !== 0) {
    ElMessage.error(env.msg || "获取参数失败");
    throw new Error(env.msg || "fetch param list failed");
  }
  return [];
}

/** 参数修改历史（POST /api/v1/instance/params/history/，{total,rows} 无 status） */
export function fetchParamHistory(params: {
  instance_id: number;
  limit?: number;
  offset?: number;
  search?: string;
}) {
  return request
    .post<{ total: number; rows: ParamRow[] }>(
      "/api/v1/instance/params/history/",
      params,
    )
    .then((res) => ({ total: res.data.total || 0, rows: res.data.rows || [] }));
}

/** 修改参数（POST /api/v1/instance/params/edit/，{status,msg,data}） */
export function editParam(params: {
  instance_id: number;
  variable_name: string;
  runtime_value: string;
}) {
  return request
    .post<{ status: number; msg: string; data?: unknown }>(
      "/api/v1/instance/params/edit/",
      params,
    )
    .then((res) => checkStatus(res.data).data);
}

export interface ParamCompareResult {
  rows: ProcessRow[];
  total: number;
  same_count: number;
  diff_count: number;
  instance1_name: string;
  instance2_name: string;
}

/** 参数对比（POST /api/v1/instance/params/compare/，{status,msg,data:{rows,total,same_count,diff_count,...}}） */
export function compareParam(params: {
  instance_id1: number;
  instance_id2: number;
  diff_only?: boolean;
}) {
  return request
    .post<{ status: number; msg: string; data?: ParamCompareResult }>(
      "/api/v1/instance/params/compare/",
      { ...params, diff_only: params.diff_only ? "true" : "false" },
    )
    .then((res) => checkStatus(res.data).data as ParamCompareResult);
}
