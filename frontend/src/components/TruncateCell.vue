<script setup lang="ts">
/** 截断长文本 + 点击展开弹窗的通用表格单元格组件。

 *  用于 el-table-column 的 #default slot：
 *    <el-table-column label="SQL">
 *      <template #default="{ row }">
 *        <TruncateCell :value="row.sql" />
 *      </template>
 *    </el-table-column>
 *
 *  动态列表头可通过 titleField 从行数据生成弹窗标题：
 *    <TruncateCell :value="row.info" title-field="id" :row="row" col="info" />
 */
import { ref, computed } from "vue";
import { ElMessage } from "element-plus";
import { CopyDocument } from "@element-plus/icons-vue";

const props = withDefaults(
  defineProps<{
    value: unknown;
    /** 截断阈值（默认 120 字符） */
    maxLen?: number;
    /** 弹窗标题中显示的字段名（如 "SQL 详情"），col 不为空则用 "详情 — {col}" */
    col?: string;
    /** 行数据引用（可选，用于拼接弹窗标题，如 #id） */
    row?: Record<string, unknown>;
    /** 行内标识字段名（默认 "id"，用于拼接弹窗标题） */
    titleField?: string;
  }>(),
  { maxLen: 120, col: "", row: undefined, titleField: "id" }
);

const visible = ref(false);
const content = ref("");

const displayText = computed(() => {
  const s = String(props.value ?? "");
  return s.length > props.maxLen ? s.substring(0, props.maxLen) + " …" : s;
});

const truncated = computed(() => String(props.value ?? "").length > props.maxLen);

const title = computed(() => {
  if (props.col) {
    const rid =
      (props.row as Record<string, unknown> | undefined)?.[
        props.titleField
      ] ?? "?";
    return `详情 — ${props.col}（#${rid}）`;
  }
  return "详情";
});

function open() {
  content.value = String(props.value ?? "");
  visible.value = true;
}

async function copyContent() {
  try {
    await navigator.clipboard.writeText(content.value);
    ElMessage.success("已复制到剪贴板");
  } catch {
    // 降级方案
    const textarea = document.createElement("textarea");
    textarea.value = content.value;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
    ElMessage.success("已复制到剪贴板");
  }
}
</script>

<template>
  <span class="tc-root">
    <span>{{ displayText }}</span>
    <el-button v-if="truncated" link type="primary" @click="open">
      展开
    </el-button>
  </span>
  <el-dialog v-model="visible" :title="title" width="800px" append-to-body>
    <template #header>
      <div class="tc-dialog-header">
        <span>{{ title }}</span>
        <el-button type="primary" size="small" @click="copyContent">
          <el-icon><CopyDocument /></el-icon>
          复制
        </el-button>
      </div>
    </template>
    <pre class="tc-pre">{{ content }}</pre>
  </el-dialog>
</template>

<style scoped lang="scss">
.tc-root {
  word-break: break-all;
}

.tc-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.tc-pre {
  margin: 0;
  padding: 12px 16px;
  background: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 4px;
  font-family: "Cascadia Code", "Fira Code", "JetBrains Mono", Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 460px;
  overflow-y: auto;
}
</style>
