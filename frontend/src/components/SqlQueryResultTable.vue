<script setup lang="ts">
import { ref, computed } from "vue";
import * as XLSX from "xlsx";
import { legacyBase } from "@/utils/request";
import type { QueryResultEnvelope } from "@/api/sqlquery";
import TruncateCell from "@/components/TruncateCell.vue";

const props = defineProps<{
  /** 执行结果信封（status 三态），null=未执行 */
  envelope: QueryResultEnvelope | null;
  loading?: boolean;
}>();

const SQL_COLUMNS = new Set(["sql", "sqllog", "sql_text"]);

function isSqlColumn(col: string): boolean {
  return SQL_COLUMNS.has(col.toLowerCase());
}

const page = ref(1);
const pageSize = ref(50);

const result = computed(() =>
  props.envelope && props.envelope.status === 0 ? props.envelope.data : null
);
const errorInfo = computed(() =>
  props.envelope && props.envelope.status !== 0
    ? { status: props.envelope.status, msg: props.envelope.msg }
    : null
);

const columnList = computed(() => result.value?.column_list || []);

/** 把值数组的 rows zip 成对象数组，供 el-table 渲染 */
const objectRows = computed<Record<string, unknown>[]>(() => {
  const r = result.value;
  if (!r) return [];
  const cols = r.column_list || [];
  return (r.rows || []).map((row) => {
    const o: Record<string, unknown> = {};
    cols.forEach((c, i) => (o[c] = row[i]));
    return o;
  });
});

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return objectRows.value.slice(start, start + pageSize.value);
});

/** show create table 类结果（column_list 形如 ['table','create table']）：用 <pre> 展示 CREATE 文本，其余按结构化表格 */
const isShowCreate = computed(() => {
  const r = result.value;
  if (!r) return false;
  const cols = (r.column_list || []).map((c) => String(c).toLowerCase());
  return (
    cols.length === 2 && cols[0].includes("table") && cols[1].includes("create")
  );
});
const createText = computed(() => {
  if (!isShowCreate.value || !result.value) return "";
  return (result.value.rows || [])
    .map((r) => String(r[1] ?? ""))
    .join("\n\n");
});

const applyUrl = `${legacyBase}/queryapplylist/`;

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function csvCell(v: unknown): string {
  const s = formatCell(v);
  if (/[",\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
  return s;
}

function exportCsv() {
  const r = result.value;
  if (!r || !r.column_list?.length) return;
  const cols = r.column_list;
  const lines = [cols.join(",")];
  for (const row of objectRows.value) {
    lines.push(cols.map((c) => csvCell(row[c])).join(","));
  }
  // BOM 防止 Excel 中文乱码
  const blob = new Blob(["﻿" + lines.join("\n")], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `query_result_${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function exportXlsx() {
  const r = result.value;
  if (!r || !r.column_list?.length) return;
  // aoa：首行列名 + 数据行（rows 本身是值数组）
  const aoa: unknown[][] = [r.column_list, ...(r.rows || [])];
  const ws = XLSX.utils.aoa_to_sheet(aoa);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "result");
  XLSX.writeFile(wb, `query_result_${Date.now()}.xlsx`);
}
</script>

<template>
  <div v-loading="props.loading" class="result-wrap">
    <!-- 错误态 -->
    <el-alert
      v-if="errorInfo"
      :title="errorInfo.msg || '查询失败'"
      :type="errorInfo.status === 2 ? 'warning' : 'error'"
      :closable="false"
      show-icon
    >
      <template v-if="errorInfo.status === 2">
        <el-link type="primary" :href="applyUrl" target="_blank">
          去申请查询权限
        </el-link>
      </template>
    </el-alert>

    <!-- 结果 -->
    <template v-else-if="result">
      <div class="meta-row">
        <el-tag size="small" type="info">行数 {{ result.affected_rows }}</el-tag>
        <el-tag size="small" type="info">耗时 {{ result.query_time }}s</el-tag>
        <el-tag v-if="result.is_masked" size="small" type="warning">
          已脱敏
        </el-tag>
        <el-tag
          v-if="result.seconds_behind_master != null"
          size="small"
          type="info"
        >
          主从延迟 {{ result.seconds_behind_master }}s
        </el-tag>
        <span class="spacer" />
        <el-button size="small" :disabled="!objectRows.length" @click="exportCsv">
          导出 CSV
        </el-button>
        <el-button size="small" :disabled="!objectRows.length" @click="exportXlsx">
          导出 XLSX
        </el-button>
      </div>

      <pre v-if="isShowCreate" class="create-text">{{ createText }}</pre>
      <el-table
        v-else-if="columnList.length"
        :data="pagedRows"
        stripe
        border
        max-height="520"
        style="width: 100%"
      >
        <el-table-column
          v-for="col in columnList"
          :key="col"
          :prop="col"
          :label="col"
          min-width="140"
          :show-overflow-tooltip="!isSqlColumn(col)"
        >
          <template v-if="isSqlColumn(col)" #default="{ row }">
            <TruncateCell :value="row[col]" :row="row" :col="col" />
          </template>
          <template v-else #default="{ row }">{{ formatCell(row[col]) }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="结果为空" />

      <div v-if="objectRows.length > pageSize" class="pager">
        <el-pagination
          :total="objectRows.length"
          :current-page="page"
          :page-size="pageSize"
          :page-sizes="[50, 100, 500, 1000]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="(p: number) => (page = p)"
          @size-change="(s: number) => (pageSize = s)"
        />
      </div>
    </template>

    <!-- 未执行 -->
    <el-empty v-else description="执行查询后在此展示结果" />
  </div>
</template>

<style scoped lang="scss">
.result-wrap {
  min-height: 200px;
}

.create-text {
  margin: 0;
  padding: 12px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-light);
  border-radius: 4px;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 520px;
  overflow: auto;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;

  .spacer {
    flex: 1;
  }
}

.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
