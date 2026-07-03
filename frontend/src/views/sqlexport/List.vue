<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { useRouter } from "vue-router";
import { Search, Refresh, Document } from "@element-plus/icons-vue";
import { useAuthStore } from "@/stores/auth";
import { fetchUserInstances, type GroupInstanceRow } from "@/api/group";
import {
  fetchWorkflowLogs,
  WORKFLOW_STATUS,
  type SqlWorkflowRow,
  type WorkflowLogRow,
} from "@/api/sqlworkflow";
import { fetchExportWorkflows, EXPORT_FORMAT_LABEL } from "@/api/sqlexport";

const auth = useAuthStore();
const router = useRouter();

const loading = ref(false);
const list = ref<SqlWorkflowRow[]>([]);
const total = ref(0);

const query = reactive({
  workflow_name: "",
  status: "",
  instance_id: undefined as number | undefined,
  date_range: null as [string, string] | null,
  page: 1,
  size: 20,
});

const instanceOptions = ref<GroupInstanceRow[]>([]);
const instanceMap = ref<Record<number, string>>({});

// 操作日志弹窗
const logVisible = ref(false);
const logLoading = ref(false);
const logList = ref<WorkflowLogRow[]>([]);
const logWorkflowName = ref("");

async function loadInstances() {
  try {
    // 走用户级接口（按资源组授权过滤），避免普通用户触发 403
    const rows = await fetchUserInstances();
    instanceOptions.value = rows || [];
    instanceMap.value = Object.fromEntries(
      instanceOptions.value.map((i) => [i.id, i.instance_name])
    );
  } catch {
    // 拦截器已提示
  }
}

async function loadData() {
  loading.value = true;
  try {
    const { data } = await fetchExportWorkflows({
      page: query.page,
      size: query.size,
      "workflow__workflow_name__icontains": query.workflow_name || undefined,
      "workflow__status": query.status || undefined,
      "workflow__instance_id": query.instance_id,
      "workflow__create_time__gte": query.date_range?.[0] || undefined,
      "workflow__create_time__lt": query.date_range?.[1] || undefined,
    });
    list.value = data.results || [];
    total.value = data.count || 0;
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

function onSearch() {
  query.page = 1;
  loadData();
}

function onReset() {
  query.workflow_name = "";
  query.status = "";
  query.instance_id = undefined;
  query.date_range = null;
  query.page = 1;
  loadData();
}

function onPageChange(p: number) {
  query.page = p;
  loadData();
}

function onSizeChange(s: number) {
  query.size = s;
  query.page = 1;
  loadData();
}

function goDetail(row: SqlWorkflowRow) {
  router.push({ name: "sqlworkflow-detail", params: { id: row.workflow_id } });
}

function exportFormat(row: SqlWorkflowRow): string {
  const fmt = row.workflow.export_format as string | undefined;
  return EXPORT_FORMAT_LABEL[fmt || ""] || fmt || "";
}

async function openLogs(row: SqlWorkflowRow) {
  logWorkflowName.value = row.workflow.workflow_name;
  logVisible.value = true;
  logLoading.value = true;
  logList.value = [];
  try {
    const { data } = await fetchWorkflowLogs(row.workflow_id);
    logList.value = data.results || [];
  } catch {
    // 拦截器已提示
  } finally {
    logLoading.value = false;
  }
}

function submitExport() {
  router.push({ name: "sqlexport-submit" });
}

onMounted(() => {
  loadInstances();
  loadData();
});
</script>

<template>
  <div class="sqlexport-page">
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="query" @submit.prevent>
        <el-form-item label="工单名称">
          <el-input
            v-model="query.workflow_name"
            placeholder="支持模糊匹配"
            clearable
            @keyup.enter="onSearch"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="query.status"
            placeholder="全部"
            clearable
            style="width: 160px"
          >
            <el-option
              v-for="(v, k) in WORKFLOW_STATUS"
              :key="k"
              :label="v.label"
              :value="k"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="实例">
          <el-select
            v-model="query.instance_id"
            placeholder="全部"
            clearable
            filterable
            style="width: 200px"
          >
            <el-option
              v-for="i in instanceOptions"
              :key="i.id"
              :label="i.instance_name"
              :value="i.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="发起时间">
          <el-date-picker
            v-model="query.date_range"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="-"
            start-placeholder="开始"
            end-placeholder="结束"
            style="width: 240px"
          />
        </el-form-item>
        <el-form-item class="filter-actions">
          <el-button type="primary" :icon="Search" @click="onSearch">查询</el-button>
          <el-button :icon="Refresh" @click="onReset">重置</el-button>
          <el-button
            v-if="auth.hasPerm('sql.sqlexport_submit')"
            type="success"
            :icon="Document"
            @click="submitExport"
          >
            提交导出工单
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="list" stripe border style="width: 100%">
        <el-table-column type="index" label="#" width="55" />
        <el-table-column label="工单名称" min-width="180">
          <template #default="{ row }">
            <el-link type="primary" @click="goDetail(row as SqlWorkflowRow)">
              {{ (row as SqlWorkflowRow).workflow.workflow_name }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            数据导出: {{ exportFormat(row as SqlWorkflowRow) }}
          </template>
        </el-table-column>
        <el-table-column
          label="发起人"
          prop="workflow.engineer_display"
          width="110"
          show-overflow-tooltip
        />
        <el-table-column label="状态" width="130">
          <template #default="{ row }">
            <el-tag
              v-if="WORKFLOW_STATUS[(row as SqlWorkflowRow).workflow.status as string]"
              :type="WORKFLOW_STATUS[(row as SqlWorkflowRow).workflow.status as string].type"
              size="small"
            >
              {{ WORKFLOW_STATUS[(row as SqlWorkflowRow).workflow.status as string].label }}
            </el-tag>
            <span v-else>{{ (row as SqlWorkflowRow).workflow.status }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="发起时间"
          prop="workflow.create_time"
          width="160"
        />
        <el-table-column label="实例" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            {{ instanceMap[(row as SqlWorkflowRow).workflow.instance as number] || (row as SqlWorkflowRow).workflow.instance }}
          </template>
        </el-table-column>
        <el-table-column
          label="数据库"
          prop="workflow.db_name"
          width="120"
          show-overflow-tooltip
        />
        <el-table-column
          label="组"
          prop="workflow.group_name"
          width="110"
          show-overflow-tooltip
        />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openLogs(row as SqlWorkflowRow)">操作日志</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          :current-page="query.page"
          :page-size="query.size"
          :page-sizes="[20, 30, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </el-card>

    <!-- 操作日志弹窗 -->
    <el-dialog
      v-model="logVisible"
      :title="`操作日志 - ${logWorkflowName}`"
      width="720px"
    >
      <el-table v-loading="logLoading" :data="logList" stripe border max-height="420">
        <el-table-column label="操作" prop="operation_type_desc" width="120" />
        <el-table-column label="操作人" prop="operator_display" width="120" />
        <el-table-column label="操作时间" prop="operation_time" width="160" />
        <el-table-column
          label="操作信息"
          prop="operation_info"
          show-overflow-tooltip
        />
      </el-table>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.sqlexport-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-card :deep(.el-form-item) {
  margin-bottom: 8px;
}

/* 操作按钮组作为整体，inline 流式排版时整组一起换行而不被拆散 */
.filter-actions {
  :deep(.el-form-item__content) {
    flex-wrap: nowrap;
  }
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
