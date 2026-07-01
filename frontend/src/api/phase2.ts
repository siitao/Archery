import request from "@/utils/request";
import { ElMessage } from "element-plus";

/**
 * Phase 2 批次 1：6 个只读页的旧 JSON 接口封装。
 * 复用 checkStatus/form 模式（参考 instance_admin.ts），旧接口 POST form + {status,msg,data/rows} 信封。
 * 所有必传参数（含 limit/offset，避免 int(None)）都给默认值。
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
    if (v === undefined || v === null) continue;
    f.append(k, typeof v === "string" ? v : String(v));
  }
  return f;
}

const FORM_HEADERS = { "Content-Type": "application/x-www-form-urlencoded" };

// ============ SQL 分析 sql_analyze.py ============

/** 生成分析（行级结果） */
export function generateAnalyze(text: string) {
  return request
    .post<{ status: number; msg: string; total?: number; rows?: Record<string, unknown>[] }>(
      "/sql_analyze/generate/",
      form({ text }),
      { headers: FORM_HEADERS }
    )
    .then((res) => {
      const e = checkStatus(res.data);
      return { total: e.total || 0, rows: e.rows || [] };
    });
}

/** 深度分析（soar markdown 报告） */
export function analyzeSql(params: {
  text: string;
  instance_name: string;
  db_name: string;
}) {
  return request
    .post<{ status: number; msg: string; data?: string }>("/sql_analyze/analyze/", form(params), {
      headers: FORM_HEADERS,
    })
    .then((res) => checkStatus(res.data).data || "");
}

// ============ 数据字典 data_dictionary.py（全 GET） ============

export type DictionaryObjectType =
  | "table"
  | "view"
  | "trigger"
  | "procedure"
  | "function"
  | "event";

const DD_TYPE_MAP: Record<DictionaryObjectType, { list: string; info: string; nameParam: string }> = {
  table: { list: "table_list", info: "table_info", nameParam: "tb_name" },
  view: { list: "view_list", info: "view_info", nameParam: "view_name" },
  trigger: { list: "trigger_list", info: "trigger_info", nameParam: "trigger_name" },
  procedure: { list: "procedure_list", info: "procedure_info", nameParam: "procedure_name" },
  function: { list: "function_list", info: "function_info", nameParam: "function_name" },
  event: { list: "event_list", info: "event_info", nameParam: "event_name" },
};

/** 对象列表（GET /data_dictionary/<type>_list/）

    实际后端返回格式:
    { status:0, data: { "a": [["name","comment"],...], "n": [...] } }
    即按首字母分组、每项 [name, comment]。
    兼容旧格式 rows: [{name}]。
*/
export function fetchDictionaryObjects(params: {
  instance_name: string;
  db_name: string;
  db_type?: string;
  object_type: DictionaryObjectType;
}): Promise<{ name: string; comment: string }[]> {
  const path = `/data_dictionary/${DD_TYPE_MAP[params.object_type].list}/`;
  return request
    .get<{ status: number; msg: string; rows?: [string, string][]; data?: Record<string, [string, string][]> | { name: string }[] }>(
      path,
      {
        params: {
          instance_name: params.instance_name,
          db_name: params.db_name,
          db_type: params.db_type || "",
        },
      }
    )
    .then((res) => {
      const e = checkStatus(res.data);
      // 新格式：data 是按首字母分组的对象 { letter: [[name, comment], ...] }
      if (e.data && !Array.isArray(e.data) && typeof e.data === "object") {
        return Object.values(e.data)
          .flat()
          .map((pair) => ({ name: pair[0], comment: pair[1] ?? "" }));
      }
      // 旧格式：rows 是 [[name, comment], ...] 或 [{name}, ...]
      const rows = e.rows ?? (Array.isArray(e.data) ? e.data : []);
      return rows.map((r: any) =>
        Array.isArray(r)
          ? { name: r[0], comment: r[1] ?? "" }
          : { name: r.name ?? String(r), comment: r.comment ?? "" }
      );
    });
}

/** 对象定义（GET /data_dictionary/<type>_info/） */
export function fetchDictionaryInfo(params: {
  instance_name: string;
  db_name: string;
  db_type?: string;
  object_type: DictionaryObjectType;
  object_name: string;
}) {
  const meta = DD_TYPE_MAP[params.object_type];
  const path = `/data_dictionary/${meta.info}/`;
  return request
    .get<{ status: number; msg: string; data?: string; rows?: Record<string, unknown>[] }>(path, {
      params: {
        instance_name: params.instance_name,
        db_name: params.db_name,
        db_type: params.db_type || "",
        [meta.nameParam]: params.object_name,
      },
    })
    .then((res) => checkStatus(res.data).data || "");
}

/** 导出数据字典（GET /data_dictionary/export/，返回 HTML 文件，blob 下载） */
export function exportDictionary(params: {
  instance_name: string;
  db_name: string;
  db_type?: string;
}) {
  return request.get<Blob>("/data_dictionary/export/", {
    params: {
      instance_name: params.instance_name,
      db_name: params.db_name,
      db_type: params.db_type || "",
    },
    responseType: "blob",
  });
}

// ============ 优化工具 sql_optimize.py ============

/** SQLAdvisor 建议 */
export function optimizeSqlAdvisor(params: {
  instance_name: string;
  db_name: string;
  sql_content: string;
  verbose?: number;
}) {
  return request
    .post<{ status: number; msg: string; data?: string }>(
      "/slowquery/optimize_sqladvisor/",
      form({ ...params, verbose: params.verbose ?? 1 }),
      { headers: FORM_HEADERS }
    )
    .then((res) => checkStatus(res.data).data || "");
}

/** SOAR 建议（markdown） */
export function optimizeSoar(params: {
  instance_name: string;
  db_name: string;
  sql: string;
}) {
  return request
    .post<{ status: number; msg: string; data?: string }>("/slowquery/optimize_soar/", form(params), {
      headers: FORM_HEADERS,
    })
    .then((res) => checkStatus(res.data).data || "");
}

/** MySQL 调优 */
export function optimizeSqlTuning(params: {
  instance_name: string;
  db_name: string;
  sql_content: string;
}) {
  return request
    .post<{ status: number; msg: string; data?: string }>(
      "/slowquery/optimize_sqltuning/",
      form(params),
      { headers: FORM_HEADERS }
    )
    .then((res) => checkStatus(res.data).data || "");
}

/** 执行计划（POST /query/explain/，返回 {column_list, rows}） */
export function explainSql(params: {
  instance_name: string;
  db_name: string;
  sql_content: string;
}) {
  return request
    .post<{ status: number; msg: string; data?: { column_list?: string[]; rows?: unknown[][] } }>(
      "/query/explain/",
      form(params),
      { headers: FORM_HEADERS }
    )
    .then((res) => checkStatus(res.data).data || { column_list: [], rows: [] });
}

// ============ 慢查日志 slowlog.py ============

/** 慢查统计（POST /slowquery/review/，{total,rows}） */
export function fetchSlowReview(params: {
  instance_name: string;
  db_name?: string;
  StartTime?: string;
  EndTime?: string;
  limit?: number;
  offset?: number;
  search?: string;
}) {
  return request
    .post<{ status: number; msg: string; total?: number; rows?: Record<string, unknown>[] }>(
      "/slowquery/review/",
      form({
        instance_name: params.instance_name,
        db_name: params.db_name ?? "",
        StartTime: params.StartTime ?? "",
        EndTime: params.EndTime ?? "",
        limit: params.limit ?? 1000,
        offset: params.offset ?? 0,
        search: params.search ?? "",
        sortName: "",
        sortOrder: "",
      }),
      { headers: FORM_HEADERS }
    )
    .then((res) => {
      const e = checkStatus(res.data);
      return { total: e.total || 0, rows: e.rows || [] };
    });
}

/** 慢查明细（POST /slowquery/review_history/） */
export function fetchSlowHistory(params: {
  instance_name: string;
  db_name?: string;
  StartTime?: string;
  EndTime?: string;
  SQLId?: string;
  limit?: number;
  offset?: number;
  search?: string;
}) {
  return request
    .post<{ status: number; msg: string; total?: number; rows?: Record<string, unknown>[] }>(
      "/slowquery/review_history/",
      form({
        instance_name: params.instance_name,
        db_name: params.db_name ?? "",
        StartTime: params.StartTime ?? "",
        EndTime: params.EndTime ?? "",
        SQLId: params.SQLId ?? "",
        limit: params.limit ?? 1000,
        offset: params.offset ?? 0,
        search: params.search ?? "",
        sortName: "",
        sortOrder: "",
      }),
      { headers: FORM_HEADERS }
    )
    .then((res) => {
      const e = checkStatus(res.data);
      return { total: e.total || 0, rows: e.rows || [] };
    });
}

/** 慢查趋势数据（GET /api/v1/slowquery/trend/，新 DRF；双 series 慢查次数 + 慢查时长95%） */
export function fetchSlowTrend(checksum: string, instanceName: string) {
  return request
    .get<{ x: string[]; series: { name: string; data: (number | string)[] }[] }>(
      "/api/v1/slowquery/trend/",
      { params: { checksum, instance_name: instanceName } }
    )
    .then((res) => res.data);
}

// ============ SchemaSync instance.py ============

export interface SchemaSyncResult {
  diff_stdout: string;
  patch_stdout: string;
  revert_stdout: string;
  [key: string]: unknown;
}

/** SchemaSync 对比（POST /instance/schemasync/） */
export function schemaSync(params: {
  instance_name: string;
  db_name: string;
  target_instance_name: string;
  target_db_name: string;
  sync_auto_inc?: boolean;
  sync_comments?: boolean;
}) {
  return request
    .post<{ status: number; msg: string; data?: SchemaSyncResult }>(
      "/instance/schemasync/",
      form({
        instance_name: params.instance_name,
        db_name: params.db_name,
        target_instance_name: params.target_instance_name,
        target_db_name: params.target_db_name,
        sync_auto_inc: params.sync_auto_inc ? "true" : "false",
        sync_comments: params.sync_comments ? "true" : "false",
      }),
      { headers: FORM_HEADERS }
    )
    .then((res) => checkStatus(res.data).data as SchemaSyncResult);
}

// ============ 系统审计 audit_log.py + 复用工单/查询审计 ============

/** 通用审计日志（POST /audit/log/，limit/offset 有默认） */
export function fetchAuditLog(params: {
  limit?: number;
  offset?: number;
  search?: string;
  action?: string;
  start_date?: string;
  end_date?: string;
}) {
  return request
    .post<{ status: number; msg: string; total?: number; rows?: Record<string, unknown>[] }>(
      "/audit/log/",
      form(params),
      { headers: FORM_HEADERS }
    )
    .then((res) => {
      // 旧接口返回 {total,rows} 无 status 字段，checkStatus 会误判；直接取数据
      const d = res.data as Record<string, unknown>;
      return { total: (d.total as number) || 0, rows: (d.rows as Record<string, unknown>[]) || [] };
    });
}

/** SQL 上线工单审计（POST /sqlworkflow_list_audit/，limit/offset 有默认） */
export function fetchWorkflowAudit(params: {
  limit?: number;
  offset?: number;
  search?: string;
}) {
  return request
    .post<{ total?: number; rows?: Record<string, unknown>[] }>(
      "/sqlworkflow_list_audit/",
      form(params),
      { headers: FORM_HEADERS }
    )
    .then((res) => {
      const d = res.data as Record<string, unknown>;
      return { total: (d.total as number) || 0, rows: (d.rows as Record<string, unknown>[]) || [] };
    });
}

/** 查询日志审计（POST /query/querylog_audit/） */
export function fetchQueryLogAudit(params: {
  limit?: number;
  offset?: number;
  search?: string;
}) {
  return request
    .post<{ total?: number; rows?: Record<string, unknown>[] }>(
      "/query/querylog_audit/",
      form(params),
      { headers: FORM_HEADERS }
    )
    .then((res) => {
      const d = res.data as Record<string, unknown>;
      return { total: (d.total as number) || 0, rows: (d.rows as Record<string, unknown>[]) || [] };
    });
}
