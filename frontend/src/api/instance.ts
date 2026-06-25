import request from "@/utils/request";

export interface InstanceRow {
  id: number;
  instance_name: string;
  type: string;
  db_type: string;
  mode?: string;
  host: string;
  port: number;
  user: string;
  db_name?: string;
  charset?: string;
  [key: string]: unknown;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface InstanceQuery {
  page?: number;
  size?: number;
  /** InstanceFilter: instance_name__icontains */
  instance_name__icontains?: string;
  db_type?: string;
  host?: string;
}

/** 实例列表（DRF InstanceList，CustomizedPagination） */
export function fetchInstances(params: InstanceQuery = {}) {
  return request.get<Paginated<InstanceRow>>("/api/v1/instance/", { params });
}
