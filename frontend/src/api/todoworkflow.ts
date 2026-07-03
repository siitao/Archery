import request from "@/utils/request";
import { type Paginated } from "@/api/instance";

/** 待办工作流类型：1=查询权限申请，2=SQL上线申请，3=数据归档申请 */
export const WORKFLOW_TYPE: Record<number, { label: string; type: "primary" | "success" | "warning" }> = {
  1: { label: "查询权限", type: "warning" },
  2: { label: "SQL上线", type: "primary" },
  3: { label: "数据归档", type: "success" },
};

/** 待办工作流审核状态（WorkflowAudit.current_status） */
export const AUDIT_STATUS: Record<number, { label: string; type: "info" | "success" | "danger" | "warning" }> = {
  0: { label: "待审核", type: "warning" },
  1: { label: "审核通过", type: "success" },
  2: { label: "审核不通过", type: "danger" },
  3: { label: "审核取消", type: "info" },
};

/** 待办行（对齐 WorkflowAuditListSerializer 输出） */
export interface TodoRow {
  audit_id: number;
  workflow_id: number;
  group_name: string;
  workflow_type: number;
  workflow_title: string;
  audit_auth_groups: string;
  current_audit: string;
  current_status: number;
  create_user_display: string;
  create_time: string;
}

/**
 * 待审核清单（POST /api/v1/workflow/auditlist/）。
 * 分页参数 page/size 走 query string；engineer 默认由后端取当前登录用户。
 */
export function fetchTodoList(params: { page?: number; size?: number; engineer?: string } = {}) {
  return request.post<Paginated<TodoRow>>("/api/v1/workflow/auditlist/", {
    engineer: params.engineer,
  }, {
    params: { page: params.page, size: params.size },
  });
}

/** 审核操作（POST /api/v1/workflow/audit/，通用版，支持全部 workflow_type） */
export function auditTodo(params: {
  engineer: string;
  workflow_id: number;
  workflow_type: number;
  audit_type: "pass" | "cancel";
  audit_remark: string;
}) {
  return request.post<{ msg: string }>("/api/v1/workflow/audit/", params);
}
