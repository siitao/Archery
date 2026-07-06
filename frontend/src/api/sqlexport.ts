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

/**
 * 导出预检（POST /api/v1/sqlexport/pre_check/）。服务端内置 max_export_rows 阈值校验。
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
      "/api/v1/sqlexport/pre_check/",
      params
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

/**
 * 下载导出文件（GET /api/v1/downloadfile/）。
 * local/sftp 返回文件流（直接触发下载）；云存储（s3c/azure）返回 JSON {type:'redirect',url} 重定向；
 * 文件不存在/失败返回 JSON {error}。复刻旧版 detail.html 的探测+分流逻辑。
 */
export async function downloadExportFile(workflowId: number, fileName: string) {
  const filePath = `/api/v1/downloadfile/?file_name=${encodeURIComponent(fileName)}&workflow_id=${workflowId}`;
  // HEAD 探测：JSON 响应=重定向或错误；否则=文件流
  const head = await fetch(filePath, { method: "HEAD", cache: "no-store" });
  const ct = head.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    const res = await fetch(filePath);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    if (data.type === "redirect") {
      window.location.href = data.url;
      return;
    }
    throw new Error("未知的响应格式");
  }
  // 文件流：触发附件下载
  const a = document.createElement("a");
  a.href = filePath;
  a.download = fileName;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}
