<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { ArrowRight } from "@element-plus/icons-vue";
import { useAuthStore } from "@/stores/auth";
import { fetchInstances } from "@/api/instance";
import {
  fetchWorkflowDetail,
  fetchWorkflowLogs,
  auditWorkflow,
  executeWorkflow,
  timingTask,
  alterRunDate,
  WORKFLOW_STATUS,
  SYNTAX_TYPE,
  type SqlWorkflowDetail,
  type ReviewRow,
  type WorkflowLogRow,
} from "@/api/sqlworkflow";
import SqlReviewTable from "@/components/SqlReviewTable.vue";
import { downloadExportFile } from "@/api/sqlexport";
import { fetchBackupSql, downloadRollback } from "@/api/sqlworkflow";

const route = useRoute();
const auth = useAuthStore();
const workflowId = Number(route.params.id);

const loading = ref(false);
const detail = ref<SqlWorkflowDetail | null>(null);
const instanceMap = ref<Record<number, string>>({});

// 日志 tab（懒加载）
const activeTab = ref("detail");
const logLoading = ref(false);
const logList = ref<WorkflowLogRow[]>([]);
let logLoaded = false;

// 定时执行弹窗
const timingVisible = ref(false);
const timingForm = reactive({ run_date: "" });

// 改可执行时间弹窗
const runDateVisible = ref(false);
const runDateForm = reactive({ run_date_start: "", run_date_end: "" });

// 执行状态轮询
let pollTimer: number | null = null;

async function loadInstances() {
  try {
    const { data } = await fetchInstances({ size: 1000 });
    instanceMap.value = Object.fromEntries(
      (data.results || []).map((i) => [i.id, i.instance_name])
    );
  } catch {
    // 拦截器已提示
  }
}

async function loadDetail() {
  loading.value = true;
  try {
    const { data } = await fetchWorkflowDetail(workflowId);
    detail.value = data;
    const st = data.workflow.status;
    if (st === "workflow_executing" || st === "workflow_queuing") {
      startPolling();
    } else {
      stopPolling();
    }
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

async function loadLogs() {
  if (logLoaded) return;
  logLoading.value = true;
  try {
    const { data } = await fetchWorkflowLogs(workflowId);
    logList.value = data.results || [];
    logLoaded = true;
  } catch {
    // 拦截器已提示
  } finally {
    logLoading.value = false;
  }
}

function onTabChange(name: string | number) {
  if (String(name) === "logs") loadLogs();
}

/** 解析 ReviewSet JSON，兼容新格式（rows 为 dict 列表）与旧格式（rows 为 [[...], ...] + column_list） */
function parseRows(jsonStr?: string): ReviewRow[] {
  if (!jsonStr) return [];
  try {
    const obj = JSON.parse(jsonStr);
    const rows = obj?.rows ?? obj?.data ?? [];
    if (Array.isArray(rows) && rows.length && Array.isArray(rows[0])) {
      const cols: string[] = obj?.column_list ?? [];
      return rows.map((r: unknown[]) => {
        const o: Record<string, unknown> = {};
        cols.forEach((c, i) => (o[c] = r[i]));
        return o as ReviewRow;
      });
    }
    return Array.isArray(rows) ? (rows as ReviewRow[]) : [];
  } catch {
    return [];
  }
}

const isFinished = computed(
  () =>
    !!detail.value &&
    ["workflow_finish", "workflow_exception"].includes(
      detail.value.workflow.status
    )
);

const reviewRows = computed<ReviewRow[]>(() => {
  if (!detail.value) return [];
  const field = isFinished.value
    ? detail.value.execute_result
    : detail.value.review_content;
  return parseRows(field);
});

const statusTag = computed(() => {
  const s = detail.value?.workflow.status;
  return s ? WORKFLOW_STATUS[s] : null;
});

const instanceName = computed(() => {
  if (!detail.value) return "";
  const id = detail.value.workflow.instance as number;
  return instanceMap.value[id] || String(id);
});

function startPolling() {
  if (pollTimer) return;
  pollTimer = window.setInterval(async () => {
    try {
      const { data } = await fetchWorkflowDetail(workflowId);
      detail.value = data;
      const st = data.workflow.status;
      if (st !== "workflow_executing" && st !== "workflow_queuing") {
        stopPolling();
        ElMessage.success("工单状态已更新");
      }
    } catch {
      // 拦截器已提示
    }
  }, 3000);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

/** 操作成功后：清日志缓存并重拉详情 */
function afterAction() {
  logLoaded = false;
  if (activeTab.value === "logs") loadLogs();
  loadDetail();
}

/** 是否为已完成的导出工单（可下载文件） */
const canDownload = computed(() => {
  const w = detail.value?.workflow;
  return !!(
    w &&
    Number(w.is_offline_export) === 1 &&
    w.file_name &&
    w.status === "workflow_finish"
  );
});

const downloading = ref(false);

async function onDownload() {
  if (!detail.value?.workflow.file_name) return;
  downloading.value = true;
  try {
    await downloadExportFile(workflowId, detail.value.workflow.file_name);
  } catch (e) {
    ElMessage.error(`下载失败：${(e as Error).message || "服务器连接失败"}`);
  } finally {
    downloading.value = false;
  }
}

// 回滚 SQL
const rollbackVisible = ref(false);
const rollbackLoading = ref(false);
const rollbackRows = ref<ReviewRow[]>([]);

async function onViewRollback() {
  rollbackVisible.value = true;
  rollbackLoading.value = true;
  rollbackRows.value = [];
  try {
    rollbackRows.value = await fetchBackupSql(workflowId);
  } catch (e) {
    ElMessage.error(`获取回滚语句失败：${(e as Error).message}`);
  } finally {
    rollbackLoading.value = false;
  }
}

function onDownloadRollback() {
  downloadRollback(workflowId);
}

async function onPass() {
  try {
    const { value } = await ElMessageBox.prompt("审核备注", "审核通过", {
      inputType: "textarea",
      inputPlaceholder: "请输入审核备注（可空）",
      confirmButtonText: "通过",
      cancelButtonText: "取消",
    });
    await auditWorkflow({
      engineer: auth.user?.username || "",
      workflow_id: workflowId,
      audit_type: "pass",
      audit_remark: value || "",
    });
    ElMessage.success("已审核通过");
    afterAction();
  } catch (e) {
    if (e !== "cancel") {
      // 业务错误已由拦截器提示
    }
  }
}

async function onCancel() {
  try {
    const { value } = await ElMessageBox.prompt("请输入终止/驳回原因", "终止流程", {
      inputType: "textarea",
      inputPlaceholder: "原因（必填）",
      inputValidator: (v) => !!v?.trim() || "原因不能为空",
      confirmButtonText: "确定",
      cancelButtonText: "取消",
    });
    await auditWorkflow({
      engineer: auth.user?.username || "",
      workflow_id: workflowId,
      audit_type: "cancel",
      audit_remark: value,
    });
    ElMessage.success("已终止");
    afterAction();
  } catch (e) {
    if (e !== "cancel") {
      // 业务错误已由拦截器提示
    }
  }
}

async function onExecute(mode: "auto" | "manual", label: string) {
  try {
    await ElMessageBox.confirm(`确认${label}？`, "提示", { type: "warning" });
    await executeWorkflow({
      engineer: auth.user?.username || "",
      workflow_id: workflowId,
      mode,
    });
    ElMessage.success("已提交执行");
    afterAction();
  } catch (e) {
    if (e !== "cancel") {
      // 业务错误已由拦截器提示
    }
  }
}

function openTiming() {
  timingForm.run_date = "";
  timingVisible.value = true;
}

async function onTimingConfirm() {
  if (!timingForm.run_date) {
    ElMessage.warning("请选择执行时间");
    return;
  }
  try {
    await timingTask({
      workflow_id: workflowId,
      run_date: timingForm.run_date,
    });
    ElMessage.success("定时执行已设置");
    timingVisible.value = false;
    afterAction();
  } catch {
    // 业务错误已由拦截器提示
  }
}

function openRunDate() {
  runDateForm.run_date_start =
    (detail.value?.workflow.run_date_start as string) || "";
  runDateForm.run_date_end = (detail.value?.workflow.run_date_end as string) || "";
  runDateVisible.value = true;
}

async function onRunDateConfirm() {
  try {
    await alterRunDate({
      workflow_id: workflowId,
      run_date_start: runDateForm.run_date_start || undefined,
      run_date_end: runDateForm.run_date_end || undefined,
    });
    ElMessage.success("可执行时间已更新");
    runDateVisible.value = false;
    loadDetail();
  } catch {
    // 业务错误已由拦截器提示
  }
}

onMounted(() => {
  loadInstances();
  loadDetail();
});

onUnmounted(stopPolling);
</script>

<template>
  <div v-loading="loading" class="detail-page">
    <template v-if="detail">
      <!-- 顶部：工单名 + 状态 -->
      <el-card shadow="never">
        <div class="header-top">
          <el-tag v-if="statusTag" :type="statusTag.type" size="small">
            {{ statusTag.label }}
          </el-tag>
          <span class="title">{{ detail.workflow.workflow_name }}</span>
          <el-link
            v-if="detail.workflow.demand_url"
            :href="detail.workflow.demand_url as string"
            target="_blank"
            type="primary"
            class="demand-link"
          >
            需求链接
          </el-link>
        </div>
      </el-card>

      <!-- 审批流 -->
      <el-card shadow="never">
        <template #header>审批流</template>
        <div class="review-flow">
          <template v-for="(node, idx) in detail.review_info" :key="idx">
            <el-tooltip
              v-if="node.is_current_node && detail.current_reviewers.length"
              :content="'当前审核人：' + detail.current_reviewers.map((r) => r.display).join('、')"
            >
              <el-tag type="primary" effect="dark">
                {{ node.is_auto_pass ? "系统自动通过" : node.group_name }}
              </el-tag>
            </el-tooltip>
            <el-tag v-else :type="node.is_passed_node ? 'success' : 'info'">
              {{ node.is_auto_pass ? "系统自动通过" : node.group_name }}
            </el-tag>
            <el-icon v-if="idx < detail.review_info.length - 1" class="arrow">
              <ArrowRight />
            </el-icon>
          </template>
          <span v-if="!detail.review_info.length" class="muted">无需审批</span>
        </div>
      </el-card>

      <!-- 基本信息 -->
      <el-card shadow="never">
        <template #header>基本信息</template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="发起人">
            {{ detail.workflow.engineer_display }}
          </el-descriptions-item>
          <el-descriptions-item label="目标实例">
            {{ instanceName }}
          </el-descriptions-item>
          <el-descriptions-item label="数据库">
            {{ detail.workflow.db_name }}
          </el-descriptions-item>
          <el-descriptions-item label="发起时间">
            {{ detail.workflow.create_time }}
          </el-descriptions-item>
          <el-descriptions-item label="可执行时间">
            {{ (detail.workflow.run_date_start as string) || "无限制" }}
            ~
            {{ (detail.workflow.run_date_end as string) || "无限制" }}
          </el-descriptions-item>
          <el-descriptions-item label="类型">
            {{
              SYNTAX_TYPE[detail.workflow.syntax_type as number] ||
              detail.workflow.syntax_type
            }}
          </el-descriptions-item>
          <el-descriptions-item label="备份">
            {{ detail.workflow.is_backup ? "是" : "否" }}
          </el-descriptions-item>
          <el-descriptions-item label="组">
            {{ detail.workflow.group_name }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.run_date" label="定时执行时间">
            {{ detail.run_date }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- Tabs：工单详情 + 操作日志 -->
      <el-card shadow="never">
        <el-tabs v-model="activeTab" @tab-change="onTabChange">
          <el-tab-pane label="工单详情" name="detail">
            <SqlReviewTable
              :rows="reviewRows"
              :phase="isFinished ? 'execute' : 'review'"
            />
            <div v-if="detail.last_operation_info" class="last-op">
              最后操作：{{ detail.last_operation_info }}
            </div>
          </el-tab-pane>
          <el-tab-pane label="操作日志" name="logs">
            <el-table v-loading="logLoading" :data="logList" stripe border>
              <el-table-column
                label="操作"
                prop="operation_type_desc"
                width="120"
              />
              <el-table-column
                label="操作人"
                prop="operator_display"
                width="120"
              />
              <el-table-column
                label="操作时间"
                prop="operation_time"
                width="160"
              />
              <el-table-column
                label="操作信息"
                prop="operation_info"
                show-overflow-tooltip
              />
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </el-card>

      <!-- 底部操作按钮区（按后端 is_can_* 显隐） -->
      <el-card shadow="never" class="action-card" body-style="padding: 12px 16px">
        <el-button v-if="detail.is_can_review" type="primary" @click="onPass">
          审核通过
        </el-button>
        <el-button v-if="detail.is_can_review" @click="openRunDate">
          改可执行时间
        </el-button>
        <el-button
          v-if="detail.is_can_execute"
          type="success"
          @click="onExecute('auto', '立即执行')"
        >
          立即执行
        </el-button>
        <el-button
          v-if="detail.is_can_execute && detail.manual"
          type="success"
          @click="onExecute('manual', '已手工完成')"
        >
          已手工完成
        </el-button>
        <el-button v-if="detail.is_can_timingtask" @click="openTiming">
          定时执行
        </el-button>
        <el-button v-if="detail.is_can_cancel" type="danger" @click="onCancel">
          终止/驳回
        </el-button>
        <el-button
          v-if="canDownload"
          type="warning"
          :loading="downloading"
          @click="onDownload"
        >
          下载文件
        </el-button>
        <el-button v-if="detail.is_can_rollback" @click="onViewRollback">
          查看回滚SQL
        </el-button>
        <el-button v-if="detail.is_can_rollback" @click="onDownloadRollback">
          下载回滚SQL
        </el-button>
      </el-card>
    </template>

    <!-- 定时执行弹窗 -->
    <el-dialog v-model="timingVisible" title="定时执行" width="400px">
      <el-date-picker
        v-model="timingForm.run_date"
        type="datetime"
        value-format="YYYY-MM-DD HH:mm"
        placeholder="选择执行时间（须晚于当前）"
        style="width: 100%"
      />
      <template #footer>
        <el-button @click="timingVisible = false">取消</el-button>
        <el-button type="primary" @click="onTimingConfirm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 回滚 SQL 弹窗 -->
    <el-dialog v-model="rollbackVisible" title="回滚 SQL" width="860px">
      <SqlReviewTable v-loading="rollbackLoading" :rows="rollbackRows" phase="review" />
    </el-dialog>

    <!-- 改可执行时间弹窗 -->
    <el-dialog v-model="runDateVisible" title="修改可执行时间" width="480px">
      <el-form label-width="100px">
        <el-form-item label="开始时间">
          <el-date-picker
            v-model="runDateForm.run_date_start"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-date-picker
            v-model="runDateForm.run_date_end"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="runDateVisible = false">取消</el-button>
        <el-button type="primary" @click="onRunDateConfirm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.detail-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-top {
  display: flex;
  align-items: center;
  gap: 8px;

  .title {
    font-size: 16px;
    font-weight: 600;
  }

  .demand-link {
    margin-left: 4px;
  }
}

.review-flow {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;

  .arrow {
    color: var(--el-text-color-secondary);
  }
}

.muted {
  color: var(--el-text-color-secondary);
}

.last-op {
  margin-top: 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.action-card {
  :deep(.el-card__body) {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
}
</style>
