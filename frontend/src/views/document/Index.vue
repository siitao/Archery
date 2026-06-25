<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";
import { fetchDbAprinciples } from "@/api/document";

const loading = ref(false);
const error = ref(false);
const title = ref("相关文档");
const content = ref("");

// gfm 表格 / 换行，对齐旧版 marked.min.js 的 setOptions
marked.setOptions({ gfm: true, breaks: false });

const html = computed(() => {
  if (!content.value) return "";
  const raw = marked.parse(content.value, { async: false }) as string;
  return DOMPurify.sanitize(raw);
});

onMounted(async () => {
  loading.value = true;
  try {
    const doc = await fetchDbAprinciples();
    title.value = doc.title || "相关文档";
    content.value = doc.content;
  } catch {
    // 拦截器已提示
    error.value = true;
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div v-loading="loading" class="document-page">
    <el-card shadow="never">
      <template #header>{{ title }}</template>
      <el-alert
        v-if="error"
        type="error"
        :closable="false"
        title="文档加载失败，请稍后重试"
      />
      <article v-else class="markdown-body" v-html="html" />
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.document-page {
  display: flex;
  flex-direction: column;
}

/* v-html 注入的内容不带 scoped 属性，需用 :deep() 穿透 */
.markdown-body {
  color: var(--el-text-color-primary);
  font-size: 14px;
  line-height: 1.75;

  :deep() {
    h1,
    h2,
    h3,
    h4 {
      margin: 20px 0 10px;
      font-weight: 600;
      line-height: 1.4;
    }
    h1 {
      font-size: 22px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--el-border-color-lighter);
    }
    h2 {
      font-size: 18px;
    }
    h3 {
      font-size: 16px;
    }
    p {
      margin: 8px 0;
    }
    ul,
    ol {
      padding-left: 24px;
      margin: 8px 0;
    }
    li {
      margin: 4px 0;
    }
    code {
      padding: 2px 6px;
      background: var(--el-fill-color-light);
      border-radius: 4px;
      font-family: var(--el-font-family-mono, monospace);
      font-size: 13px;
    }
    pre {
      padding: 12px;
      margin: 10px 0;
      background: var(--el-fill-color-light);
      border-radius: 4px;
      overflow: auto;

      code {
        padding: 0;
        background: none;
      }
    }
    table {
      width: 100%;
      margin: 12px 0;
      border-collapse: collapse;
      overflow: auto;

      th,
      td {
        padding: 8px 12px;
        border: 1px solid var(--el-border-color);
        text-align: left;
      }
      th {
        background: var(--el-fill-color-light);
        font-weight: 600;
      }
      tr:nth-child(2n) td {
        background: var(--el-fill-color-blank);
      }
    }
    blockquote {
      margin: 10px 0;
      padding: 8px 14px;
      color: var(--el-text-color-secondary);
      border-left: 4px solid var(--el-border-color);
      background: var(--el-fill-color-light);
    }
    a {
      color: var(--el-color-primary);
      text-decoration: none;

      &:hover {
        text-decoration: underline;
      }
    }
  }
}
</style>
