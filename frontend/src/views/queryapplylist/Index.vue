<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { useAuthStore } from "@/stores/auth";
import {
  fetchResourceGroups,
  fetchGroupInstances,
  fetchGroupAuditors,
  type ResourceGroupRow,
  type GroupInstanceRow,
} from "@/api/group";
import { fetchQueryResources } from "@/api/sqlquery";
import { fetchWorkflowLogs, type WorkflowLogRow } from "@/api/sqlworkflow";
import {
  fetchApplyList,
  applyForPrivileges,
  fetchUserPrivileges,
  modifyPrivilege,
  PRIV_TYPE_LABEL,
  APPLY_STATUS,
  VALID_DATE_OPTIONS,
  computeValidDate,
  type ApplyRow,
  type UserPrivRow,
} from "@/api/querypriv";

const auth = useAuthStore();
const router = useRouter();

// ===================== Tab 1: 申请列表 =====================
const activeTab = ref("apply");
const applyLoading = ref(false);
const applyList = ref<ApplyRow[]>([]);
const applyTotal = ref(0);
const applyQuery = reactive({
  search: "",
  page: 1,
  size: 20,
});

async function loadApplyList() {
  applyLoading.value = true;
  try {
    const { total, rows } = await fetchApplyList({
      limit: applyQuery.size,
      offset: (applyQuery.page - 1) * applyQuery.size,
      search: applyQuery.search,
    });
    applyList.value = rows;
    applyTotal.value = total;
  } catch {
    // 拦截器已提示
  } finally {
    applyLoading.value = false;
  }
}

function onApplySearch() {
  applyQuery.page = 1;
  loadApplyList();
}

function dbListDisplay(row: ApplyRow): string {
  return row.priv_type === 2 ? row.table_list : row.db_list;
}

function goDetail(row: ApplyRow) {
  router.push({ name: "queryapply-detail", params: { id: row.apply_id } });
}

// 操作日志弹窗
const logVisible = ref(false);
const logLoading = ref(false);
const logList = ref<WorkflowLogRow[]>([]);
const logTitle = ref("");

async function openLogs(row: ApplyRow) {
  logTitle.value = row.title;
  logVisible.value = true;
  logLoading.value = true;
  logList.value = [];
  try {
    const { data } = await fetchWorkflowLogs(row.apply_id, 1);
    logList.value = data.results || [];
  } catch {
    // 拦截器已提示
  } finally {
    logLoading.value = false;
  }
}

// ===================== 申请权限弹窗 =====================
const applyDialogVisible = ref(false);
const applySubmitting = ref(false);
const groupOptions = ref<ResourceGroupRow[]>([]);
const instanceOptions = ref<GroupInstanceRow[]>([]);
const auditorsDisplay = ref("");
const dbOptions = ref<string[]>([]);
const tableOptions = ref<string[]>([]);

const applyForm = reactive({
  title: "",
  group_id: undefined as number | undefined,
  instance_name: "",
  priv_type: 1 as number,
  db_name: "", // priv_type=2 单库
  db_list: [] as string[], // priv_type=1 多库
  table_list: [] as string[], // priv_type=2 多表
  valid_date: "day",
  limit_num: 1000,
});

// 当前选中实例的 db_type（决定 priv_type 可选项：MySQL 才支持 TABLE）
const currentDbType = computed(() => {
  const inst = instanceOptions.value.find(
    (i) => i.instance_name === applyForm.instance_name
  );
  return inst?.db_type || "";
});

const privTypeOptions = computed(() => {
  if (currentDbType.value === "mysql") {
    return [
      { value: 1, label: "DATABASE" },
      { value: 2, label: "TABLE" },
    ];
  }
  return [{ value: 1, label: "DATABASE" }];
});

async function openApplyDialog() {
  // 重置
  Object.assign(applyForm, {
    title: "",
    group_id: undefined,
    instance_name: "",
    priv_type: 1,
    db_name: "",
    db_list: [],
    table_list: [],
    valid_date: "day",
    limit_num: 1000,
  });
  instanceOptions.value = [];
  auditorsDisplay.value = "";
  dbOptions.value = [];
  tableOptions.value = [];
  applyDialogVisible.value = true;
}

// 选资源组 → 拉实例（tag_code=can_read）+ 审批流（workflow_type=1）
watch(
  () => applyForm.group_id,
  async (gid) => {
    instanceOptions.value = [];
    applyForm.instance_name = "";
    auditorsDisplay.value = "";
    if (!gid) return;
    const grp = groupOptions.value.find((g) => g.group_id === gid);
    if (!grp) return;
    const gname = grp.group_name as string;
    try {
      instanceOptions.value = await fetchGroupInstances(gname, "can_read");
    } catch {
      // 拦截器已提示
    }
    try {
      const a = await fetchGroupAuditors(gname, 1);
      auditorsDisplay.value = a.auditors_display || "无需审批";
    } catch {
      // 拦截器已提示
    }
  }
);

// 选实例 → 拉库；并按 db_type 重置 priv_type
watch(() => applyForm.instance_name, async () => {
  applyForm.db_name = "";
  applyForm.db_list = [];
  applyForm.table_list = [];
  dbOptions.value = [];
  tableOptions.value = [];
  if (!applyForm.instance_name) return;
  // 非 MySQL 强制库权限
  if (currentDbType.value !== "mysql") applyForm.priv_type = 1;
  else if (applyForm.priv_type === 1 && !privTypeOptions.value.some((o) => o.value === 1))
    applyForm.priv_type = 2;
  try {
    dbOptions.value = await fetchQueryResources({
      instance_name: applyForm.instance_name,
      resource_type: "database",
    });
  } catch {
    // 拦截器已提示
  }
});

// priv_type 切换清空选项
watch(() => applyForm.priv_type, () => {
  applyForm.db_list = [];
  applyForm.table_list = [];
});

// 库权限选了单库（表权限用）→ 拉表
watch(() => applyForm.db_name, async () => {
  applyForm.table_list = [];
  tableOptions.value = [];
  if (!applyForm.db_name) return;
  try {
    tableOptions.value = await fetchQueryResources({
      instance_name: applyForm.instance_name,
      resource_type: "table",
      db_name: applyForm.db_name,
    });
  } catch {
    // 拦截器已提示
  }
});

async function submitApply() {
  if (!applyForm.title.trim()) return ElMessage.warning("请填写权限用途说明");
  if (!applyForm.group_id) return ElMessage.warning("请选择资源组");
  if (!applyForm.instance_name) return ElMessage.warning("请选择实例");
  if (applyForm.priv_type === 1 && applyForm.db_list.length === 0)
    return ElMessage.warning("请选择数据库");
  if (applyForm.priv_type === 2) {
    if (!applyForm.db_name) return ElMessage.warning("请选择数据库");
    if (applyForm.table_list.length === 0) return ElMessage.warning("请选择表");
  }
  if (!applyForm.limit_num) return ElMessage.warning("请填写查询限制行数");
  try {
    applySubmitting.value = true;
    await applyForPrivileges({
      title: applyForm.title.trim(),
      instance_name: applyForm.instance_name,
      group_name: (groupOptions.value.find((g) => g.group_id === applyForm.group_id)?.group_name as string),
      priv_type: applyForm.priv_type,
      db_name: applyForm.priv_type === 2 ? applyForm.db_name : undefined,
      db_list: applyForm.priv_type === 1 ? applyForm.db_list : undefined,
      table_list: applyForm.priv_type === 2 ? applyForm.table_list : undefined,
      valid_date: computeValidDate(applyForm.valid_date),
      limit_num: applyForm.limit_num,
    });
    ElMessage.success("提交成功");
    applyDialogVisible.value = false;
    onApplySearch();
  } catch {
    // 拦截器已提示
  } finally {
    applySubmitting.value = false;
  }
}

// ===================== Tab 2: 用户权限管理 =====================
const privLoading = ref(false);
const privList = ref<UserPrivRow[]>([]);
const privTotal = ref(0);
const privQuery = reactive({ search: "", page: 1, size: 20 });

async function loadPrivList() {
  privLoading.value = true;
  try {
    const { total, rows } = await fetchUserPrivileges({
      limit: privQuery.size,
      offset: (privQuery.page - 1) * privQuery.size,
      search: privQuery.search,
    });
    privList.value = rows;
    privTotal.value = total;
  } catch {
    // 拦截器已提示
  } finally {
    privLoading.value = false;
  }
}

function onPrivSearch() {
  privQuery.page = 1;
  loadPrivList();
}

// 变更权限弹窗
const modifyVisible = ref(false);
const modifySubmitting = ref(false);
const modifyForm = reactive({
  privilege_id: 0,
  valid_date: "",
  limit_num: 0,
});

function openModify(row: UserPrivRow) {
  modifyForm.privilege_id = row.privilege_id;
  modifyForm.valid_date = row.valid_date;
  modifyForm.limit_num = Number(row.limit_num);
  modifyVisible.value = true;
}

async function submitModify() {
  try {
    modifySubmitting.value = true;
    await modifyPrivilege({
      privilege_id: modifyForm.privilege_id,
      type: 2,
      valid_date: modifyForm.valid_date,
      limit_num: modifyForm.limit_num,
    });
    ElMessage.success("变更成功");
    modifyVisible.value = false;
    loadPrivList();
  } catch {
    // 拦截器已提示
  } finally {
    modifySubmitting.value = false;
  }
}

async function onDelete(row: UserPrivRow) {
  try {
    await ElMessageBox.confirm(
      `确认删除 ${row.user_display} 在 ${row.instance__instance_name} 的权限？`,
      "提示",
      { type: "warning" }
    );
    await modifyPrivilege({ privilege_id: row.privilege_id, type: 1 });
    ElMessage.success("已删除");
    loadPrivList();
  } catch (e) {
    if (e !== "cancel") {
      // 业务错误已由拦截器提示
    }
  }
}

function onTabChange(name: string | number) {
  if (name === "priv" && privList.value.length === 0) loadPrivList();
}

onMounted(async () => {
  if (auth.hasPerm("sql.query_applypriv")) {
    try {
      const { data } = await fetchResourceGroups({ size: 1000 });
      groupOptions.value = data.results || [];
    } catch {
      // 拦截器已提示
    }
  }
  loadApplyList();
});
</script>

<template>
  <div class="queryapply-page">
    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <!-- Tab 1: 申请列表 -->
      <el-tab-pane label="申请列表" name="apply">
        <el-card shadow="never" class="filter-card">
          <el-form :inline="true" @submit.prevent>
            <el-form-item label="搜索">
              <el-input
                v-model="applyQuery.search"
                placeholder="工单名称/申请人"
                clearable
                @keyup.enter="onApplySearch"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="onApplySearch">查询</el-button>
              <el-button
                v-if="auth.hasPerm('sql.query_applypriv')"
                type="success"
                @click="openApplyDialog"
              >
                申请权限
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card shadow="never">
          <el-table
            v-loading="applyLoading"
            :data="applyList"
            stripe
            border
            row-key="apply_id"
          >
            <el-table-column type="expand">
              <template #default="{ row }">
                <div class="expand-detail">
                  <template v-if="row.priv_type === 2">
                    表清单：<br />{{ (row as ApplyRow).table_list.replace(/,/g, "\n") }}
                  </template>
                  <template v-else>
                    数据库清单：<br />{{ (row as ApplyRow).db_list.replace(/,/g, "\n") }}
                  </template>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="工单名称" min-width="160">
              <template #default="{ row }">
                <el-link type="primary" @click="goDetail(row as ApplyRow)">
                  {{ (row as ApplyRow).title }}
                </el-link>
              </template>
            </el-table-column>
            <el-table-column
              label="实例"
              prop="instance__instance_name"
              width="140"
              show-overflow-tooltip
            />
            <el-table-column label="数据库" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">
                {{ dbListDisplay(row as ApplyRow) }}
              </template>
            </el-table-column>
            <el-table-column label="权限级别" width="100">
              <template #default="{ row }">
                {{ PRIV_TYPE_LABEL[(row as ApplyRow).priv_type] }}
              </template>
            </el-table-column>
            <el-table-column label="结果集" prop="limit_num" width="80" />
            <el-table-column label="有效时间" prop="valid_date" width="120" />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag
                  v-if="APPLY_STATUS[(row as ApplyRow).status]"
                  :type="APPLY_STATUS[(row as ApplyRow).status].type"
                  size="small"
                >
                  {{ APPLY_STATUS[(row as ApplyRow).status].label }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="申请人" prop="user_display" width="100" />
            <el-table-column label="申请时间" prop="create_time" width="160" />
            <el-table-column label="组" prop="group_name" width="100" show-overflow-tooltip />
            <el-table-column label="操作" width="90" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openLogs(row as ApplyRow)">
                  操作日志
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pager">
            <el-pagination
              :current-page="applyQuery.page"
              :page-size="applyQuery.size"
              :page-sizes="[20, 30, 50, 100]"
              :total="applyTotal"
              layout="total, sizes, prev, pager, next, jumper"
              background
              @current-change="(p: number) => { applyQuery.page = p; loadApplyList(); }"
              @size-change="(s: number) => { applyQuery.size = s; applyQuery.page = 1; loadApplyList(); }"
            />
          </div>
        </el-card>
      </el-tab-pane>

      <!-- Tab 2: 权限管理 -->
      <el-tab-pane label="权限管理" name="priv">
        <el-card shadow="never" class="filter-card">
          <el-form :inline="true" @submit.prevent>
            <el-form-item label="搜索">
              <el-input
                v-model="privQuery.search"
                placeholder="用户/数据库/表"
                clearable
                @keyup.enter="onPrivSearch"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="onPrivSearch">查询</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card shadow="never">
          <el-table v-loading="privLoading" :data="privList" stripe border>
            <el-table-column label="用户" prop="user_display" width="110" />
            <el-table-column
              label="实例"
              prop="instance__instance_name"
              width="140"
              show-overflow-tooltip
            />
            <el-table-column label="数据库" prop="db_name" width="130" show-overflow-tooltip />
            <el-table-column label="权限级别" width="90">
              <template #default="{ row }">
                {{ PRIV_TYPE_LABEL[(row as UserPrivRow).priv_type] }}
              </template>
            </el-table-column>
            <el-table-column label="表" prop="table_name" min-width="140" show-overflow-tooltip />
            <el-table-column label="结果集" prop="limit_num" width="80" />
            <el-table-column label="有效时间" prop="valid_date" width="120" />
            <el-table-column
              v-if="auth.hasPerm('sql.query_mgtpriv')"
              label="操作"
              width="130"
              fixed="right"
            >
              <template #default="{ row }">
                <el-button link type="primary" @click="openModify(row as UserPrivRow)">变更</el-button>
                <el-button link type="danger" @click="onDelete(row as UserPrivRow)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pager">
            <el-pagination
              :current-page="privQuery.page"
              :page-size="privQuery.size"
              :page-sizes="[20, 30, 50, 100]"
              :total="privTotal"
              layout="total, sizes, prev, pager, next, jumper"
              background
              @current-change="(p: number) => { privQuery.page = p; loadPrivList(); }"
              @size-change="(s: number) => { privQuery.size = s; privQuery.page = 1; loadPrivList(); }"
            />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 申请权限弹窗 -->
    <el-dialog
      v-model="applyDialogVisible"
      title="申请数据库查询权限"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form :model="applyForm" label-width="90px">
        <el-form-item label="用途说明" required>
          <el-input v-model="applyForm.title" placeholder="简单说明权限用途" />
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
        <el-form-item label="实例" required>
          <el-select
            v-model="applyForm.instance_name"
            placeholder="请选择实例"
            filterable
            :disabled="!applyForm.group_id"
            style="width: 100%"
          >
            <el-option
              v-for="i in instanceOptions"
              :key="i.id"
              :label="i.instance_name"
              :value="i.instance_name"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="权限级别" required>
          <el-select v-model="applyForm.priv_type" style="width: 100%">
            <el-option
              v-for="o in privTypeOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <!-- 库权限：多选库 -->
        <template v-if="applyForm.priv_type === 1">
          <el-form-item label="数据库" required>
            <el-select
              v-model="applyForm.db_list"
              multiple
              filterable
              placeholder="请选择数据库（可多选）"
              style="width: 100%"
            >
              <el-option v-for="d in dbOptions" :key="d" :label="d" :value="d" />
            </el-select>
          </el-form-item>
        </template>
        <!-- 表权限：单选库 + 多选表 -->
        <template v-else>
          <el-form-item label="数据库" required>
            <el-select v-model="applyForm.db_name" filterable placeholder="请选择数据库" style="width: 100%">
              <el-option v-for="d in dbOptions" :key="d" :label="d" :value="d" />
            </el-select>
          </el-form-item>
          <el-form-item label="表" required>
            <el-select
              v-model="applyForm.table_list"
              multiple
              filterable
              placeholder="请选择表（可多选）"
              style="width: 100%"
            >
              <el-option v-for="t in tableOptions" :key="t" :label="t" :value="t" />
            </el-select>
          </el-form-item>
        </template>
        <el-form-item label="授权时长" required>
          <el-select v-model="applyForm.valid_date" style="width: 100%">
            <el-option
              v-for="o in VALID_DATE_OPTIONS"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="限制行数" required>
          <el-input-number v-model="applyForm.limit_num" :min="1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="applyDialogVisible = false">取消</el-button>
        <el-button type="success" :loading="applySubmitting" @click="submitApply">
          提交申请
        </el-button>
      </template>
    </el-dialog>

    <!-- 变更权限弹窗 -->
    <el-dialog v-model="modifyVisible" title="变更权限" width="420px">
      <el-form :model="modifyForm" label-width="90px">
        <el-form-item label="有效时间" required>
          <el-date-picker
            v-model="modifyForm.valid_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="限制行数" required>
          <el-input-number v-model="modifyForm.limit_num" :min="1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="modifyVisible = false">取消</el-button>
        <el-button type="primary" :loading="modifySubmitting" @click="submitModify">
          确认变更
        </el-button>
      </template>
    </el-dialog>

    <!-- 操作日志弹窗 -->
    <el-dialog v-model="logVisible" :title="`操作日志 - ${logTitle}`" width="720px">
      <el-table v-loading="logLoading" :data="logList" stripe border max-height="420">
        <el-table-column label="操作" prop="operation_type_desc" width="120" />
        <el-table-column label="操作人" prop="operator_display" width="120" />
        <el-table-column label="操作时间" prop="operation_time" width="160" />
        <el-table-column label="操作信息" prop="operation_info" show-overflow-tooltip />
      </el-table>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.queryapply-page {
  display: flex;
  flex-direction: column;
}

.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.expand-detail {
  padding: 8px 16px;
  white-space: pre-wrap;
  color: var(--el-text-color-regular);
  font-size: 13px;
}

.hint {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
