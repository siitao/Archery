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
  // 仅保留仍使用旧路径的非 /api 端点：
  // - /instance/schemasync/（SchemaSync，sql/urls.py）
  // - /sqlexport/pre_check/（数据导出预检）
  // - /config/change/（配置管理）
  // - /downloadfile/（导出文件下载）
  // - /rollback/（回滚 SQL 下载）
  "/instance/": { target: apiTarget, changeOrigin: true },
  "/sqlexport/": { target: apiTarget, changeOrigin: true },
  "/config/": { target: apiTarget, changeOrigin: true },
  "/downloadfile/": { target: apiTarget, changeOrigin: true },
  "/rollback/": { target: apiTarget, changeOrigin: true },
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
