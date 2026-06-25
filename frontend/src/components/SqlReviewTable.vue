<script setup lang="ts">
import { ref, computed } from "vue";
import type { ReviewRow } from "@/api/sqlworkflow";

const props = defineProps<{
  rows: ReviewRow[];
  /** review=提交检测阶段（无耗时/阶段列）；execute=执行结果阶段 */
  phase: "review" | "execute";
}>();

const page = ref(1);
const pageSize = ref(500);

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return props.rows.slice(start, start + pageSize.value);
});

/** 按 errlevel 行变色：2 错误红 / 1 警告黄 */
function rowClass({ row }: { row: ReviewRow }): string {
  const lvl = Number((row as ReviewRow).errlevel ?? 0);
  if (lvl === 2) return "row-error";
  if (lvl === 1) return "row-warning";
  return "";
}

function levelText(lvl: unknown): string {
  const n = Number(lvl ?? 0);
  return n === 0 ? "正常" : n === 1 ? "警告" : n === 2 ? "错误" : String(lvl);
}
</script>

<template>
  <el-table
    :data="pagedRows"
    stripe
    border
    :row-class-name="rowClass"
    style="width: 100%"
    max-height="520"
  >
    <el-table-column type="index" label="#" width="55" />
    <el-table-column label="SQL 内容" min-width="320" show-overflow-tooltip>
      <template #default="{ row }">{{ (row as ReviewRow).sql }}</template>
    </el-table-column>
    <el-table-column label="状态" width="90">
      <template #default="{ row }">{{ levelText((row as ReviewRow).errlevel) }}</template>
    </el-table-column>
    <el-table-column label="信息" min-width="240" show-overflow-tooltip>
      <template #default="{ row }">{{ (row as ReviewRow).errormessage }}</template>
    </el-table-column>
    <el-table-column label="影响行数" width="100">
      <template #default="{ row }">{{ (row as ReviewRow).affected_rows }}</template>
    </el-table-column>
    <template v-if="phase === 'execute'">
      <el-table-column label="执行耗时" width="100">
        <template #default="{ row }">{{ (row as ReviewRow).execute_time }}</template>
      </el-table-column>
      <el-table-column label="阶段" width="140" show-overflow-tooltip>
        <template #default="{ row }">{{ (row as ReviewRow).stagestatus }}</template>
      </el-table-column>
    </template>
  </el-table>

  <div v-if="rows.length > pageSize" class="pager">
    <el-pagination
      :total="rows.length"
      :current-page="page"
      :page-size="pageSize"
      :page-sizes="[500, 1000, 5000]"
      layout="total, sizes, prev, pager, next"
      background
      @current-change="(p: number) => (page = p)"
      @size-change="(s: number) => (pageSize = s)"
    />
  </div>
</template>

<style scoped lang="scss">
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

:deep(.row-error) {
  background: #fef0f0 !important;
}

:deep(.row-warning) {
  background: #fdf6ec !important;
}
</style>
