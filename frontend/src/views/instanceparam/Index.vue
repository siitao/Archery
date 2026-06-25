<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { useInstanceSelect } from "@/composables/useInstanceSelect";
import {
  fetchParamList,
  fetchParamHistory,
  editParam,
  type ParamRow,
} from "@/api/instance_admin";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const { instanceName, instanceGroups, currentInstance, loadInstances } =
  useInstanceSelect();

const activeTab = ref("list");
const list = ref<ParamRow[]>([]);
const loading = ref(false);
const editable = ref(0);
const search = ref("");

// 行内编辑
const editing = ref<ParamRow | null>(null);
const editValue = ref("");

// 历史
const history = ref<ParamRow[]>([]);
const historyTotal = ref(0);
const historyLoading = ref(false);
const historyPage = ref(1);
const historySize = ref(20);

const canEdit = ref(false);

async function loadData() {
  if (!currentInstance.value) {
    list.value = [];
    return;
  }
  loading.value = true;
  try {
    list.value = await fetchParamList({
      instance_id: currentInstance.value.id,
      editable: editable.value,
      search: search.value || undefined,
    });
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

async function loadHistory() {
  if (!currentInstance.value) return;
  historyLoading.value = true;
  try {
    const r = await fetchParamHistory({
      instance_id: currentInstance.value.id,
      limit: historySize.value,
      offset: (historyPage.value - 1) * historySize.value,
    });
    history.value = r.rows;
    historyTotal.value = r.total;
  } catch {
    // 拦截器已提示
  } finally {
    historyLoading.value = false;
  }
}

watch(instanceName, () => {
  loadData();
  if (activeTab.value === "history") loadHistory();
});
watch([editable, search], () => loadData());

function onTabChange(name: string | number) {
  if (String(name) === "history") loadHistory();
}

function canEditParam(row: ParamRow) {
  return canEdit.value && row.editable;
}

function openEdit(row: ParamRow) {
  editing.value = row;
  editValue.value = String(row.runtime_value ?? "");
}

async function saveEdit() {
  if (!editing.value || !currentInstance.value) return;
  try {
    await editParam({
      instance_id: currentInstance.value.id,
      variable_name: editing.value.variable_name,
      runtime_value: editValue.value,
    });
    ElMessage.success("修改成功（仅运行时，需手动持久化到配置文件）");
    editing.value = null;
    loadData();
  } catch {
    // 业务错误已提示
  }
}

onMounted(async () => {
  await loadInstances();
  // 权限：sql.param_edit
  canEdit.value = auth.hasPerm("sql.param_edit");
});
</script>

<template>
  <div class="param-page">
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="实例">
          <el-select v-model="instanceName" filterable placeholder="选择实例" style="width: 240px">
            <el-option-group v-for="grp in instanceGroups" :key="grp.label" :label="grp.label">
              <el-option v-for="i in grp.items" :key="i.id" :label="i.instance_name" :value="i.instance_name" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="筛选">
          <el-select v-model="editable" style="width: 140px">
            <el-option :value="0" label="全部" />
            <el-option :value="1" label="仅可修改" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="search"
            placeholder="参数名搜索"
            clearable
            style="width: 200px"
            @keyup.enter="loadData"
          />
          <el-button type="primary" style="margin-left: 8px" @click="loadData">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <!-- 参数列表（行内编辑） -->
        <el-tab-pane label="参数列表" name="list">
          <el-table v-loading="loading" :data="list" stripe border max-height="600">
            <el-table-column prop="variable_name" label="参数名" min-width="220" show-overflow-tooltip />
            <el-table-column label="运行值" min-width="240">
              <template #default="{ row }">
                <span v-if="editing === row">
                  <el-input v-model="editValue" size="small" style="width: 200px" />
                  <el-button size="small" type="primary" link @click="saveEdit">保存</el-button>
                  <el-button size="small" link @click="editing = null">取消</el-button>
                </span>
                <span v-else>{{ row.runtime_value }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="default_value" label="默认值" min-width="180" show-overflow-tooltip />
            <el-table-column prop="description" label="说明" min-width="240" show-overflow-tooltip />
            <el-table-column label="可改" width="70">
              <template #default="{ row }">
                <el-tag :type="row.editable ? 'success' : 'info'" size="small">
                  {{ row.editable ? "是" : "否" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="90" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="canEditParam(row as ParamRow) && editing !== row"
                  link
                  type="primary"
                  size="small"
                  @click="openEdit(row as ParamRow)"
                >
                  修改
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 修改历史 -->
        <el-tab-pane label="修改历史" name="history">
          <el-table v-loading="historyLoading" :data="history" stripe border max-height="600">
            <el-table-column prop="variable_name" label="参数名" min-width="200" show-overflow-tooltip />
            <el-table-column prop="old_value" label="原值" min-width="160" show-overflow-tooltip />
            <el-table-column prop="new_value" label="新值" min-width="160" show-overflow-tooltip />
            <el-table-column prop="create_user" label="操作人" width="120" show-overflow-tooltip />
            <el-table-column prop="create_time" label="时间" width="160" />
          </el-table>
          <div class="pager">
            <el-pagination
              :total="historyTotal"
              :current-page="historyPage"
              :page-size="historySize"
              :page-sizes="[20, 50, 100]"
              layout="total, sizes, prev, pager, next"
              background
              @current-change="(p: number) => { historyPage = p; loadHistory(); }"
              @size-change="(s: number) => { historySize = s; historyPage = 1; loadHistory(); }"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.param-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}

.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
