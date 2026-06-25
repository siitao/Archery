import request from "@/utils/request";
import { ElMessage } from "element-plus";

/**
 * 查询权限申请。旧接口走 /query/*（POST form + {total,rows}/{status,msg,data} 信封），
 * 详情/审核走新增 DRF /api/v1/query_priv/*。
 * 复用 checkStatus/form 模式（参考 phase2.ts）。申请 workflow_type=1（区别 SQL 上线=2）。
 */

function checkStatus<T extends { status?: number; msg?: string }>(env: T): T {
  if (env.status !== 0) {
    ElMessage.error(env.msg || "操作失败");
    throw new Error(env.msg || "operation failed");
  }
  return env;
}

/** 支持「同名多值」的 form：数组用重复键（后端 request.POST.getlist 收） */
function form(obj: Record<string, unknown>) {
  const f = new URLSearchParams();
  for (const [k, v] of Object.entries(obj)) {
    if (v === undefined || v === null) continue;
    if (Array.isArray(v)) {
      for (const item of v) f.append(k, String(item));
    } else {
      f.append(k, String(v));
    }
  }
  return f;
}

const FORM_HEADERS = { "Content-Type": "application/x-www-form-urlencoded" };

// ============ 常量 ============

/** 权限级别（QueryPrivilegesApply.priv_type） */
export const PRIV_TYPE_LABEL: Record<number, string> = { 1: "DATABASE", 2: "TABLE" };

/** 授权时长选项 → 天数（前端算出 valid_date 日期，与旧版 addDate 一致） */
export const VALID_DATE_OPTIONS = [
  { value: "day", label: "一天", days: 1 },
  { value: "week", label: "一周", days: 7 },
  { value: "month", label: "一月", days: 30 },
  { value: "year", label: "长期(一年)", days: 365 },
] as const;

/** 申请状态（QueryPrivilegesApply.status，WorkflowStatus） */
export const APPLY_STATUS: Record<
  number,
  { label: string; type: "success" | "info" | "warning" | "danger" }
> = {
  0: { label: "待审核", type: "info" },
  1: { label: "审核通过", type: "success" },
  2: { label: "审核不通过", type: "danger" },
  3: { label: "审核取消", type: "warning" },
};

/** 时长 value → 截止日期字符串（YYYY-MM-DD） */
export function computeValidDate(value: string): string {
  const opt = VALID_DATE_OPTIONS.find((o) => o.value === value);
  const days = opt ? opt.days : 1;
  const d = new Date();
  d.setDate(d.getDate() + days);
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

// ============ 申请列表 / 申请 / 用户权限 / 变更 ============

/** 申请列表行 */
export interface ApplyRow {
  apply_id: number;
  title: string;
  instance__instance_name: string;
  db_list: string;
  priv_type: number;
  table_list: string;
  limit_num: number | string;
  valid_date: string;
  user_display: string;
  status: number;
  create_time: string;
  group_name: string;
}

/** 申请列表（POST /query/applylist/，{total,rows}） */
export function fetchApplyList(params: {
  limit: number;
  offset: number;
  search?: string;
}) {
  return request
    .post<{ total: number; rows: ApplyRow[] }>(
      "/query/applylist/",
      form({ limit: params.limit, offset: params.offset, search: params.search ?? "" }),
      { headers: FORM_HEADERS }
    )
    .then((res) => ({ total: res.data.total || 0, rows: res.data.rows || [] }));
}

/** 申请权限（POST /query/applyforprivileges/）。priv_type 1=库(db_list[]) / 2=表(table_list[]) */
export function applyForPrivileges(params: {
  title: string;
  instance_name: string;
  group_name: string;
  priv_type: number;
  db_name?: string; // priv_type=2 单库
  db_list?: string[]; // priv_type=1 多库
  table_list?: string[]; // priv_type=2 多表
  valid_date: string; // 已算好的 YYYY-MM-DD
  limit_num: number | string;
}) {
  return request
    .post<{ status: number; msg: string; data: unknown }>(
      "/query/applyforprivileges/",
      form({
        title: params.title,
        instance_name: params.instance_name,
        group_name: params.group_name,
        priv_type: params.priv_type,
        db_name: params.db_name ?? "",
        "db_list[]": params.db_list ?? [],
        "table_list[]": params.table_list ?? [],
        valid_date: params.valid_date,
        limit_num: params.limit_num,
      }),
      { headers: FORM_HEADERS }
    )
    .then((res) => checkStatus(res.data));
}

/** 用户已有权限行 */
export interface UserPrivRow {
  privilege_id: number;
  user_display: string;
  instance__instance_name: string;
  db_name: string;
  priv_type: number;
  table_name: string;
  limit_num: number | string;
  valid_date: string;
}

/** 用户已有权限（POST /query/userprivileges/，{total,rows}） */
export function fetchUserPrivileges(params: {
  limit: number;
  offset: number;
  search?: string;
  user_display?: string;
}) {
  return request
    .post<{ total: number; rows: UserPrivRow[] }>(
      "/query/userprivileges/",
      form({
        limit: params.limit,
        offset: params.offset,
        search: params.search ?? "",
        user_display: params.user_display ?? "all",
      }),
      { headers: FORM_HEADERS }
    )
    .then((res) => ({ total: res.data.total || 0, rows: res.data.rows || [] }));
}

/** 变更/删除权限（POST /query/modifyprivileges/，type 1=删除 / 2=改 valid_date+limit_num） */
export function modifyPrivilege(params: {
  privilege_id: number;
  type: 1 | 2;
  valid_date?: string;
  limit_num?: number | string;
}) {
  return request
    .post<{ status: number; msg: string; data: unknown }>(
      "/query/modifyprivileges/",
      form(params),
      { headers: FORM_HEADERS }
    )
    .then((res) => checkStatus(res.data));
}

// ============ 详情 / 审核（新增 DRF） ============

export interface ReviewNodeInfo {
  group_name: string;
  is_current_node: boolean;
  is_passed_node: boolean;
  is_auto_pass: boolean;
}

export interface ApplyDetail {
  apply: {
    apply_id: number;
    title: string;
    group_name: string;
    user_display: string;
    user_name: string;
    instance_name: string;
    priv_type: number;
    db_list: string;
    table_list: string;
    limit_num: number | string;
    valid_date: string;
    status: number;
    create_time: string;
  };
  review_info: ReviewNodeInfo[];
  current_reviewers: { username: string; display: string }[];
  is_can_review: boolean;
  last_operation_info: string;
  logs: {
    operation_type_desc: string;
    operation_info: string;
    operator_display: string;
    operation_time: string;
  }[];
}

/** 申请详情（GET /api/v1/query_priv/<id>/） */
export function fetchApplyDetail(applyId: number) {
  return request
    .get<ApplyDetail>(`/api/v1/query_priv/${applyId}/`)
    .then((res) => res.data);
}

/** 审核（POST /api/v1/query_priv/audit/，audit_status 1=通过 / 2=驳回） */
export function auditApply(params: {
  apply_id: number;
  audit_status: 1 | 2;
  audit_remark?: string;
}) {
  return request
    .post<{ status: number; msg: string }>("/api/v1/query_priv/audit/", params)
    .then((res) => checkStatus(res.data));
}
