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
