<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  fetchApplyDetail,
  auditApply,
  PRIV_TYPE_LABEL,
  APPLY_STATUS,
  type ApplyDetail,
} from "@/api/querypriv";

const route = useRoute();
const router = useRouter();
const applyId = Number(route.params.id);

const loading = ref(false);
const detail = ref<ApplyDetail | null>(null);
const auditing = ref(false);

const auditForm = reactive({ audit_remark: "" });

async function loadDetail() {
  loading.value = true;
  try {
    detail.value = await fetchApplyDetail(applyId);
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

async function doAudit(status: 1 | 2) {
  try {
    auditing.value = true;
    await auditApply({
      apply_id: applyId,
      audit_status: status,
      audit_remark: auditForm.audit_remark,
    });
    ElMessage.success(status === 1 ? "已通过" : "已驳回");
    auditForm.audit_remark = "";
    loadDetail();
  } catch {
    // 拦截器已提示
  } finally {
    auditing.value = false;
  }
}

onMounted(loadDetail);
</script>

<template>
  <div v-loading="loading" class="detail-page">
    <el-page-header @back="router.back()">
      <template #content>
        <span class="title">{{ detail?.apply.title }}</span>
      </template>
    </el-page-header>

    <template v-if="detail">
      <!-- 审批流 -->
      <el-card shadow="never">
        <template #header>审批流</template>
        <el-steps :active="detail.review_info.findIndex((n) => n.is_current_node)" finish-status="success" align-center>
          <el-step
            v-for="(node, idx) in detail.review_info"
            :key="idx"
            :title="node.is_auto_pass ? '自动通过' : node.group_name"
            :status="node.is_current_node ? 'process' : node.is_passed_node ? 'success' : 'wait'"
          />
        </el-steps>
        <div v-if="detail.current_reviewers.length" class="reviewers">
          当前审核人：{{ detail.current_reviewers.map((r) => r.display).join("、") }}
        </div>
        <div v-if="detail.last_operation_info" class="last-op">
          最近操作：{{ detail.last_operation_info }}
        </div>
      </el-card>

      <!-- 其他信息 -->
      <el-card shadow="never">
        <template #header>其他信息</template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="申请人">{{ detail.apply.user_display }}</el-descriptions-item>
          <el-descriptions-item label="实例">{{ detail.apply.instance_name }}</el-descriptions-item>
          <el-descriptions-item label="权限级别">{{ PRIV_TYPE_LABEL[detail.apply.priv_type] }}</el-descriptions-item>
          <el-descriptions-item label="数据库">
            {{ detail.apply.priv_type === 2 ? detail.apply.db_list : detail.apply.db_list }}
          </el-descriptions-item>
          <el-descriptions-item label="结果集">{{ detail.apply.limit_num }}</el-descriptions-item>
          <el-descriptions-item label="有效时间">{{ detail.apply.valid_date }}</el-descriptions-item>
          <el-descriptions-item label="申请时间">{{ detail.apply.create_time }}</el-descriptions-item>
          <el-descriptions-item label="当前状态">
            <el-tag v-if="APPLY_STATUS[detail.apply.status]" :type="APPLY_STATUS[detail.apply.status].type" size="small">
              {{ APPLY_STATUS[detail.apply.status].label }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="组">{{ detail.apply.group_name }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 审核操作 -->
      <el-card v-if="detail.is_can_review && detail.apply.status === 0" shadow="never">
        <template #header>审核</template>
        <el-input
          v-model="auditForm.audit_remark"
          type="textarea"
          :rows="2"
          placeholder="审核备注（可选）"
          style="margin-bottom: 12px"
        />
        <el-button type="success" :loading="auditing" @click="doAudit(1)">通过</el-button>
        <el-button type="danger" :loading="auditing" @click="doAudit(2)">驳回</el-button>
      </el-card>

      <!-- 操作日志 -->
      <el-card shadow="never">
        <template #header>操作日志</template>
        <el-table :data="detail.logs" stripe border>
          <el-table-column label="操作" prop="operation_type_desc" width="120" />
          <el-table-column label="操作人" prop="operator_display" width="120" />
          <el-table-column label="操作时间" prop="operation_time" width="160" />
          <el-table-column label="操作信息" prop="operation_info" show-overflow-tooltip />
        </el-table>
      </el-card>
    </template>
  </div>
</template>

<style scoped lang="scss">
.detail-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.title {
  font-weight: 600;
}

.reviewers,
.last-op {
  margin-top: 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
