import request from "@/utils/request";

/** 全部配置 key-value 字典（GET /api/v1/config/，superuser 专用） */
export function fetchConfig() {
  return request.get<Record<string, unknown>>("/api/v1/config/").then((r) => r.data);
}

/** 保存全部配置（POST /config/change/，旧接口 [{key,value}] JSON）。
 * 多选字段数组值自动 join 成逗号字符串。 */
export function saveConfig(values: Record<string, unknown>) {
  const configs = Object.entries(values).map(([key, value]) => ({
    key,
    value: Array.isArray(value) ? value.join(",") : String(value ?? ""),
  }));
  const form = new URLSearchParams();
  form.append("configs", JSON.stringify(configs));
  return request
    .post<{ status: number; msg: string }>("/config/change/", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    })
    .then((res) => {
      if (res.data.status !== 0) {
        throw new Error(res.data.msg || "保存失败");
      }
      return res.data;
    });
}

/** goInception 连接测试（POST /check/go_inception/） */
export function checkGoInception(params: {
  go_inception_host: string;
  go_inception_port: string;
  go_inception_user: string;
  go_inception_password: string;
  inception_remote_backup_host: string;
  inception_remote_backup_port: string;
  inception_remote_backup_user: string;
  inception_remote_backup_password: string;
}) {
  const form = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => form.append(k, String(v ?? "")));
  return request
    .post<{ status: number; msg: string }>("/check/go_inception/", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    })
    .then((res) => {
      if (res.data.status !== 0) {
        throw new Error(res.data.msg || "连接测试失败");
      }
      return res.data;
    });
}
