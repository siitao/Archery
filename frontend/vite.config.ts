import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import AutoImport from "unplugin-auto-import/vite";
import Components from "unplugin-vue-components/vite";
import { ElementPlusResolver } from "unplugin-vue-components/resolvers";
import { fileURLToPath, URL } from "node:url";

// 后端 Django 地址（开发期）。生产期 SPA 与 API 同源，无需代理。
const apiTarget = process.env.ARCHERY_API_TARGET || "http://localhost:8000";

// 仅代理 API 与少量非 /api 的接口。
// 注意：不要代理与 SPA 路由同前缀的路径（如 /dashboard、/instance、/login），
// 否则刷新页面会被转发到 Django 而非返回 index.html。
// 旧页面通过 VITE_LEGACY_BASE 直连后端在新标签打开，保持迁移期共存。
const proxy = {
  "/api": { target: apiTarget, changeOrigin: true },
  "/authenticate": { target: apiTarget, changeOrigin: true },
  "/logout": { target: apiTarget, changeOrigin: true },
  "/dashboard/api": { target: apiTarget, changeOrigin: true },
  "/jsi18n": { target: apiTarget, changeOrigin: true },
  // 旧 JSON 接口（迁移期 SPA 调用）。带尾斜杠避免与 SPA 路由冲突：
  //   /instance/ 不匹配 SPA 的 /instance；/param/ 不匹配 SPA 的 /paramcompare
  //   /audit/ 不匹配 SPA 的 /audit；/slowquery/ 不匹配 SPA 的 /slowquery
  "/group/": { target: apiTarget, changeOrigin: true },
  "/db_diagnostic/": { target: apiTarget, changeOrigin: true },
  "/instance/": { target: apiTarget, changeOrigin: true },
  "/param/": { target: apiTarget, changeOrigin: true },
  "/query/": { target: apiTarget, changeOrigin: true },
  "/check/": { target: apiTarget, changeOrigin: true },
  // Phase 2 批次 1：SQL 分析 / 数据字典 / 慢查日志+优化工具 / 系统审计
  "/sql_analyze/": { target: apiTarget, changeOrigin: true },
  "/data_dictionary/": { target: apiTarget, changeOrigin: true },
  "/slowquery/": { target: apiTarget, changeOrigin: true },
  "/audit/": { target: apiTarget, changeOrigin: true },
  "/sqlworkflow_list_audit/": { target: apiTarget, changeOrigin: true },
  // 数据导出：提交前预检
  "/sqlexport/": { target: apiTarget, changeOrigin: true },
  // 数据归档（PTArchiver）：list/apply/audit/log/switch/once
  "/archive/": { target: apiTarget, changeOrigin: true },
  // My2SQL：binlog 列表 / 解析
  "/binlog/": { target: apiTarget, changeOrigin: true },
  // 数据导出：导出文件下载（local/sftp 文件流 / 云存储重定向）
  "/downloadfile/": { target: apiTarget, changeOrigin: true },
  // SQL 上线 Step E：回滚语句查看（backup_sql）/ 下载（rollback）
  // 用完整路径，避免与 SPA 的 /sqlworkflow/:id、/sqlworkflow/submit 路由前缀冲突
  "/sqlworkflow/backup_sql/": { target: apiTarget, changeOrigin: true },
  "/rollback/": { target: apiTarget, changeOrigin: true },
  // SQL 上线 Step E：OSC 进度控制（goInception pt-osc/gh-ost）
  "/inception/osc_control/": { target: apiTarget, changeOrigin: true },
};

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      imports: ["vue", "vue-router", "pinia"],
      resolvers: [ElementPlusResolver()],
      dts: "src/auto-imports.d.ts",
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: "src/components.d.ts",
    }),
  ],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy,
  },
});
