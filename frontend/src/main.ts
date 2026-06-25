import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";
import { setUnauthorizedHandler } from "./utils/request";
import { useAuthStore } from "./stores/auth";
import * as ElementPlusIconsVue from "@element-plus/icons-vue";

// Element Plus 全量样式（含 ElMessage / ElMessageBox 等命令式组件所需样式）
import "element-plus/dist/index.css";
import "element-plus/theme-chalk/dark/css-vars.css";
import "./styles/index.scss";

const app = createApp(App);
app.use(createPinia());
app.use(router);

// 全局注册 Element Plus 图标，供菜单等处以 <component :is="..."> 使用
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component);
}

// 401（会话失效）：清空登录态并跳回登录页（已在公开路由则不动）
setUnauthorizedHandler(() => {
  const auth = useAuthStore();
  auth.clear();
  const current = router.currentRoute.value;
  if (current.name !== "login" && !current.meta.public) {
    router.replace({ name: "login", query: { redirect: current.fullPath } });
  }
});

app.mount("#app");
