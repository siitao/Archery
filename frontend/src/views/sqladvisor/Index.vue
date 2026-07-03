<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { marked } from "marked";
import DOMPurify from "dompurify";
import { useInstanceSelect } from "@/composables/useInstanceSelect";
import { fetchQueryResources } from "@/api/sqlquery";
import SqlEditor from "@/components/SqlEditor.vue";
import {
  optimizeSqlAdvisor,
  optimizeSoar,
  optimizeSqlTuning,
  explainSql,
  optimizeSqlByAI,
} from "@/api/phase2";
import TruncateCell from "@/components/TruncateCell.vue";

// gfm 表格渲染
marked.setOptions({ gfm: true, breaks: false });

const { instanceName, instanceGroups, currentInstance, loadInstances } =
  useInstanceSelect();

const dbName = ref("");
const dbOptions = ref<string[]>([]);
const sqlText = ref("");
type OptTool = "advisor" | "soar" | "tuning" | "explain" | "ai";
const tool = ref<OptTool>("advisor");
const loading = ref(false);

const resultText = ref(""); // advisor/soar 文本或 markdown
const explainCols = ref<string[]>([]);
const explainRows = ref<unknown[][]>([]);

// tuning 维度复选框，对应后端 option
const tuningOptions = ref<string[]>(["sys_parm", "sql_plan", "obj_stat", "sql_profile"]);
const tuningOptionItems: { value: string; label: string }[] = [
  { value: "sys_parm", label: "系统参数" },
  { value: "sql_plan", label: "SQL 计划" },
  { value: "obj_stat", label: "对象统计" },
  { value: "sql_profile", label: "会话状态" },
];
// tuning 结构化结果
type TableData = { column_list: string[]; rows: unknown[][] };
type TuningResult = Record<string, unknown>;
const tuningData = ref<TuningResult>({});

const tools: { key: OptTool; label: string }[] = [
  { key: "advisor", label: "SQLAdvisor" },
  { key: "soar", label: "SOAR" },
  { key: "tuning", label: "MySQL 调优" },
  { key: "explain", label: "执行计划" },
  { key: "ai", label: "AI 优化" },
];

/** tuning 各 section 的中文标题映射 */
const TUNING_SECTION_TITLE: Record<string, string> = {
  basic_information: "基本信息",
  sys_parameter: "系统参数",
  optimizer_switch: "优化器开关",
  optimizer_rewrite_sql: "优化器改写",
  plan: "执行计划",
  object_statistics: "对象统计",
  session_status: "会话状态",
  sqltext: "SQL 语句",
  structure: "表结构",
  table_info: "表信息",
  index_info: "索引信息",
  EXECUTE_TIME: "执行耗时",
  BEFORE_STATUS: "执行前状态",
  AFTER_STATUS: "执行后状态",
  "SESSION_STATUS(DIFFERENT)": "状态差异",
  PROFILING_DETAIL: "Profile 明细",
  PROFILING_SUMMARY: "Profile 汇总",
};

/** SQL 长文本列名集合 */
const SQL_COLUMNS = new Set(["sql", "query", "info", "detail", "plan", "suggestion"]);

/** 判断是否为 {column_list, rows} 表格数据 */
function isTableData(v: unknown): v is TableData {
  return (
    !!v &&
    typeof v === "object" &&
    Array.isArray((v as TableData).column_list) &&
    Array.isArray((v as TableData).rows)
  );
}

/** 把 {column_list, rows} 的行数组 zip 成对象数组，便于 el-table 渲染 */
function zipRows(table: TableData): Record<string, unknown>[] {
  return table.rows.map((row) => {
    const o: Record<string, unknown> = {};
    table.column_list.forEach((_col, idx) => {
      o[String(idx)] = (row as unknown[])[idx];
    });
    return o;
  });
}

function sectionTitle(key: string): string {
  return TUNING_SECTION_TITLE[key] || key;
}

/** resultText（markdown，soar / ai）→ 安全 HTML */
const resultHtml = computed(() => {
  if (!resultText.value) return "";
  const raw = marked.parse(resultText.value, { async: false }) as string;
  return DOMPurify.sanitize(raw);
});

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
  tuningData.value = {};
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
      tuningData.value = await optimizeSqlTuning({
        instance_name: instanceName.value,
        db_name: dbName.value,
        sql_content: sqlText.value,
        option: tuningOptions.value,
      });
    } else if (tool.value === "ai") {
      resultText.value = await optimizeSqlByAI({
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
        <el-form-item v-if="tool === 'tuning'" label="维度">
          <el-checkbox-group v-model="tuningOptions">
            <el-checkbox v-for="o in tuningOptionItems" :key="o.value" :value="o.value">{{ o.label }}</el-checkbox>
          </el-checkbox-group>
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
      <pre v-if="tool !== 'soar' && tool !== 'ai'" class="result-text">{{ resultText }}</pre>
      <div v-else class="markdown" v-html="resultHtml" />
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

    <!-- MySQL 调优：结构化分区展示 -->
    <template v-if="tool === 'tuning' && Object.keys(tuningData).length">
      <!-- 一级 section：表格 / 列表 / 字符串 -->
      <el-card
        v-for="(value, key) in tuningData"
        :key="key"
        shadow="never"
        class="tuning-card"
      >
        <template #header>{{ sectionTitle(String(key)) }}</template>
        <!-- 1) 单表格 -->
        <el-table
          v-if="isTableData(value)"
          :data="zipRows(value)"
          stripe
          border
          max-height="420"
        >
          <el-table-column
            v-for="(col, idx) in value.column_list"
            :key="col"
            :prop="String(idx)"
            :label="col"
            min-width="140"
            :show-overflow-tooltip="!isSqlColumn(col)"
          >
            <template v-if="isSqlColumn(col)" #default="{ row }">
              <TruncateCell :value="String(row[String(idx)])" :row="row" :col="col" />
            </template>
            <template v-else #default="{ row }">{{ row[String(idx)] }}</template>
          </el-table-column>
        </el-table>
        <!-- 2) 字符串（sqltext / EXECUTE_TIME） -->
        <pre v-else-if="typeof value === 'string'" class="result-text">{{ value }}</pre>
        <!-- 3) 对象统计：表数组，每张表含 structure/table_info/index_info -->
        <div v-else-if="Array.isArray(value)" class="obj-stat">
          <div v-for="(tbl, ti) in value" :key="ti" class="obj-stat-table">
            <div class="obj-stat-title">表 #{{ ti + 1 }}</div>
            <el-card
              v-for="(subVal, subKey) in tbl as Record<string, unknown>"
              :key="subKey"
              shadow="never"
              class="tuning-sub-card"
            >
              <template #header>{{ sectionTitle(String(subKey)) }}</template>
              <el-table
                v-if="isTableData(subVal)"
                :data="zipRows(subVal)"
                stripe
                border
                max-height="360"
              >
                <el-table-column
                  v-for="(col, idx) in subVal.column_list"
                  :key="col"
                  :prop="String(idx)"
                  :label="col"
                  min-width="140"
                  :show-overflow-tooltip="!isSqlColumn(col)"
                >
                  <template v-if="isSqlColumn(col)" #default="{ row }">
                    <TruncateCell :value="String(row[String(idx)])" :row="row" :col="col" />
                  </template>
                  <template v-else #default="{ row }">{{ row[String(idx)] }}</template>
                </el-table-column>
              </el-table>
              <pre v-else-if="typeof subVal === 'string'" class="result-text">{{ subVal }}</pre>
            </el-card>
          </div>
        </div>
        <!-- 4) 会话状态：嵌套字典（EXECUTE_TIME 字符串 + 多个表格） -->
        <div v-else-if="value && typeof value === 'object'" class="session-status">
          <pre v-if="'EXECUTE_TIME' in (value as Record<string, unknown>)" class="result-text">执行耗时：{{ (value as Record<string, unknown>).EXECUTE_TIME }} s</pre>
          <el-card
            v-for="(subVal, subKey) in value as Record<string, unknown>"
            :key="subKey"
            shadow="never"
            class="tuning-sub-card"
          >
            <template #header>{{ sectionTitle(String(subKey)) }}</template>
            <el-table
              v-if="isTableData(subVal)"
              :data="zipRows(subVal)"
              stripe
              border
              max-height="360"
            >
              <el-table-column
                v-for="(col, idx) in subVal.column_list"
                :key="col"
                :prop="String(idx)"
                :label="col"
                min-width="140"
                :show-overflow-tooltip="!isSqlColumn(col)"
              >
                <template v-if="isSqlColumn(col)" #default="{ row }">
                  <TruncateCell :value="String(row[String(idx)])" :row="row" :col="col" />
                </template>
                <template v-else #default="{ row }">{{ row[String(idx)] }}</template>
              </el-table-column>
            </el-table>
          </el-card>
        </div>
      </el-card>
    </template>
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

.tuning-card {
  margin-bottom: 0;
}

.obj-stat {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.obj-stat-title {
  font-weight: 600;
  margin-bottom: 8px;
}

.tuning-sub-card {
  margin-bottom: 8px;
  :deep(.el-card__header) {
    padding: 8px 12px;
    font-size: 13px;
  }
}
</style>
