import request from "@/utils/request";
import { ElMessage } from "element-plus";

/**
 * 数据归档（PTArchiver）。旧接口 /api/v1/archive/*（list/log/once 为 GET，apply/audit/switch 为 POST），
 * 信封 {total,rows} 或 {status,msg,data}。详情/审核走新增 DRF /api/v1/archive/*。
 * 复用 checkStatus/form 模式（参考 querypriv.ts）。申请 workflow_type=3（ArchiveConfig）。
 */

function checkStatus<T extends { status?: number; msg?: string }>(env: T): T {
  if (env.status !== 0) {
    ElMessage.error(env.msg || "操作失败");
    throw new Error(env.msg || "operation failed");
  }
  return env;
}

function form(obj: Record<string, unknown>) {
  const f = new URLSearchParams();
  for (const [k, v] of Object.entries(obj)) {
    if (v === undefined || v === null || v === "") continue;
    f.append(k, typeof v === "string" ? v : String(v));
  }
  return f;
}

const FORM_HEADERS = { "Content-Type": "application/x-www-form-urlencoded" };

// ============ 常量 ============

/** 归档模式（ArchiveConfig.mode） */
export const ARCHIVE_MODE: Record<string, string> = {
  file: "归档到文件",
  dest: "归档到其他实例",
  purge: "直接删除",
};

/** 工单状态（WorkflowStatus） */
export const ARCHIVE_STATUS: Record<
  number,
  { label: string; type: "success" | "info" | "warning" | "danger" }
> = {
  0: { label: "待审核", type: "info" },
  1: { label: "审核通过", type: "success" },
  2: { label: "审核不通过", type: "danger" },
  3: { label: "审核取消", type: "warning" },
};

// ============ 归档列表 / 申请 / 日志 / 开关 / 单次 ============

export interface ArchiveRow {
  id: number;
  title: string;
  src_instance__instance_name: string;
  src_db_name: string;
  src_table_name: string;
  dest_instance__instance_name?: string;
  dest_db_name?: string;
  dest_table_name?: string;
  sleep: number;
  mode: string;
  no_delete: boolean;
  status: number;
  state: boolean;
  user_display: string;
  create_time: string;
  resource_group__group_name: string;
}

/** 归档列表（GET /archive/list/） */
export function fetchArchiveList(params: {
  limit: number;
  offset: number;
  search?: string;
  filter_instance_id?: number | string;
  state?: "true" | "false" | "";
}) {
  return request
    .get<{ total: number; rows: ArchiveRow[] }>("/api/v1/archive/list/", { params })
    .then((res) => ({ total: res.data.total || 0, rows: res.data.rows || [] }));
}

/** 申请归档（POST /archive/apply/）。mode file/dest/purge */
export function archiveApply(params: {
  title: string;
  group_name: string;
  src_instance_name: string;
  src_db_name: string;
  src_table_name: string;
  mode: string;
  dest_instance_name?: string;
  dest_db_name?: string;
  dest_table_name?: string;
  condition: string;
  no_delete: boolean;
  sleep?: number;
}) {
  return request
    .post<{ status: number; msg: string; data: { archive_id?: number } }>(
      "/api/v1/archive/apply/",
      form({
        title: params.title,
        group_name: params.group_name,
        src_instance_name: params.src_instance_name,
        src_db_name: params.src_db_name,
        src_table_name: params.src_table_name,
        mode: params.mode,
        dest_instance_name: params.dest_instance_name ?? "",
        dest_db_name: params.dest_db_name ?? "",
        dest_table_name: params.dest_table_name ?? "",
        condition: params.condition,
        no_delete: params.no_delete ? "true" : "false",
        sleep: params.sleep ?? 0,
      }),
      { headers: FORM_HEADERS }
    )
    .then((res) => checkStatus(res.data));
}

export interface ArchiveLogRow {
  id?: number;
  cmd: string;
  info: string;
  condition: string;
  mode: string;
  no_delete: boolean;
  select_cnt: number;
  insert_cnt: number;
  delete_cnt: number;
  success: boolean;
  error_info: string;
  start_time: string;
  end_time: string;
}

/** 归档日志（GET /archive/log/） */
export function fetchArchiveLog(params: {
  archive_id: number;
  limit: number;
  offset: number;
}) {
  return request
    .get<{ total: number; rows: ArchiveLogRow[] }>("/api/v1/archive/log/", { params })
    .then((res) => ({ total: res.data.total || 0, rows: res.data.rows || [] }));
}

/** 开启/关闭归档任务（POST /archive/switch/） */
export function archiveSwitch(archive_id: number, state: boolean) {
  return request
    .post<{ status: number; msg: string; data: unknown }>(
      "/api/v1/archive/switch/",
      form({ archive_id, state: state ? "true" : "false" }),
      { headers: FORM_HEADERS }
    )
    .then((res) => checkStatus(res.data));
}

/** 单次立即执行归档（GET /archive/once/，触发 django-q 异步任务） */
export function archiveOnce(archive_id: number) {
  return request
    .get<{ status: number; msg: string; data: unknown }>("/api/v1/archive/once/", {
      params: { archive_id },
    })
    .then((res) => checkStatus(res.data));
}

// ============ 详情 / 审核（新增 DRF） ============

export interface ArchiveReviewNode {
  group_name: string;
  is_current_node: boolean;
  is_passed_node: boolean;
  is_auto_pass: boolean;
}

export interface ArchiveDetail {
  archive: {
    id: number;
    title: string;
    group_name: string;
    src_instance_name: string;
    src_db_name: string;
    src_table_name: string;
    dest_instance_name: string;
    dest_db_name: string;
    dest_table_name: string;
    mode: string;
    no_delete: boolean;
    sleep: number;
    condition: string;
    status: number;
    state: boolean;
    user_display: string;
    create_time: string;
  };
  review_info: ArchiveReviewNode[];
  current_reviewers: { username: string; display: string }[];
  can_review: boolean;
  last_operation_info: string;
  logs: {
    operation_type_desc: string;
    operation_info: string;
    operator_display: string;
    operation_time: string;
  }[];
}

/** 归档详情（GET /api/v1/archive/<id>/） */
export function fetchArchiveDetail(id: number) {
  return request.get<ArchiveDetail>(`/api/v1/archive/${id}/`).then((res) => res.data);
}

/** 审核（POST /api/v1/archive/audit/，audit_status 1=通过 / 2=驳回） */
export function archiveAudit(params: {
  archive_id: number;
  audit_status: 1 | 2;
  audit_remark?: string;
}) {
  return request
    .post<{ status: number; msg: string }>("/api/v1/archive/audit/", params)
    .then((res) => checkStatus(res.data));
}
