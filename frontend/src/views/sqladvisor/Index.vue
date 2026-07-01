<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { useInstanceSelect } from "@/composables/useInstanceSelect";
import { fetchQueryResources } from "@/api/sqlquery";
import SqlEditor from "@/components/SqlEditor.vue";
import {
  optimizeSqlAdvisor,
  optimizeSoar,
  optimizeSqlTuning,
  explainSql,
} from "@/api/phase2";
import TruncateCell from "@/components/TruncateCell.vue";

const { instanceName, instanceGroups, currentInstance, loadInstances } =
  useInstanceSelect();

const dbName = ref("");
const dbOptions = ref<string[]>([]);
const sqlText = ref("");
type OptTool = "advisor" | "soar" | "tuning" | "explain";
const tool = ref<OptTool>("advisor");
const loading = ref(false);

const resultText = ref(""); // advisor/soar/tuning 文本或 markdown
const explainCols = ref<string[]>([]);
const explainRows = ref<unknown[][]>([]);

const tools: { key: OptTool; label: string }[] = [
  { key: "advisor", label: "SQLAdvisor" },
  { key: "soar", label: "SOAR" },
  { key: "tuning", label: "MySQL 调优" },
  { key: "explain", label: "执行计划" },
];

/** SQL 长文本列名集合 */
const SQL_COLUMNS = new Set(["sql", "query", "info", "detail", "plan", "suggestion"]);

function isSqlColumn(col: string): boolean {
  return SQL_COLUMNS.has(col.toLowerCase());
}

async function loadDbs() {
  if (!currentInstance.value) return;
  try {
    dbOptions.value = await fetchQueryResources({
      instance_id: currentInstance.value.id,
      resource_type: "database",
    });
  } catch {
    // 拦截器已提示
  }
}

watch(instanceName, () => {
  dbName.value = "";
  if (currentInstance.value) loadDbs();
});

async function onRun() {
  if (!instanceName.value || !dbName.value)
    return ElMessage.warning("请选择实例和库");
  if (!sqlText.value.trim()) return ElMessage.warning("请输入 SQL");
  loading.value = true;
  resultText.value = "";
  explainCols.value = [];
  explainRows.value = [];
  try {
    if (tool.value === "advisor") {
      resultText.value = await optimizeSqlAdvisor({
        instance_name: instanceName.value,
        db_name: dbName.value,
        sql_content: sqlText.value,
      });
    } else if (tool.value === "soar") {
      resultText.value = await optimizeSoar({
        instance_name: instanceName.value,
        db_name: dbName.value,
        sql: sqlText.value,
      });
    } else if (tool.value === "tuning") {
      resultText.value = await optimizeSqlTuning({
        instance_name: instanceName.value,
        db_name: dbName.value,
        sql_content: sqlText.value,
      });
    } else {
      const r = await explainSql({
        instance_name: instanceName.value,
        db_name: dbName.value,
        sql_content: sqlText.value,
      });
      explainCols.value = r.column_list || [];
      explainRows.value = r.rows || [];
    }
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

onMounted(loadInstances);
</script>

<template>
  <div v-loading="loading" class="advisor-page">
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="实例">
          <el-select v-model="instanceName" filterable placeholder="选择实例" style="width: 220px">
            <el-option-group v-for="g in instanceGroups" :key="g.label" :label="g.label">
              <el-option v-for="i in g.items" :key="i.id" :label="i.instance_name" :value="i.instance_name" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="库">
          <el-select v-model="dbName" filterable placeholder="选择库" style="width: 200px">
            <el-option v-for="d in dbOptions" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="工具">
          <el-select v-model="tool" style="width: 150px">
            <el-option v-for="t in tools" :key="t.key" :label="t.label" :value="t.key" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <SqlEditor v-model="sqlText" />
      <div class="actions">
        <el-button type="primary" @click="onRun">执行</el-button>
      </div>
    </el-card>

    <el-card v-if="resultText" shadow="never">
      <template #header>建议</template>
      <pre v-if="tool !== 'soar'" class="result-text">{{ resultText }}</pre>
      <div v-else class="markdown" v-html="resultText" />
    </el-card>

    <el-card v-if="explainCols.length" shadow="never">
      <template #header>执行计划</template>
      <el-table :data="explainRows" stripe border max-height="420">
        <el-table-column
          v-for="(col, idx) in explainCols"
          :key="col"
          :prop="String(idx)"
          :label="col"
          min-width="140"
          :show-overflow-tooltip="!isSqlColumn(col)"
        >
          <template v-if="isSqlColumn(col)" #default="{ row }">
            <TruncateCell :value="String((row as unknown[])[idx])" :row="row as unknown as Record<string,unknown>" :col="col" />
          </template>
          <template v-else #default="{ row }">{{ (row as unknown[])[idx] }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.advisor-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}

.actions {
  margin-top: 12px;
}

.result-text {
  margin: 0;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  font-family: monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
}

.markdown {
  :deep(table) {
    border-collapse: collapse;
  }
  :deep(th),
  :deep(td) {
    border: 1px solid var(--el-border-color);
    padding: 4px 8px;
  }
}
</style>
