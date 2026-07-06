import request from "@/utils/request";

/** 全部配置 key-value 字典（GET /api/v1/config/，superuser 专用） */
export function fetchConfig() {
  return request.get<Record<string, unknown>>("/api/v1/config/").then((r) => r.data);
}

/** 保存全部配置（POST /api/v1/config/change/，body: {configs:[{key,value}]}）。
 * 多选字段数组值自动 join 成逗号字符串。 */
export function saveConfig(values: Record<string, unknown>) {
  const configs = Object.entries(values).map(([key, value]) => ({
    key,
    value: Array.isArray(value) ? value.join(",") : String(value ?? ""),
  }));
  return request
    .post<{ status: number; msg: string }>("/api/v1/config/change/", { configs })
    .then((res) => {
      if (res.data.status !== 0) {
        throw new Error(res.data.msg || "保存失败");
      }
      return res.data;
    });
}

/** goInception 连接测试（POST /api/v1/config/check_inception/） */
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
  return request
    .post<{ status: number; msg: string }>("/api/v1/config/check_inception/", params)
    .then((res) => {
      if (res.data.status !== 0) {
        throw new Error(res.data.msg || "连接测试失败");
      }
      return res.data;
    });
}

/** AI 服务连接测试（POST /api/v1/config/check_ai/，测试当前表单输入值） */
export function checkAIConnection(params: {
  openai_base_url: string;
  openai_api_key: string;
  default_chat_model: string;
}) {
  return request
    .post<{ status: number; msg: string }>("/api/v1/config/check_ai/", params)
    .then((res) => {
      if (res.data.status !== 0) {
        throw new Error(res.data.msg || "连接测试失败");
      }
      return res.data;
    });
}
