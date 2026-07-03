<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { useAuthStore } from "@/stores/auth";
import {
  fetchResourceGroups,
  fetchGroupInstances,
  fetchGroupAuditors,
  fetchUserInstances,
  type ResourceGroupRow,
  type GroupInstanceRow,
} from "@/api/group";
import { fetchQueryResources } from "@/api/sqlquery";
import {
  fetchArchiveList,
  archiveApply,
  fetchArchiveLog,
  archiveSwitch,
  archiveOnce,
  ARCHIVE_MODE,
  ARCHIVE_STATUS,
  type ArchiveRow,
  type ArchiveLogRow,
} from "@/api/archiver";

const auth = useAuthStore();
const router = useRouter();

// ===================== 列表 =====================
const loading = ref(false);
const list = ref<ArchiveRow[]>([]);
const total = ref(0);
const instanceOptions = ref<GroupInstanceRow[]>([]);

const query = reactive({
  search: "",
  filter_instance_id: undefined as number | undefined,
  state: "" as "" | "true" | "false",
  page: 1,
  size: 20,
});

async function loadInstances() {
  try {
    // 走用户级接口（按资源组授权过滤），避免普通用户触发 403
    const rows = await fetchUserInstances();
    instanceOptions.value = rows || [];
  } catch {
    // 拦截器已提示
  }
}

async function loadData() {
  loading.value = true;
  try {
    const { total: t, rows } = await fetchArchiveList({
      limit: query.size,
      offset: (query.page - 1) * query.size,
      search: query.search,
      filter_instance_id: query.filter_instance_id,
      state: query.state,
    });
    list.value = rows;
    total.value = t;
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

function goDetail(row: ArchiveRow) {
  router.push({ name: "archive-detail", params: { id: row.id } });
}

// 启用/停用
async function onSwitch(row: ArchiveRow, val: boolean) {
  try {
    await archiveSwitch(row.id, val);
    ElMessage.success(val ? "已启用" : "已停用");
    row.state = val;
  } catch {
    // 拦截器已提示
  }
}

// 单次执行
async function onOnce(row: ArchiveRow) {
  try {
    await ElMessageBox.confirm(`确认立即执行归档「${row.title}」？`, "提示", {
      type: "warning",
    });
    await archiveOnce(row.id);
    ElMessage.success("已提交执行（异步任务）");
  } catch (e) {
    if (e !== "cancel") {
      // 业务错误已由拦截器提示
    }
  }
}

// 归档日志弹窗
const logVisible = ref(false);
const logLoading = ref(false);
const logList = ref<ArchiveLogRow[]>([]);
const logTitle = ref("");

async function openLogs(row: ArchiveRow) {
  logTitle.value = row.title;
  logVisible.value = true;
  logLoading.value = true;
  logList.value = [];
  try {
    const { rows } = await fetchArchiveLog({ archive_id: row.id, limit: 100, offset: 0 });
    logList.value = rows;
  } catch {
    // 拦截器已提示
  } finally {
    logLoading.value = false;
  }
}

// ===================== 申请弹窗 =====================
const applyVisible = ref(false);
const applySubmitting = ref(false);
const groupOptions = ref<ResourceGroupRow[]>([]);
const instanceList = ref<GroupInstanceRow[]>([]);
const auditorsDisplay = ref("");
const srcDbOptions = ref<string[]>([]);
const srcTableOptions = ref<string[]>([]);
const destDbOptions = ref<string[]>([]);
const destTableOptions = ref<string[]>([]);

const applyForm = reactive({
  title: "",
  group_id: undefined as number | undefined,
  src_instance_name: "",
  src_db_name: "",
  src_table_name: "",
  mode: "file" as "file" | "dest" | "purge",
  no_delete: true,
  dest_instance_name: "",
  dest_db_name: "",
  dest_table_name: "",
  condition: "",
  sleep: 1,
});

const showNoDelete = computed(() => applyForm.mode !== "purge");
const showDest = computed(() => applyForm.mode === "dest");

async function openApplyDialog() {
  Object.assign(applyForm, {
    title: "",
    group_id: undefined,
    src_instance_name: "",
    src_db_name: "",
    src_table_name: "",
    mode: "file",
    no_delete: true,
    dest_instance_name: "",
    dest_db_name: "",
    dest_table_name: "",
    condition: "",
    sleep: 1,
  });
  instanceList.value = [];
  auditorsDisplay.value = "";
  srcDbOptions.value = [];
  srcTableOptions.value = [];
  destDbOptions.value = [];
  destTableOptions.value = [];
  applyVisible.value = true;
}

// 选资源组 → 拉实例（mysql）+ 审批流（workflow_type=3）
watch(
  () => applyForm.group_id,
  async (gid) => {
    instanceList.value = [];
    applyForm.src_instance_name = "";
    applyForm.dest_instance_name = "";
    auditorsDisplay.value = "";
    if (!gid) return;
    const grp = groupOptions.value.find((g) => g.group_id === gid);
    if (!grp) return;
    const gname = grp.group_name as string;
    try {
      const all = await fetchGroupInstances(gname, "can_read");
      // 仅 MySQL 支持归档
      instanceList.value = all.filter((i) => i.db_type === "mysql");
    } catch {
      // 拦截器已提示
    }
    try {
      const a = await fetchGroupAuditors(gname, 3);
      auditorsDisplay.value = a.auditors_display || "无需审批";
    } catch {
      // 拦截器已提示
    }
  }
);

// 源实例 → 源库
watch(() => applyForm.src_instance_name, async () => {
  applyForm.src_db_name = "";
  applyForm.src_table_name = "";
  srcDbOptions.value = [];
  srcTableOptions.value = [];
  if (!applyForm.src_instance_name) return;
  try {
    srcDbOptions.value = await fetchQueryResources({
      instance_name: applyForm.src_instance_name,
      resource_type: "database",
    });
  } catch {
    // 拦截器已提示
  }
});

// 源库 → 源表
watch(() => applyForm.src_db_name, async () => {
  applyForm.src_table_name = "";
  srcTableOptions.value = [];
  if (!applyForm.src_db_name) return;
  try {
    srcTableOptions.value = await fetchQueryResources({
      instance_name: applyForm.src_instance_name,
      resource_type: "table",
      db_name: applyForm.src_db_name,
    });
  } catch {
    // 拦截器已提示
  }
});

// 目标实例 → 目标库
watch(() => applyForm.dest_instance_name, async () => {
  applyForm.dest_db_name = "";
  applyForm.dest_table_name = "";
  destDbOptions.value = [];
  destTableOptions.value = [];
  if (!applyForm.dest_instance_name) return;
  try {
    destDbOptions.value = await fetchQueryResources({
      instance_name: applyForm.dest_instance_name,
      resource_type: "database",
    });
  } catch {
    // 拦截器已提示
  }
});

// 目标库 → 目标表
watch(() => applyForm.dest_db_name, async () => {
  applyForm.dest_table_name = "";
  destTableOptions.value = [];
  if (!applyForm.dest_db_name) return;
  try {
    destTableOptions.value = await fetchQueryResources({
      instance_name: applyForm.dest_instance_name,
      resource_type: "table",
      db_name: applyForm.dest_db_name,
    });
  } catch {
    // 拦截器已提示
  }
});

async function submitApply() {
  if (!applyForm.title.trim()) return ElMessage.warning("请填写归档描述");
  if (!applyForm.group_id) return ElMessage.warning("请选择资源组");
  if (!applyForm.src_instance_name) return ElMessage.warning("请选择源实例");
  if (!applyForm.src_db_name) return ElMessage.warning("请选择源数据库");
  if (!applyForm.src_table_name) return ElMessage.warning("请选择源表");
  if (!applyForm.mode) return ElMessage.warning("请选择归档模式");
  if (showDest.value) {
    if (!applyForm.dest_instance_name) return ElMessage.warning("请选择目标实例");
    if (!applyForm.dest_db_name) return ElMessage.warning("请选择目标数据库");
    if (!applyForm.dest_table_name) return ElMessage.warning("请选择目标表");
  }
  if (!applyForm.condition.trim()) return ElMessage.warning("请填写归档条件（WHERE）");
  try {
    applySubmitting.value = true;
    const gname = groupOptions.value.find((g) => g.group_id === applyForm.group_id)
      ?.group_name as string;
    await archiveApply({
      title: applyForm.title.trim(),
      group_name: gname,
      src_instance_name: applyForm.src_instance_name,
      src_db_name: applyForm.src_db_name,
      src_table_name: applyForm.src_table_name,
      mode: applyForm.mode,
      dest_instance_name: showDest.value ? applyForm.dest_instance_name : undefined,
      dest_db_name: showDest.value ? applyForm.dest_db_name : undefined,
      dest_table_name: showDest.value ? applyForm.dest_table_name : undefined,
      condition: applyForm.condition.trim(),
      no_delete: applyForm.no_delete,
      sleep: applyForm.sleep,
    });
    ElMessage.success("提交成功");
    applyVisible.value = false;
    onSearch();
  } catch {
    // 拦截器已提示
  } finally {
    applySubmitting.value = false;
  }
}

onMounted(() => {
  loadInstances();
  if (auth.hasPerm("sql.archive_apply")) {
    fetchResourceGroups({ size: 1000 })
      .then(({ data }) => (groupOptions.value = data.results || []))
      .catch(() => {});
  }
  loadData();
});
</script>

<template>
  <div class="archive-page">
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="实例">
          <el-select
            v-model="query.filter_instance_id"
            placeholder="全部实例"
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
        <el-form-item label="启用状态">
          <el-select v-model="query.state" placeholder="全部" clearable style="width: 120px">
            <el-option label="启用" value="true" />
            <el-option label="未启用" value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="搜索">
          <el-input
            v-model="query.search"
            placeholder="标题/申请人"
            clearable
            @keyup.enter="onSearch"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onSearch">查询</el-button>
          <el-button
            v-if="auth.hasPerm('sql.archive_apply')"
            type="success"
            @click="openApplyDialog"
          >
            申请归档
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="list" stripe border>
        <el-table-column label="标题" min-width="160">
          <template #default="{ row }">
            <el-link type="primary" @click="goDetail(row as ArchiveRow)">
              {{ (row as ArchiveRow).title }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="源实例" prop="src_instance__instance_name" width="140" show-overflow-tooltip />
        <el-table-column label="源表" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            {{ (row as ArchiveRow).src_db_name }}.{{ (row as ArchiveRow).src_table_name }}
          </template>
        </el-table-column>
        <el-table-column label="归档模式" width="120">
          <template #default="{ row }">
            {{ ARCHIVE_MODE[(row as ArchiveRow).mode] }}
          </template>
        </el-table-column>
        <el-table-column label="保留源数据" width="90">
          <template #default="{ row }">
            {{ (row as ArchiveRow).no_delete ? "是" : "否" }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag
              v-if="ARCHIVE_STATUS[(row as ArchiveRow).status]"
              :type="ARCHIVE_STATUS[(row as ArchiveRow).status].type"
              size="small"
            >
              {{ ARCHIVE_STATUS[(row as ArchiveRow).status].label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80" v-if="auth.hasPerm('sql.archive_mgt')">
          <template #default="{ row }">
            <el-switch
              :model-value="(row as ArchiveRow).state"
              @change="(v) => onSwitch(row as ArchiveRow, Boolean(v))"
            />
          </template>
        </el-table-column>
        <el-table-column label="申请人" prop="user_display" width="100" />
        <el-table-column label="申请时间" prop="create_time" width="160" />
        <el-table-column label="组" prop="resource_group__group_name" width="100" show-overflow-tooltip />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="auth.hasPerm('sql.archive_mgt')"
              link
              type="primary"
              @click="onOnce(row as ArchiveRow)"
            >
              立即执行
            </el-button>
            <el-button link type="info" @click="openLogs(row as ArchiveRow)">日志</el-button>
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
          @current-change="(p: number) => { query.page = p; loadData(); }"
          @size-change="(s: number) => { query.size = s; query.page = 1; loadData(); }"
        />
      </div>
    </el-card>

    <!-- 申请归档弹窗 -->
    <el-dialog
      v-model="applyVisible"
      title="申请数据归档"
      width="620px"
      :close-on-click-modal="false"
    >
      <el-form :model="applyForm" label-width="100px">
        <el-form-item label="描述" required>
          <el-input v-model="applyForm.title" placeholder="对归档进行简单描述" />
        </el-form-item>
        <el-form-item label="资源组" required>
          <el-select v-model="applyForm.group_id" placeholder="请选择资源组" filterable style="width: 100%">
            <el-option
              v-for="g in groupOptions"
              :key="g.group_id"
              :label="g.group_name"
              :value="g.group_id"
            />
          </el-select>
          <div v-if="auditorsDisplay" class="hint">审批流：{{ auditorsDisplay }}</div>
        </el-form-item>
        <el-form-item label="源实例" required>
          <el-select v-model="applyForm.src_instance_name" filterable placeholder="请选择源实例" :disabled="!applyForm.group_id" style="width: 100%">
            <el-option v-for="i in instanceList" :key="i.id" :label="i.instance_name" :value="i.instance_name" />
          </el-select>
        </el-form-item>
        <el-form-item label="源数据库" required>
          <el-select v-model="applyForm.src_db_name" filterable placeholder="请选择源数据库" :disabled="!applyForm.src_instance_name" style="width: 100%">
            <el-option v-for="d in srcDbOptions" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="源表" required>
          <el-select v-model="applyForm.src_table_name" filterable placeholder="请选择源表" :disabled="!applyForm.src_db_name" style="width: 100%">
            <el-option v-for="t in srcTableOptions" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="归档模式" required>
          <el-select v-model="applyForm.mode" style="width: 100%">
            <el-option label="归档到文件" value="file" />
            <el-option label="归档到其他实例" value="dest" />
            <el-option label="直接删除" value="purge" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="showNoDelete" label="保留源数据" required>
          <el-switch v-model="applyForm.no_delete" />
        </el-form-item>
        <template v-if="showDest">
          <el-form-item label="目标实例" required>
            <el-select v-model="applyForm.dest_instance_name" filterable placeholder="请选择目标实例" style="width: 100%">
              <el-option v-for="i in instanceList" :key="i.id" :label="i.instance_name" :value="i.instance_name" />
            </el-select>
          </el-form-item>
          <el-form-item label="目标数据库" required>
            <el-select v-model="applyForm.dest_db_name" filterable placeholder="请选择目标数据库" :disabled="!applyForm.dest_instance_name" style="width: 100%">
              <el-option v-for="d in destDbOptions" :key="d" :label="d" :value="d" />
            </el-select>
          </el-form-item>
          <el-form-item label="目标表" required>
            <el-select v-model="applyForm.dest_table_name" filterable placeholder="请选择目标表" :disabled="!applyForm.dest_db_name" style="width: 100%">
              <el-option v-for="t in destTableOptions" :key="t" :label="t" :value="t" />
            </el-select>
          </el-form-item>
        </template>
        <el-form-item label="归档条件" required>
          <el-input
            v-model="applyForm.condition"
            type="textarea"
            :rows="2"
            placeholder="WHERE 条件，如 id < 1000 AND create_time < '2024-01-01'"
          />
        </el-form-item>
        <el-form-item label="休眠秒数">
          <el-input-number v-model="applyForm.sleep" :min="0" />
          <span class="hint">每次归档 limit 行后的休眠秒数</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="applyVisible = false">取消</el-button>
        <el-button type="success" :loading="applySubmitting" @click="submitApply">
          提交申请
        </el-button>
      </template>
    </el-dialog>

    <!-- 归档日志弹窗 -->
    <el-dialog v-model="logVisible" :title="`归档日志 - ${logTitle}`" width="820px">
      <el-table v-loading="logLoading" :data="logList" stripe border max-height="440">
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="(row as ArchiveLogRow).success ? 'success' : 'danger'" size="small">
              {{ (row as ArchiveLogRow).success ? "成功" : "失败" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="查询/插入/删除" width="140">
          <template #default="{ row }">
            {{ (row as ArchiveLogRow).select_cnt }} / {{ (row as ArchiveLogRow).insert_cnt }} / {{ (row as ArchiveLogRow).delete_cnt }}
          </template>
        </el-table-column>
        <el-table-column label="开始时间" prop="start_time" width="160" />
        <el-table-column label="结束时间" prop="end_time" width="160" />
        <el-table-column label="错误信息" prop="error_info" show-overflow-tooltip />
      </el-table>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.archive-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
