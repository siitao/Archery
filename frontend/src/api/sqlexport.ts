import request from "@/utils/request";
import { ElMessage } from "element-plus";
import { type Paginated } from "@/api/instance";
import {
  type SqlWorkflowRow,
  type SqlWorkflowQuery,
  type ReviewRow,
} from "@/api/sqlworkflow";

/**
 * 数据导出工单。导出工单复用 SqlWorkflow（workflow_type=2 SQL 上线，syntax_type=3 数据导出，
 * 带 export_format + is_offline_export=1）。列表/日志复用 workflow 接口，校验走专用 pre_check。
 */

/** 导出格式（SqlWorkflow.export_format） */
export const EXPORT_FORMATS: { value: string; label: string }[] = [
  { value: "csv", label: "CSV" },
  { value: "xlsx", label: "Excel" },
  { value: "sql", label: "SQL" },
  { value: "json", label: "JSON" },
  { value: "xml", label: "XML" },
];

export const EXPORT_FORMAT_LABEL: Record<string, string> = Object.fromEntries(
  EXPORT_FORMATS.map((f) => [f.value, f.label])
);

/** 导出工单列表（GET /api/v1/workflow/，固定 syntax_type=3） */
export function fetchExportWorkflows(params: SqlWorkflowQuery = {}) {
  return request.get<Paginated<SqlWorkflowRow>>("/api/v1/workflow/", {
    params: { ...params, "workflow__syntax_type": 3 },
  });
}

/** 导出校验结果（{status,msg,data} 信封；data.rows 为 ReviewRow[]，可直接喂 SqlReviewTable） */
export interface ExportPreCheckResult {
  error_count: number;
  warning_count: number;
  rows: ReviewRow[];
}

function form(obj: Record<string, unknown>) {
  const f = new URLSearchParams();
  for (const [k, v] of Object.entries(obj)) {
    if (v === undefined || v === null) continue;
    f.append(k, typeof v === "string" ? v : String(v));
  }
  return f;
}

const FORM_HEADERS = { "Content-Type": "application/x-www-form-urlencoded" };

/**
 * 导出预检（POST /sqlexport/pre_check/）。服务端内置 max_export_rows 阈值校验。
 * 注意：校验「未通过」时 status=1 但 data 仍带 error_count/rows，需交给 UI 按 error_count 判断；
 * 仅当无 data（参数缺失/实例未关联）时视为请求级错误抛出。
 */
export function exportPreCheck(params: {
  instance_name: string;
  db_name: string;
  sql_content: string;
}) {
  return request
    .post<{ status: number; msg: string; data?: ExportPreCheckResult }>(
      "/sqlexport/pre_check/",
      form(params),
      { headers: FORM_HEADERS }
    )
    .then((res) => {
      const e = res.data;
      if (e.data) {
        return {
          error_count: e.data.error_count ?? 0,
          warning_count: e.data.warning_count ?? 0,
          rows: Array.isArray(e.data.rows) ? (e.data.rows as ReviewRow[]) : [],
        };
      }
      ElMessage.error(e.msg || "校验失败");
      throw new Error(e.msg || "pre_check failed");
    });
}
