<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  fetchArchiveDetail,
  archiveAudit,
  ARCHIVE_MODE,
  ARCHIVE_STATUS,
  type ArchiveDetail as ArchiveDetailData,
} from "@/api/archiver";

const route = useRoute();
const router = useRouter();
const archiveId = Number(route.params.id);

const loading = ref(false);
const detail = ref<ArchiveDetailData | null>(null);
const auditing = ref(false);
const auditForm = reactive({ audit_remark: "" });

async function loadDetail() {
  loading.value = true;
  try {
    detail.value = await fetchArchiveDetail(archiveId);
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

async function doAudit(status: 1 | 2) {
  try {
    auditing.value = true;
    await archiveAudit({
      archive_id: archiveId,
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
        <span class="title">{{ detail?.archive.title }}</span>
      </template>
    </el-page-header>

    <template v-if="detail">
      <!-- 审批流 -->
      <el-card shadow="never">
        <template #header>审批流</template>
        <el-steps
          :active="detail.review_info.findIndex((n) => n.is_current_node)"
          finish-status="success"
          align-center
        >
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

      <!-- 归档配置 -->
      <el-card shadow="never">
        <template #header>归档配置</template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="申请人">{{ detail.archive.user_display }}</el-descriptions-item>
          <el-descriptions-item label="资源组">{{ detail.archive.group_name }}</el-descriptions-item>
          <el-descriptions-item label="归档模式">{{ ARCHIVE_MODE[detail.archive.mode] }}</el-descriptions-item>
          <el-descriptions-item label="源实例">{{ detail.archive.src_instance_name }}</el-descriptions-item>
          <el-descriptions-item label="源表" :span="2">
            {{ detail.archive.src_db_name }}.{{ detail.archive.src_table_name }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.archive.mode === 'dest'" label="目标实例">
            {{ detail.archive.dest_instance_name }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.archive.mode === 'dest'" label="目标表" :span="2">
            {{ detail.archive.dest_db_name }}.{{ detail.archive.dest_table_name }}
          </el-descriptions-item>
          <el-descriptions-item label="保留源数据">{{ detail.archive.no_delete ? "是" : "否" }}</el-descriptions-item>
          <el-descriptions-item label="休眠秒数">{{ detail.archive.sleep }}</el-descriptions-item>
          <el-descriptions-item label="当前状态">
            <el-tag v-if="ARCHIVE_STATUS[detail.archive.status]" :type="ARCHIVE_STATUS[detail.archive.status].type" size="small">
              {{ ARCHIVE_STATUS[detail.archive.status].label }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="归档条件" :span="3">
            <code>{{ detail.archive.condition }}</code>
          </el-descriptions-item>
          <el-descriptions-item label="申请时间" :span="3">{{ detail.archive.create_time }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 审核 -->
      <el-card v-if="detail.can_review && detail.archive.status === 0" shadow="never">
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

      <!-- 审核日志 -->
      <el-card shadow="never">
        <template #header>审核日志</template>
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
