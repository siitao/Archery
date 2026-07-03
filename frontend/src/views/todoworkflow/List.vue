<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { useAuthStore } from "@/stores/auth";
import {
  fetchTodoList,
  auditTodo,
  WORKFLOW_TYPE,
  AUDIT_STATUS,
  type TodoRow,
} from "@/api/todoworkflow";

const auth = useAuthStore();
const router = useRouter();

const loading = ref(false);
const list = ref<TodoRow[]>([]);
const total = ref(0);

const query = reactive({
  page: 1,
  size: 20,
});

async function loadData() {
  loading.value = true;
  try {
    const { data } = await fetchTodoList({
      page: query.page,
      size: query.size,
      engineer: auth.user?.username,
    });
    list.value = data.results || [];
    total.value = data.count || 0;
  } catch {
    // 错误提示已由 request 拦截器处理
  } finally {
    loading.value = false;
  }
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

/** 按 workflow_type 跳转对应详情页 */
function goDetail(row: TodoRow) {
  const id = row.workflow_id;
  if (row.workflow_type === 2) {
    router.push({ name: "sqlworkflow-detail", params: { id } });
  } else if (row.workflow_type === 1) {
    router.push({ name: "queryapply-detail", params: { id } });
  } else if (row.workflow_type === 3) {
    router.push({ name: "archive-detail", params: { id } });
  }
}

// ============ 快捷审批 ============
const auditVisible = ref(false);
const auditLoading = ref(false);
const auditForm = reactive({
  audit_id: 0,
  workflow_id: 0,
  workflow_type: 0,
  workflow_title: "",
  audit_type: "pass" as "pass" | "cancel",
  audit_remark: "",
});

function openAudit(row: TodoRow, type: "pass" | "cancel") {
  auditForm.audit_id = row.audit_id;
  auditForm.workflow_id = row.workflow_id;
  auditForm.workflow_type = row.workflow_type;
  auditForm.workflow_title = row.workflow_title;
  auditForm.audit_type = type;
  auditForm.audit_remark = "";
  auditVisible.value = true;
}

async function onAudit() {
  if (!auditForm.audit_remark.trim()) {
    return ElMessage.warning("请填写审核备注");
  }
  auditLoading.value = true;
  try {
    await auditTodo({
      engineer: auth.user?.username || "",
      workflow_id: auditForm.workflow_id,
      workflow_type: auditForm.workflow_type,
      audit_type: auditForm.audit_type,
      audit_remark: auditForm.audit_remark,
    });
    ElMessage.success(auditForm.audit_type === "pass" ? "已通过" : "已驳回");
    auditVisible.value = false;
    loadData();
  } catch {
    // 错误提示已由 request 拦截器处理
  } finally {
    auditLoading.value = false;
  }
}

onMounted(loadData);
</script>

<template>
  <div class="todoworkflow-page">
    <el-card shadow="never">
      <template #header>待办工作流</template>
      <el-table v-loading="loading" :data="list" stripe border style="width: 100%">
        <el-table-column type="index" label="#" width="55" />
        <el-table-column label="工单标题" min-width="200">
          <template #default="{ row }">
            <el-link type="primary" @click="goDetail(row as TodoRow)">
              {{ (row as TodoRow).workflow_title }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag
              v-if="WORKFLOW_TYPE[(row as TodoRow).workflow_type]"
              :type="WORKFLOW_TYPE[(row as TodoRow).workflow_type].type"
              size="small"
            >
              {{ WORKFLOW_TYPE[(row as TodoRow).workflow_type].label }}
            </el-tag>
            <span v-else>{{ (row as TodoRow).workflow_type }}</span>
          </template>
        </el-table-column>
        <el-table-column label="资源组" prop="group_name" width="130" show-overflow-tooltip />
        <el-table-column label="申请人" prop="create_user_display" width="120" show-overflow-tooltip />
        <el-table-column label="当前审批组" prop="current_audit" width="110" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              v-if="AUDIT_STATUS[(row as TodoRow).current_status]"
              :type="AUDIT_STATUS[(row as TodoRow).current_status].type"
              size="small"
            >
              {{ AUDIT_STATUS[(row as TodoRow).current_status].label }}
            </el-tag>
            <span v-else>{{ (row as TodoRow).current_status }}</span>
          </template>
        </el-table-column>
        <el-table-column label="申请时间" prop="create_time" width="160" />
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="success" @click="openAudit(row as TodoRow, 'pass')">通过</el-button>
            <el-button link type="danger" @click="openAudit(row as TodoRow, 'cancel')">驳回</el-button>
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

    <!-- 审批弹窗 -->
    <el-dialog
      v-model="auditVisible"
      :title="`${auditForm.audit_type === 'pass' ? '通过' : '驳回'} - ${auditForm.workflow_title}`"
      width="560px"
    >
      <el-form label-width="90px">
        <el-form-item label="审核备注">
          <el-input
            v-model="auditForm.audit_remark"
            type="textarea"
            :rows="4"
            placeholder="请填写审核备注"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="auditVisible = false">取消</el-button>
        <el-button type="primary" :loading="auditLoading" @click="onAudit">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.todoworkflow-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
