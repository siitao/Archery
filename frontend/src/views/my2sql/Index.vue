<script setup lang="ts">
import { ref, reactive, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { format as sqlFormat } from "sql-formatter";
import { fetchQueryInstances, fetchQueryResources } from "@/api/sqlquery";
import { fetchBinlogList, runMy2sql, type BinlogFile, type My2SqlRow } from "@/api/binlog";
import { useBinlogHandoffStore } from "@/stores/binlogHandoff";

const router = useRouter();
const handoff = useBinlogHandoffStore();

// 实例（仅 MySQL）
const instanceOptions = ref<{ instance_name: string }[]>([]);
const binlogFiles = ref<BinlogFile[]>([]);
const dbOptions = ref<string[]>([]);
const tableOptions = ref<string[]>([]);
const loading = ref(false);
const result = ref<My2SqlRow[]>([]);

const form = reactive({
  instance_name: "",
  save_sql: false,
  rollback: false,
  extra_info: false,
  ignore_primary_key: false,
  full_columns: false,
  no_db_prefix: false,
  file_per_table: false,
  threads: 4,
  num: 30,
  start_file: "",
  start_pos: "" as number | string,
  end_file: "",
  end_pos: "" as number | string,
  start_time: "",
  stop_time: "",
  only_schemas: "",
  only_tables: [] as string[],
  sql_type: [] as string[],
});

async function loadInstances() {
  try {
    instanceOptions.value = await fetchQueryInstances({ db_type: ["mysql"] });
  } catch {
    // 拦截器已提示
  }
}

// 实例变更 → 拉库 + binlog
watch(
  () => form.instance_name,
  async () => {
    dbOptions.value = [];
    tableOptions.value = [];
    binlogFiles.value = [];
    form.only_schemas = "";
    form.only_tables = [];
    form.start_file = "";
    form.end_file = "";
    result.value = [];
    if (!form.instance_name) return;
    try {
      dbOptions.value = await fetchQueryResources({
        instance_name: form.instance_name,
        resource_type: "database",
      });
    } catch {
      // 拦截器已提示
    }
    try {
      binlogFiles.value = await fetchBinlogList(form.instance_name);
    } catch {
      // 拦截器已提示
    }
  }
);

// 库变更 → 拉表
watch(
  () => form.only_schemas,
  async () => {
    form.only_tables = [];
    tableOptions.value = [];
    result.value = [];
    if (!form.only_schemas) return;
    try {
      tableOptions.value = await fetchQueryResources({
        instance_name: form.instance_name,
        resource_type: "table",
        db_name: form.only_schemas,
      });
    } catch {
      // 拦截器已提示
    }
  }
);

function binlogLabel(f: BinlogFile): string {
  return `${f.Log_name}   Size:${f.File_size}`;
}

function binlogSize(f: BinlogFile): string {
  return String(f.File_size);
}

function formatSql(sql: string): string {
  try {
    return sqlFormat(sql, { language: "mysql" });
  } catch {
    return sql;
  }
}

async function onRun() {
  if (!form.instance_name) return ElMessage.warning("请选择实例");
  if (!form.start_file) return ElMessage.warning("请选择起始解析文件");
  // 默认 end_file = start_file
  if (!form.end_file) form.end_file = form.start_file;
  // 默认 end_pos = 当前 end_file 的 Size
  if (!form.end_pos) {
    const ef = binlogFiles.value.find((f) => f.Log_name === form.end_file);
    if (ef) form.end_pos = binlogSize(ef);
  }
  loading.value = true;
  result.value = [];
  try {
    result.value = await runMy2sql({
      instance_name: form.instance_name,
      save_sql: form.save_sql,
      rollback: form.rollback,
      extra_info: form.extra_info,
      ignore_primary_key: form.ignore_primary_key,
      full_columns: form.full_columns,
      no_db_prefix: form.no_db_prefix,
      file_per_table: form.file_per_table,
      threads: form.threads,
      num: form.num,
      start_file: form.start_file,
      start_pos: form.start_pos,
      end_file: form.end_file,
      end_pos: form.end_pos,
      stop_time: form.stop_time,
      start_time: form.start_time,
      only_schemas: form.only_schemas,
      only_tables: form.only_tables,
      sql_type: form.sql_type,
    });
    if (result.value.length === 0) ElMessage.info("无解析结果");
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

function onSubmitWorkflow() {
  if (result.value.length === 0) return;
  if (result.value.length > 2000) {
    return ElMessage.warning("SQL 语句超过 2000 行，不支持提交工单，请使用异步导出文件方式");
  }
  const sqlContent = result.value.map((r) => r.sql).filter(Boolean).join("\n");
  const wfName = `My2SQL回滚-${form.instance_name}-${form.only_schemas}`.slice(0, 49);
  handoff.set({
    workflow_name: wfName,
    sql_content: sqlContent,
    instance_name: form.instance_name,
    db_name: form.only_schemas,
  });
  router.push({ name: "sqlworkflow-submit" });
}

loadInstances();
</script>

<template>
  <div class="my2sql-page">
    <el-row :gutter="16">
      <!-- 左：选项 -->
      <el-col :span="7">
        <el-card shadow="never" v-loading="loading">
          <template #header>操作选项</template>
          <el-form :model="form" label-width="0" label-position="top">
            <el-form-item label="选择实例" required>
              <el-select v-model="form.instance_name" filterable placeholder="请选择实例" style="width: 100%">
                <el-option
                  v-for="i in instanceOptions"
                  :key="i.instance_name"
                  :label="i.instance_name"
                  :value="i.instance_name"
                />
              </el-select>
            </el-form-item>

            <el-form-item>
              <el-checkbox v-model="form.save_sql">保存到文件（异步）</el-checkbox>
            </el-form-item>

            <div class="section-title">解析模式</div>
            <el-checkbox v-model="form.rollback">-work-type rollback</el-checkbox>
            <el-checkbox v-model="form.ignore_primary_key">-ignore-primaryKey-forInsert</el-checkbox>
            <el-checkbox v-model="form.full_columns">-full-columns</el-checkbox>
            <el-checkbox v-model="form.no_db_prefix">-do-not-add-prifixDb</el-checkbox>
            <el-checkbox v-model="form.file_per_table">-file-per-table</el-checkbox>
            <el-checkbox v-model="form.extra_info">-add-extraInfo</el-checkbox>

            <div class="section-title">解析线程数</div>
            <el-input-number v-model="form.threads" :min="1" controls-position="right" style="width: 100%" />

            <div class="section-title">解析范围控制</div>
            <el-input-number v-model="form.num" :min="1" controls-position="right" placeholder="解析行数，默认 30" style="width: 100%" />
            <el-select v-model="form.start_file" filterable placeholder="起始解析文件" style="width: 100%">
              <el-option v-for="f in binlogFiles" :key="f.Log_name" :label="binlogLabel(f)" :value="f.Log_name" />
            </el-select>
            <el-input v-model="form.start_pos" placeholder="起始解析位置（可选）" />
            <el-select v-model="form.end_file" filterable clearable placeholder="终止解析文件（可选）" style="width: 100%">
              <el-option v-for="f in binlogFiles" :key="f.Log_name" :label="binlogLabel(f)" :value="f.Log_name" />
            </el-select>
            <el-input v-model="form.end_pos" placeholder="终止解析位置（可选）" />
            <el-date-picker v-model="form.start_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" placeholder="起始解析时间（不建议）" style="width: 100%" />
            <el-date-picker v-model="form.stop_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" placeholder="终止解析时间（可选）" style="width: 100%" />

            <div class="section-title">对象过滤</div>
            <el-select v-model="form.only_schemas" filterable clearable placeholder="数据库过滤（可选）" style="width: 100%">
              <el-option v-for="d in dbOptions" :key="d" :label="d" :value="d" />
            </el-select>
            <el-select v-model="form.only_tables" multiple filterable placeholder="表过滤（可选）" style="width: 100%">
              <el-option v-for="t in tableOptions" :key="t" :label="t" :value="t" />
            </el-select>
            <el-select v-model="form.sql_type" multiple placeholder="类型过滤（可选）" style="width: 100%">
              <el-option label="INSERT" value="insert" />
              <el-option label="UPDATE" value="update" />
              <el-option label="DELETE" value="delete" />
            </el-select>

            <div class="btn-row">
              <el-button type="danger" :loading="loading" @click="onRun">获取 SQL</el-button>
              <el-button
                type="success"
                :disabled="result.length === 0"
                @click="onSubmitWorkflow"
              >
                提交工单
              </el-button>
            </div>
          </el-form>
        </el-card>
      </el-col>

      <!-- 右：结果 -->
      <el-col :span="17">
        <el-card shadow="never">
          <template #header>SQL 语句（{{ result.length }}）</template>
          <div class="tip">
            前端展示数量由解析范围参数控制；若勾选「保存到文件」，会异步获取完整 SQL 文件保存到 downloads 目录，开启消息通知后执行结束会通知操作人。
          </div>
          <el-table
            :data="result"
            stripe
            border
            max-height="640"
            :default-sort="{ prop: '', order: 'ascending' }"
          >
            <el-table-column type="expand">
              <template #default="{ row }">
                <pre class="sql-full">{{ formatSql((row as My2SqlRow).sql) }}</pre>
                <pre v-if="(row as My2SqlRow).extra_info" class="extra-full">{{ (row as My2SqlRow).extra_info }}</pre>
              </template>
            </el-table-column>
            <el-table-column label="SQL" min-width="400" show-overflow-tooltip>
              <template #default="{ row }">
                {{ (row as My2SqlRow).sql }}
              </template>
            </el-table-column>
            <el-table-column label="ExtraInfo" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">
                {{ (row as My2SqlRow).extra_info || "" }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.my2sql-page {
  .section-title {
    margin: 12px 0 6px;
    font-weight: 600;
    font-size: 13px;
    color: var(--el-text-color-primary);
  }

  .el-select,
  .el-input,
  .el-input-number,
  .el-date-editor {
    margin-bottom: 8px;
  }

  .btn-row {
    margin-top: 16px;
    display: flex;
    gap: 8px;
  }

  .tip {
    margin-bottom: 12px;
    color: var(--el-color-danger);
    font-size: 12px;
    line-height: 1.6;
  }

  .sql-full,
  .extra-full {
    margin: 0;
    padding: 8px 12px;
    background: var(--el-fill-color-light);
    border-radius: 4px;
    font-family: var(--el-font-family-mono, monospace);
    font-size: 13px;
    white-space: pre-wrap;
    word-break: break-all;
  }

  .extra-full {
    margin-top: 8px;
    color: var(--el-text-color-secondary);
  }
}
</style>
