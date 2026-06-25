<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { useInstanceSelect } from "@/composables/useInstanceSelect";
import { fetchQueryResources } from "@/api/sqlquery";
import { fetchSlowReview, fetchSlowHistory } from "@/api/phase2";

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
  return dateRange.value?.[i] || "";
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
              :label="col"
              min-width="140"
              show-overflow-tooltip
            />
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="慢查明细" name="history">
          <el-table v-loading="loading" :data="historyRows" stripe border max-height="560">
            <el-table-column
              v-for="col in historyCols"
              :key="col"
              :prop="col"
              :label="col"
              min-width="140"
              show-overflow-tooltip
            />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
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
</style>
