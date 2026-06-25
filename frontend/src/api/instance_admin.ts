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

/** 表单编码（旧接口多用 request.POST） */
function form(obj: Record<string, unknown>) {
  const f = new URLSearchParams();
  for (const [k, v] of Object.entries(obj)) {
    if (v === undefined || v === null) continue;
    f.append(k, typeof v === "string" ? v : JSON.stringify(v));
  }
  return f;
}

const FORM_HEADERS = { "Content-Type": "application/x-www-form-urlencoded" };

// ============ 会话诊断 db_diagnostic ============

export interface ProcessRow {
  [key: string]: unknown;
}

/** 进程列表（POST /db_diagnostic/process/，{status,msg,rows}） */
export function fetchProcess(params: {
  instance_name: string;
  command_type?: string;
} & Record<string, unknown>) {
  return request
    .post<{ status: number; msg: string; rows?: ProcessRow[] }>(
      "/db_diagnostic/process/",
      form(params),
      { headers: FORM_HEADERS }
    )
    .then((res) => checkStatus(res.data).rows || []);
}

/** Top 表空间（POST /db_diagnostic/tablespace/，{status,msg,rows,total}） */
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
    }>("/db_diagnostic/tablespace/", form(params), { headers: FORM_HEADERS })
    .then((res) => {
      const e = checkStatus(res.data);
      return { rows: e.rows || [], total: e.total || 0 };
    });
}

/** 事务信息（POST /db_diagnostic/innodb_trx/，{status,msg,rows}） */
export function fetchInnodbTrx(instance_name: string) {
  return request
    .post<{ status: number; msg: string; rows?: ProcessRow[] }>(
      "/db_diagnostic/innodb_trx/",
      form({ instance_name }),
      { headers: FORM_HEADERS }
    )
    .then((res) => checkStatus(res.data).rows || []);
}

/** 锁信息（POST /db_diagnostic/trxandlocks/，{status,msg,rows}） */
export function fetchTrxAndLocks(instance_name: string) {
  return request
    .post<{ status: number; msg: string; rows?: ProcessRow[] }>(
      "/db_diagnostic/trxandlocks/",
      form({ instance_name }),
      { headers: FORM_HEADERS }
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
      "/db_diagnostic/create_kill_session/",
      form({ instance_name: params.instance_name, ThreadIDs: params.ThreadIDs }),
      { headers: FORM_HEADERS }
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
      "/db_diagnostic/kill_session/",
      form({ instance_name: params.instance_name, ThreadIDs: params.ThreadIDs }),
      { headers: FORM_HEADERS }
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

/** 库列表（POST /instance/database/list/，{status,msg,rows}） */
export function fetchDatabases(instance_id: number, saved = 0) {
  return request
    .post<{ status: number; msg: string; rows?: DatabaseRow[] }>(
      "/instance/database/list/",
      form({ instance_id, saved }),
      { headers: FORM_HEADERS }
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
      "/instance/database/create/",
      form(params),
      { headers: FORM_HEADERS }
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
      "/instance/database/edit/",
      form(params),
      { headers: FORM_HEADERS }
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

export function fetchUsers(instance_id: number, saved = 0) {
  return request
    .post<{ status: number; msg: string; rows?: AccountRow[] }>(
      "/instance/user/list",
      form({ instance_id, saved }),
      { headers: FORM_HEADERS }
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
      "/instance/user/create/",
      form(params),
      { headers: FORM_HEADERS }
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
      "/instance/user/edit/",
      form(params),
      { headers: FORM_HEADERS }
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
      "/instance/user/grant/",
      form({
        ...params,
        privs: params.privs,
        db_name: params.db_name || [],
        tb_name: params.tb_name || [],
        col_name: params.col_name || [],
      }),
      { headers: FORM_HEADERS }
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
      "/instance/user/reset_pwd/",
      form(params),
      { headers: FORM_HEADERS }
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
      "/instance/user/lock/",
      form(params),
      { headers: FORM_HEADERS }
    )
    .then((res) => checkStatus(res.data).data);
}

export function deleteAccount(params: {
  instance_id: number;
  user_host: string;
}) {
  return request
    .post<{ status: number; msg: string; data?: unknown }>(
      "/instance/user/delete/",
      form(params),
      { headers: FORM_HEADERS }
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
 * 参数列表（POST /param/list/）。
 * 成功返回**裸数组**，失败返回 {status,msg,data}。需按返回类型分支。
 */
export async function fetchParamList(params: {
  instance_id: number;
  editable?: number;
  search?: string;
}): Promise<ParamRow[]> {
  const { data } = await request.post<unknown>("/param/list/", form(params), {
    headers: FORM_HEADERS,
  });
  if (Array.isArray(data)) return data as ParamRow[];
  // 失败信封
  const env = data as { status?: number; msg?: string };
  if (env.status !== 0) {
    ElMessage.error(env.msg || "获取参数失败");
    throw new Error(env.msg || "fetch param list failed");
  }
  return [];
}

/** 参数修改历史（POST /param/history/，{total,rows} 无 status） */
export function fetchParamHistory(params: {
  instance_id: number;
  limit?: number;
  offset?: number;
  search?: string;
}) {
  return request
    .post<{ total: number; rows: ParamRow[] }>(
      "/param/history/",
      form(params),
      { headers: FORM_HEADERS }
    )
    .then((res) => ({ total: res.data.total || 0, rows: res.data.rows || [] }));
}

/** 修改参数（POST /param/edit/，{status,msg,data}） */
export function editParam(params: {
  instance_id: number;
  variable_name: string;
  runtime_value: string;
}) {
  return request
    .post<{ status: number; msg: string; data?: unknown }>(
      "/param/edit/",
      form(params),
      { headers: FORM_HEADERS }
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

/** 参数对比（POST /param/compare/，{status,msg,data:{rows,total,same_count,diff_count,...}}） */
export function compareParam(params: {
  instance_id1: number;
  instance_id2: number;
  diff_only?: boolean;
}) {
  return request
    .post<{ status: number; msg: string; data?: ParamCompareResult }>(
      "/param/compare/",
      form({ ...params, diff_only: params.diff_only ? "true" : "false" }),
      { headers: FORM_HEADERS }
    )
    .then((res) => checkStatus(res.data).data as ParamCompareResult);
}
