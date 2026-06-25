<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useInstanceSelect } from "@/composables/useInstanceSelect";
import {
  fetchProcess,
  fetchTablespace,
  fetchInnodbTrx,
  fetchTrxAndLocks,
  createKillSession,
  killSession,
  type ProcessRow,
} from "@/api/instance_admin";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const { instanceName, instanceGroups, currentInstance, loadInstances } =
  useInstanceSelect();

const activeTab = ref("process");
const commandType = ref("");

// 各 tab 数据
const processList = ref<ProcessRow[]>([]);
const tablespaceRows = ref<ProcessRow[]>([]);
const tablespaceTotal = ref(0);
const trxList = ref<ProcessRow[]>([]);
const lockList = ref<ProcessRow[]>([]);
const loading = ref(false);

// 表空间分页
const tsPage = ref(1);
const tsSize = ref(20);

// 进程多选
const processSelection = ref<ProcessRow[]>([]);

const canViewProcess = computed(() => auth.hasPerm("sql.process_view"));
const canKill = computed(() => auth.hasPerm("sql.process_kill"));
const canViewTablespace = computed(() => auth.hasPerm("sql.tablespace_view"));
const canViewTrx = computed(() => auth.hasPerm("sql.trx_view"));
const canViewLock = computed(() => auth.hasPerm("sql.trxandlocks_view"));

/** 从进程行取线程 id（多 db_type 适配，对齐旧版 dbdiagnostic.html:748-758） */
function getThreadId(row: ProcessRow): string | number | (string | number)[] | undefined {
  const r = row as Record<string, unknown>;
  if (r.id != null) return r.id as string | number; // mysql
  if (r.opid != null) return r.opid as string | number; // mongo
  if (r.SID != null)
    return [r.SID as string | number, r["SERIAL#"] as string | number]; // oracle
  if (r.kill_id != null) return r.kill_id as string | number; // tdengine
  if (r.query_id != null) return r.query_id as string | number; // clickhouse
  return undefined;
}

async function loadProcess() {
  if (!currentInstance.value) return;
  loading.value = true;
  try {
    processList.value = await fetchProcess({
      instance_name: currentInstance.value.instance_name,
      command_type: commandType.value || undefined,
    });
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

async function loadTablespace() {
  if (!currentInstance.value) return;
  loading.value = true;
  try {
    const r = await fetchTablespace({
      instance_name: currentInstance.value.instance_name,
      offset: (tsPage.value - 1) * tsSize.value,
      limit: tsSize.value,
    });
    tablespaceRows.value = r.rows;
    tablespaceTotal.value = r.total;
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

async function loadTrx() {
  if (!currentInstance.value) return;
  loading.value = true;
  try {
    trxList.value = await fetchInnodbTrx(currentInstance.value.instance_name);
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

async function loadLock() {
  if (!currentInstance.value) return;
  loading.value = true;
  try {
    lockList.value = await fetchTrxAndLocks(currentInstance.value.instance_name);
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

function onTabChange(name: string | number) {
  const t = String(name);
  if (!currentInstance.value) return;
  if (t === "process" && canViewProcess.value) loadProcess();
  else if (t === "tablespace" && canViewTablespace.value) loadTablespace();
  else if (t === "trx" && canViewTrx.value) loadTrx();
  else if (t === "lock" && canViewLock.value) loadLock();
}

watch(instanceName, () => {
  if (currentInstance.value) onTabChange(activeTab.value);
});

/** 两步 kill：先 createKillSession 拿 SQL 确认，再 killSession 执行 */
async function onKill() {
  if (!processSelection.value.length) return ElMessage.warning("请先选择要终止的会话");
  if (!currentInstance.value) return;
  const threadIds = processSelection.value
    .map(getThreadId)
    .filter((x) => x !== undefined);
  if (!threadIds.length) return ElMessage.warning("无法获取所选会话的线程 id");
  try {
    // 第一步：构造 kill SQL（确认线程存活）
    const killSql = await createKillSession({
      instance_name: currentInstance.value.instance_name,
      ThreadIDs: threadIds as (string | number)[],
    });
    if (!killSql) {
      ElMessage.warning("所选会话已终止");
      return;
    }
    // 弹确认
    await ElMessageBox.confirm(
      `将执行以下操作终止会话，确认？\n${killSql}`,
      "终止会话",
      { type: "warning", confirmButtonText: "确定终止", cancelButtonText: "取消" }
    );
    // 第二步：执行 kill
    await killSession({
      instance_name: currentInstance.value.instance_name,
      ThreadIDs: threadIds as (string | number)[],
    });
    ElMessage.success("已终止");
    processSelection.value = [];
    loadProcess();
  } catch (e) {
    if (e !== "cancel") {
      // 业务错误已提示
    }
  }
}

// 进程表格列：动态（行字段不固定，取并集展示常见列）
const processColumns = computed(() => {
  if (!processList.value.length) return ["id", "user", "host", "db", "command", "time", "state", "info"];
  // 取第一行的 key 作列（所有行列一致）
  return Object.keys(processList.value[0]);
});

onMounted(() => {
  loadInstances();
});
</script>

<template>
  <div class="diag-page">
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="实例">
          <el-select v-model="instanceName" filterable placeholder="选择实例" style="width: 240px">
            <el-option-group v-for="grp in instanceGroups" :key="grp.label" :label="grp.label">
              <el-option v-for="i in grp.items" :key="i.id" :label="i.instance_name" :value="i.instance_name" />
            </el-option-group>
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <!-- 进程状态 -->
        <el-tab-pane v-if="canViewProcess" label="进程状态" name="process">
          <div class="toolbar">
            <el-input
              v-model="commandType"
              placeholder="command 类型过滤（可空）"
              style="width: 200px"
              clearable
            />
            <el-button @click="loadProcess">刷新</el-button>
            <el-button v-if="canKill" type="danger" :disabled="!processSelection.length" @click="onKill">
              终止会话 ({{ processSelection.length }})
            </el-button>
          </div>
          <el-table
            v-loading="loading"
            :data="processList"
            stripe
            border
            max-height="560"
            @selection-change="(s: ProcessRow[]) => (processSelection = s)"
          >
            <el-table-column v-if="canKill" type="selection" width="45" />
            <el-table-column
              v-for="col in processColumns"
              :key="col"
              :prop="col"
              :label="col"
              min-width="140"
              show-overflow-tooltip
            />
          </el-table>
        </el-tab-pane>

        <!-- Top 表空间 -->
        <el-tab-pane v-if="canViewTablespace" label="Top 表空间" name="tablespace">
          <el-table v-loading="loading" :data="tablespaceRows" stripe border max-height="560">
            <el-table-column
              v-for="col in tablespaceRows.length ? Object.keys(tablespaceRows[0]) : ['table_schema','table_name','data_length','index_length','data_free']"
              :key="col"
              :prop="col"
              :label="col"
              min-width="140"
              show-overflow-tooltip
            />
          </el-table>
          <div class="pager">
            <el-pagination
              :total="tablespaceTotal"
              :current-page="tsPage"
              :page-size="tsSize"
              layout="total, prev, pager, next"
              background
              @current-change="(p: number) => { tsPage = p; loadTablespace(); }"
            />
          </div>
        </el-tab-pane>

        <!-- 事务信息 -->
        <el-tab-pane v-if="canViewTrx" label="事务信息" name="trx">
          <el-table v-loading="loading" :data="trxList" stripe border max-height="560">
            <el-table-column
              v-for="col in trxList.length ? Object.keys(trxList[0]) : ['trx_id','trx_state','trx_started','trx_wait_started']"
              :key="col"
              :prop="col"
              :label="col"
              min-width="140"
              show-overflow-tooltip
            />
          </el-table>
        </el-tab-pane>

        <!-- 锁信息 -->
        <el-tab-pane v-if="canViewLock" label="锁信息" name="lock">
          <el-table v-loading="loading" :data="lockList" stripe border max-height="560">
            <el-table-column
              v-for="col in lockList.length ? Object.keys(lockList[0]) : ['request_id','lock_mode','lock_type']"
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
.diag-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}

.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
