<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { useRouter } from "vue-router";
import { Search, Refresh, Document } from "@element-plus/icons-vue";
import { useAuthStore } from "@/stores/auth";
import { fetchUserInstances, type GroupInstanceRow } from "@/api/group";
import {
  fetchSqlWorkflows,
  fetchWorkflowLogs,
  WORKFLOW_STATUS,
  SYNTAX_TYPE,
  type SqlWorkflowRow,
  type WorkflowLogRow,
} from "@/api/sqlworkflow";

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

// 实例选项 + id→name 映射（下拉与表格「实例」列共用，因后端 instance 只返回 id）
// 走用户级接口（按资源组授权过滤），普通用户可见自己组内的实例
const instanceOptions = ref<GroupInstanceRow[]>([]);
const instanceMap = ref<Record<number, string>>({});

// 操作日志弹窗
const logVisible = ref(false);
const logLoading = ref(false);
const logList = ref<WorkflowLogRow[]>([]);
const logWorkflowName = ref("");

async function loadInstances() {
  try {
    const rows = await fetchUserInstances();
    instanceOptions.value = rows || [];
    instanceMap.value = Object.fromEntries(
      instanceOptions.value.map((i) => [i.id, i.instance_name])
    );
  } catch {
    // 错误提示已由 request 拦截器处理
  }
}

async function loadData() {
  loading.value = true;
  try {
    const { data } = await fetchSqlWorkflows({
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
    // 错误提示已由 request 拦截器处理
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

async function openLogs(row: SqlWorkflowRow) {
  logWorkflowName.value = row.workflow.workflow_name;
  logVisible.value = true;
  logLoading.value = true;
  logList.value = [];
  try {
    const { data } = await fetchWorkflowLogs(row.workflow_id);
    logList.value = data.results || [];
  } catch {
    // 错误提示已由 request 拦截器处理
  } finally {
    logLoading.value = false;
  }
}

function submitSql() {
  router.push({ name: "sqlworkflow-submit" });
}

onMounted(() => {
  loadInstances();
  loadData();
});
</script>

<template>
  <div class="sqlworkflow-page">
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
            v-if="auth.hasPerm('sql.sql_submit')"
            type="success"
            :icon="Document"
            @click="submitSql"
          >
            提交 SQL
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
              {{ row.workflow.workflow_name }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            {{ SYNTAX_TYPE[row.workflow.syntax_type as number] || row.workflow.syntax_type }}
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
              v-if="WORKFLOW_STATUS[row.workflow.status as string]"
              :type="WORKFLOW_STATUS[row.workflow.status as string].type"
              size="small"
            >
              {{ WORKFLOW_STATUS[row.workflow.status as string].label }}
            </el-tag>
            <span v-else>{{ row.workflow.status }}</span>
          </template>
        </el-table-column>
        <el-table-column label="备份" width="70">
          <template #default="{ row }">
            {{ row.workflow.is_backup ? "是" : "否" }}
          </template>
        </el-table-column>
        <el-table-column
          label="发起时间"
          prop="workflow.create_time"
          width="160"
        />
        <el-table-column label="实例" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            {{ instanceMap[row.workflow.instance as number] || row.workflow.instance }}
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
.sqlworkflow-page {
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
