/// <reference types="vite/client" />

declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>;
  export default component;
}

interface ImportMetaEnv {
  /** 旧版页面直连后端地址；为空时按相对路径处理（生产同源） */
  readonly VITE_LEGACY_BASE: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
