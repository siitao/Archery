<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { fetchInstances, type InstanceRow } from "@/api/instance";
import { compareParam, type ParamCompareResult } from "@/api/instance_admin";

const instances = ref<InstanceRow[]>([]);
const loading = ref(false);

// 筛选
const dbType = ref("");
const instanceId1 = ref<number | undefined>(undefined);
const instanceId2 = ref<number | undefined>(undefined);
const diffOnly = ref(true);

const result = ref<ParamCompareResult | null>(null);

/** 按 db_type 过滤的实例（仅 mysql/goinception 支持） */
const supportedTypes = ["mysql", "goinception"];
const filteredInstances = computed(() =>
  instances.value.filter((i) => !dbType.value || i.db_type === dbType.value)
);

const displayRows = computed(() => {
  if (!result.value) return [];
  const rows = result.value.rows || [];
  return diffOnly.value
    ? rows.filter(
        (r) =>
          (r as { diff_type?: string }).diff_type &&
          (r as { diff_type?: string }).diff_type !== "一致"
      )
    : rows;
});

function diffTypeTag(t?: string) {
  switch (t) {
    case "值不同":
      return "danger";
    case "仅源存在":
    case "仅目标存在":
      return "warning";
    default:
      return "success";
  }
}

async function onCompare() {
  if (!instanceId1.value || !instanceId2.value)
    return ElMessage.warning("请选择两个实例");
  if (instanceId1.value === instanceId2.value)
    return ElMessage.warning("请选择不同的实例");
  loading.value = true;
  result.value = null;
  try {
    result.value = await compareParam({
      instance_id1: instanceId1.value,
      instance_id2: instanceId2.value,
      diff_only: diffOnly.value,
    });
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  try {
    const { data } = await fetchInstances({ size: 1000 });
    instances.value = (data.results || []).filter((i) =>
      supportedTypes.includes(i.db_type)
    );
  } catch {
    // 拦截器已提示
  }
});
</script>

<template>
  <div v-loading="loading" class="compare-page">
    <el-row :gutter="12">
      <!-- 左：筛选 -->
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>选择实例</template>
          <el-form label-width="90px" size="default">
            <el-form-item label="数据库类型">
              <el-select v-model="dbType" placeholder="全部" clearable style="width: 100%">
                <el-option v-for="t in supportedTypes" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
            <el-form-item label="源实例">
              <el-select
                v-model="instanceId1"
                filterable
                placeholder="选择源实例"
                style="width: 100%"
              >
                <el-option
                  v-for="i in filteredInstances"
                  :key="i.id"
                  :label="i.instance_name"
                  :value="i.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="目标实例">
              <el-select
                v-model="instanceId2"
                filterable
                placeholder="选择目标实例"
                style="width: 100%"
              >
                <el-option
                  v-for="i in filteredInstances"
                  :key="i.id"
                  :label="i.instance_name"
                  :value="i.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="仅差异">
              <el-switch v-model="diffOnly" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="onCompare">开始对比</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 右：结果 -->
      <el-col :span="16">
        <template v-if="result">
          <el-row :gutter="12" class="stat-row">
            <el-col :span="8">
              <el-card shadow="never" body-class="stat-card stat-success">
                <div class="stat-num">{{ result.same_count }}</div>
                <div class="stat-label">一致</div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="never" body-class="stat-card stat-danger">
                <div class="stat-num">{{ result.diff_count }}</div>
                <div class="stat-label">差异</div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="never" body-class="stat-card">
                <div class="stat-num">{{ result.total }}</div>
                <div class="stat-label">总参数</div>
              </el-card>
            </el-col>
          </el-row>

          <el-card shadow="never" class="result-card">
            <template #header>
              {{ result.instance1_name }} ↔ {{ result.instance2_name }}
            </template>
            <el-table :data="displayRows" stripe border max-height="540">
              <el-table-column type="expand">
                <template #default="{ row }">
                  <div class="expand-desc">
                    {{ (row as { description?: string }).description || "（无说明）" }}
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="variable_name" label="参数名" min-width="220" show-overflow-tooltip />
              <el-table-column label="源值" min-width="180" show-overflow-tooltip>
                <template #default="{ row }">{{ (row as { instance1_value?: string }).instance1_value }}</template>
              </el-table-column>
              <el-table-column label="目标值" min-width="180" show-overflow-tooltip>
                <template #default="{ row }">{{ (row as { instance2_value?: string }).instance2_value }}</template>
              </el-table-column>
              <el-table-column label="差异" width="110">
                <template #default="{ row }">
                  <el-tag :type="diffTypeTag((row as { diff_type?: string }).diff_type)" size="small">
                    {{ (row as { diff_type?: string }).diff_type || "一致" }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </template>
        <el-empty v-else description="选择两个同类型实例后开始对比" />
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.compare-page {
  min-height: 400px;
}

.stat-row {
  margin-bottom: 12px;
}

.stat-card {
  text-align: center;

  .stat-num {
    font-size: 28px;
    font-weight: 700;
  }

  .stat-label {
    color: var(--el-text-color-secondary);
    font-size: 13px;
  }

  &.stat-success .stat-num {
    color: var(--el-color-success);
  }

  &.stat-danger .stat-num {
    color: var(--el-color-danger);
  }
}

.result-card {
  margin-top: 0;
}

.expand-desc {
  padding: 8px 16px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
