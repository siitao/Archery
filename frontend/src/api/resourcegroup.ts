import request from "@/utils/request";
import { type Paginated } from "@/api/instance";
import { ElMessage } from "element-plus";

// ============ 资源组（DRF） ============

export interface ResourceGroupRow {
  group_id: number;
  group_name: string;
  group_parent_id?: number | null;
  group_sort?: number;
  group_level?: number;
  ding_webhook?: string;
  feishu_webhook?: string;
  qywx_webhook?: string;
  [key: string]: unknown;
}

export interface ResourceGroupQuery {
  page?: number;
  size?: number;
  group_name__icontains?: string;
}

/** 资源组列表（GET /api/v1/user/resourcegroup/，DRF 分页） */
export function fetchResourceGroups(params: ResourceGroupQuery = {}) {
  return request.get<Paginated<ResourceGroupRow>>(
    "/api/v1/user/resourcegroup/",
    { params }
  );
}

/** 资源组详情（GET /api/v1/user/resourcegroup/<id>/） */
export function fetchResourceGroup(id: number) {
  return request.get<ResourceGroupRow>(`/api/v1/user/resourcegroup/${id}/`);
}

export function createResourceGroup(data: Partial<ResourceGroupRow>) {
  return request.post<ResourceGroupRow>("/api/v1/user/resourcegroup/", data);
}

export function updateResourceGroup(id: number, data: Partial<ResourceGroupRow>) {
  return request.put<ResourceGroupRow>(`/api/v1/user/resourcegroup/${id}/`, data);
}

/** 删除（后端软删） */
export function deleteResourceGroup(id: number) {
  return request.delete(`/api/v1/user/resourcegroup/${id}/`);
}

// ============ 关联管理（旧接口） ============

export interface RelationRow {
  object_type: 0 | 1; // 0=用户 1=实例
  object_id: number;
  object_name: string;
  group_id: number;
  group_name: string;
  [key: string]: unknown;
}

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
    f.append(k, typeof v === "string" ? v : JSON.stringify(v));
  }
  return f;
}

const FORM_HEADERS = { "Content-Type": "application/x-www-form-urlencoded" };

/** 关联对象列表（POST /group/relations/，{status,total,rows}。limit/offset 必传） */
export function fetchRelations(params: {
  group_id: number;
  type?: 0 | 1 | "";
  limit?: number;
  offset?: number;
  search?: string;
}) {
  return request
    .post<{ status: number; msg: string; total?: number; rows?: RelationRow[] }>(
      "/group/relations/",
      form({
        group_id: params.group_id,
        type: params.type ?? "",
        limit: params.limit ?? 1000,
        offset: params.offset ?? 0,
        search: params.search ?? "",
      }),
      { headers: FORM_HEADERS }
    )
    .then((res) => {
      const e = checkStatus(res.data);
      return { total: e.total || 0, rows: e.rows || [] };
    });
}

/** 未关联对象（POST /group/unassociated/，{status,rows,total}） */
export function fetchUnassociated(params: {
  group_id: number;
  object_type: 0 | 1;
}) {
  return request
    .post<{ status: number; msg: string; rows?: { object_id: number; object_name: string }[]; total?: number }>(
      "/group/unassociated/",
      form(params),
      { headers: FORM_HEADERS }
    )
    .then((res) => {
      const e = checkStatus(res.data);
      return e.rows || [];
    });
}

/** 新增关联（POST /group/addrelation/，object_info 为 ["id,name",...] JSON） */
export function addRelation(params: {
  group_id: number;
  object_type: 0 | 1;
  object_info: string[];
}) {
  return request
    .post<{ status: number; msg: string }>("/group/addrelation/", form(params), {
      headers: FORM_HEADERS,
    })
    .then((res) => checkStatus(res.data));
}

/** 移除关联（POST /group/removerelation/，新增接口） */
export function removeRelation(params: {
  group_id: number;
  object_type: 0 | 1;
  object_info: string[];
}) {
  return request
    .post<{ status: number; msg: string }>("/group/removerelation/", form(params), {
      headers: FORM_HEADERS,
    })
    .then((res) => checkStatus(res.data));
}

// ============ 审核流配置（旧接口） ============

export interface AuditorsData {
  auditors: string;
  auditors_display: string;
}

/** 获取审核流（POST /group/auditors/） */
export function fetchAuditors(group_name: string, workflow_type: number) {
  return request
    .post<{ status: number; msg: string; data?: AuditorsData }>(
      "/group/auditors/",
      form({ group_name, workflow_type }),
      { headers: FORM_HEADERS }
    )
    .then((res) => checkStatus(res.data).data as AuditorsData);
}

/** 修改审核流（POST /group/changeauditors/，audit_auth_groups 为逗号分隔的 name） */
export function changeAuditors(params: {
  group_name: string;
  audit_auth_groups: string;
  workflow_type: number;
}) {
  return request
    .post<{ status: number; msg: string }>("/group/changeauditors/", form(params), {
      headers: FORM_HEADERS,
    })
    .then((res) => checkStatus(res.data));
}

// ============ auth 用户组（审核流配置用，DRF GroupList） ============

export interface AuthGroupRow {
  id: number;
  name: string;
}

export function fetchAuthGroups() {
  return request.get<Paginated<AuthGroupRow>>("/api/v1/user/group/", {
    params: { size: 1000 },
  });
}
