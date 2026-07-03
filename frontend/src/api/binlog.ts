import request from "@/utils/request";
import { ElMessage } from "element-plus";

/**
 * My2SQL（binlog 解析）。两个旧接口均通过 /api/v1/binlog/* POST form + {status,msg,data} 信封。
 * 复用 checkStatus/form 模式。数组参数 only_tables[]/sql_type[] 用 URLSearchParams 重复键。
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
    if (Array.isArray(v)) {
      for (const item of v) f.append(k, String(item));
    } else {
      f.append(k, String(v));
    }
  }
  return f;
}

const FORM_HEADERS = { "Content-Type": "application/x-www-form-urlencoded" };

/** binlog 文件行（show binary logs） */
export interface BinlogFile {
  Log_name: string;
  File_size: number | string;
  [key: string]: unknown;
}

/** 获取 binlog 列表（POST /binlog/list/） */
export function fetchBinlogList(instance_name: string) {
  return request
    .post<{ status: number; msg: string; data: BinlogFile[] }>(
      "/api/v1/binlog/list/",
      form({ instance_name }),
      { headers: FORM_HEADERS }
    )
    .then((res) => checkStatus(res.data).data || []);
}

/** 解析后的 SQL 行 */
export interface My2SqlRow {
  sql: string;
  extra_info?: string;
  [key: string]: unknown;
}

/** 运行 my2sql 解析 binlog → SQL（POST /binlog/my2sql/） */
export function runMy2sql(params: {
  instance_name: string;
  save_sql?: boolean;
  rollback?: boolean;
  extra_info?: boolean;
  ignore_primary_key?: boolean;
  full_columns?: boolean;
  no_db_prefix?: boolean;
  file_per_table?: boolean;
  threads?: number | string;
  num?: number | string;
  start_file: string;
  start_pos?: number | string;
  end_file?: string;
  end_pos?: number | string;
  stop_time?: string;
  start_time?: string;
  only_schemas?: string;
  only_tables?: string[];
  sql_type?: string[];
}) {
  const bool = (v?: boolean) => (v ? "true" : "false");
  return request
    .post<{ status: number; msg: string; data: My2SqlRow[] }>(
      "/api/v1/binlog/my2sql/",
      form({
        instance_name: params.instance_name,
        save_sql: bool(params.save_sql),
        rollback: bool(params.rollback),
        extra_info: bool(params.extra_info),
        ignore_primary_key: bool(params.ignore_primary_key),
        full_columns: bool(params.full_columns),
        no_db_prefix: bool(params.no_db_prefix),
        file_per_table: bool(params.file_per_table),
        threads: params.threads ?? "",
        num: params.num ?? "",
        start_file: params.start_file,
        start_pos: params.start_pos ?? "",
        end_file: params.end_file ?? "",
        end_pos: params.end_pos ?? "",
        stop_time: params.stop_time ?? "",
        start_time: params.start_time ?? "",
        only_schemas: params.only_schemas ?? "",
        "only_tables[]": params.only_tables ?? [],
        "sql_type[]": params.sql_type ?? [],
      }),
      { headers: FORM_HEADERS }
    )
    .then((res) => checkStatus(res.data).data || []);
}
