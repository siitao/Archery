<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { ElMessage } from "element-plus";
import type { EChartsOption } from "echarts";
import { useInstanceSelect } from "@/composables/useInstanceSelect";
import { fetchQueryResources } from "@/api/sqlquery";
import { fetchSlowReview, fetchSlowHistory, fetchSlowTrend } from "@/api/phase2";
import EChart from "@/components/EChart.vue";
import TruncateCell from "@/components/TruncateCell.vue";

const { instanceName, instanceGroups, currentInstance, loadInstances } =
  useInstanceSelect();

const dbName = ref("");
const dbOptions = ref<string[]>([]);
const dateRange = ref<[string, string] | null>(null);
const activeTab = ref("review");

const reviewRows = ref<Record<string, unknown>[]>([]);
const reviewCols = ref<string[]>([]);
const historyRows = ref<Record<string, unknown>[]>([]);
const historyCols = ref<string[]>([]);
const loading = ref(false);

/** SQL 长文本列名集合（大小写不敏感） */
const SQL_COLUMNS = new Set(["sqltext", "sql_text", "sql", "info", "fingerprint"]);

function isSqlColumn(col: string): boolean {
  return SQL_COLUMNS.has(col.toLowerCase());
}

/** 慢查统计/明细字段名 → 中文表头（后端返回驼峰英文字段，映射缺失时回退原字段名） */
const COLUMN_LABELS: Record<string, string> = {
  SQLText: "SQL 文本",
  SQLId: "SQL ID",
  DBName: "数据库",
  CreateTime: "最近出现时间",
  ExecutionStartTime: "执行开始时间",
  TotalExecutionCounts: "执行次数",
  TotalExecutionTimes: "总执行耗时",
  MySQLTotalExecutionCounts: "执行次数",
  MySQLTotalExecutionTimes: "总执行耗时",
  QueryTimeAvg: "平均耗时",
  QueryTimePct95: "95% 耗时",
  QueryTimes: "执行耗时",
  DurationPct95: "95% 耗时",
  ParseTotalRowCounts: "总扫描行数",
  ReturnTotalRowCounts: "总返回行数",
  ParseRowAvg: "平均扫描行数",
  ReturnRowAvg: "平均返回行数",
  ParseRowCounts: "扫描行数",
  ReturnRowCounts: "返回行数",
  HostName: "主机",
  HostAddress: "客户端地址",
  LockTimes: "锁等待时间",
};

function colLabel(col: string): string {
  return COLUMN_LABELS[col] || col;
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

function dateStr(i: 0 | 1) {
  return dateRange.value?.[i] || undefined;
}

async function loadReview() {
  if (!instanceName.value) return;
  loading.value = true;
  reviewRows.value = [];
  try {
    const r = await fetchSlowReview({
      instance_name: instanceName.value,
      db_name: dbName.value,
      StartTime: dateStr(0),
      EndTime: dateStr(1),
      limit: 1000,
    });
    reviewRows.value = r.rows;
    if (r.rows.length) reviewCols.value = Object.keys(r.rows[0]);
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

async function loadHistory() {
  if (!instanceName.value) return;
  loading.value = true;
  historyRows.value = [];
  try {
    const r = await fetchSlowHistory({
      instance_name: instanceName.value,
      db_name: dbName.value,
      StartTime: dateStr(0),
      EndTime: dateStr(1),
      limit: 1000,
    });
    historyRows.value = r.rows;
    if (r.rows.length) historyCols.value = Object.keys(r.rows[0]);
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

function onQuery() {
  if (activeTab.value === "review") loadReview();
  else loadHistory();
}

watch(instanceName, () => {
  dbName.value = "";
  if (currentInstance.value) loadDbs();
});

function onTabChange(name: string | number) {
  if (String(name) === "review") loadReview();
  else loadHistory();
}

// 趋势弹窗
const trendVisible = ref(false);
const trendLoading = ref(false);
// 用宽松对象类型，避免 echarts v6 在 ref<EChartsOption> 赋值时触发的 graphic 联合类型深检问题
const trendOption = ref<Record<string, unknown>>({});
const trendTitle = ref("");

async function openTrend(row: Record<string, unknown>) {
  const checksum = String(row.SQLId || row.checksum || "");
  if (!checksum) return ElMessage.warning("该行无 SQLId，无法查看趋势");
  trendTitle.value = String(row.fingerprint || row.SQLText || checksum).slice(0, 80);
  trendVisible.value = true;
  trendLoading.value = true;
  trendOption.value = {};
  try {
    const r = await fetchSlowTrend(checksum, instanceName.value);
    const s0 = r.series[0] || { name: "慢查次数", data: [] };
    const s1 = r.series[1] || { name: "慢查时长(95%)", data: [] };
    trendOption.value = {
      title: { text: "SQL 历史趋势", left: "center", textStyle: { fontSize: 14 } },
      tooltip: { trigger: "axis" },
      legend: { top: 24 },
      grid: { left: 56, right: 24, top: 56, bottom: 48, containLabel: true },
      xAxis: {
        type: "category",
        data: r.x,
        boundaryGap: false,
        axisLabel: { interval: 0, rotate: r.x.length > 12 ? 45 : 0 },
      },
      yAxis: [
        { type: "value", name: "慢查次数" },
        { type: "value", name: "慢查时长(95%)" },
      ],
      series: [
        {
          name: s0.name || "慢查次数",
          type: "line",
          smooth: true,
          areaStyle: { opacity: 0.3 },
          data: s0.data,
        },
        {
          name: s1.name || "慢查时长(95%)",
          type: "line",
          smooth: true,
          yAxisIndex: 1,
          showSymbol: false,
          areaStyle: { opacity: 0.3 },
          data: s1.data,
        },
      ],
    } as EChartsOption;
  } catch {
    // 拦截器已提示
  } finally {
    trendLoading.value = false;
  }
}

onMounted(loadInstances);
</script>

<template>
  <div class="slow-page">
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
          <el-select v-model="dbName" filterable placeholder="全部" clearable style="width: 180px">
            <el-option v-for="d in dbOptions" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="-"
            start-placeholder="开始"
            end-placeholder="结束"
            style="width: 240px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onQuery">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <el-tab-pane label="慢查统计" name="review">
          <el-table v-loading="loading" :data="reviewRows" stripe border max-height="560">
            <el-table-column
              v-for="col in reviewCols"
              :key="col"
              :prop="col"
              :label="colLabel(col)"
              min-width="140"
              :show-overflow-tooltip="!isSqlColumn(col)"
            >
              <template v-if="isSqlColumn(col)" #default="{ row }">
                <TruncateCell :value="(row as Record<string,unknown>)[col]" :row="row as Record<string,unknown>" :col="col" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="90" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openTrend(row as Record<string, unknown>)">
                  趋势
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="慢查明细" name="history">
          <el-table v-loading="loading" :data="historyRows" stripe border max-height="560">
            <el-table-column
              v-for="col in historyCols"
              :key="col"
              :prop="col"
              :label="colLabel(col)"
              min-width="140"
              :show-overflow-tooltip="!isSqlColumn(col)"
            >
              <template v-if="isSqlColumn(col)" #default="{ row }">
                <TruncateCell :value="(row as Record<string,unknown>)[col]" :row="row as Record<string,unknown>" :col="col" />
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 趋势弹窗 -->
    <el-dialog v-model="trendVisible" title="慢查历史趋势" width="900px">
      <div class="trend-title" :title="trendTitle">{{ trendTitle }}</div>
      <EChart v-loading="trendLoading" :option="trendOption" height="420px" />
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.slow-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}

.trend-title {
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
