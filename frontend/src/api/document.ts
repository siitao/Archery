import request from "@/utils/request";

/** 相关文档（MySQL 设计规范）原文 + 标题。后端 sql_api/api_document.py 提供。 */
export interface DbAprinciplesDoc {
  title: string;
  content: string;
}

/** 获取相关文档的原始 Markdown 文本，交由前端渲染。 */
export function fetchDbAprinciples() {
  return request
    .get<DbAprinciplesDoc>("/api/v1/document/dbaprinciples/")
    .then((res) => res.data);
}
