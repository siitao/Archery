<script setup lang="ts">
/** OpenAPI（drf-spectacular Swagger UI）以 iframe 嵌入 SPA，避免跳旧版。
 * 同源，登录态自动带 cookie。 */
const src = "/api/swagger/";
</script>

<template>
  <div class="openapi-page">
    <iframe :src="src" class="openapi-frame" title="OpenAPI" />
  </div>
</template>

<style scoped lang="scss">
.openapi-page {
  height: calc(100vh - 140px);
}

.openapi-frame {
  width: 100%;
  height: 100%;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
  background: #fff;
}
</style>
