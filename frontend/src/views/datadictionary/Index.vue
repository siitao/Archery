<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { useInstanceSelect } from "@/composables/useInstanceSelect";
import { fetchQueryResources } from "@/api/sqlquery";
import {
  fetchDictionaryObjects,
  fetchDictionaryInfo,
  exportDictionary,
  type DictionaryObjectType,
} from "@/api/phase2";

const { instanceName, instanceGroups, currentInstance, loadInstances } =
  useInstanceSelect();

const dbName = ref("");
const dbOptions = ref<string[]>([]);
const activeType = ref<DictionaryObjectType>("table");
const objectName = ref("");
const objects = ref<{ name: string }[]>([]);
const listLoading = ref(false);
const info = ref("");
const infoLoading = ref(false);
const exporting = ref(false);

const objectTypes: { key: DictionaryObjectType; label: string }[] = [
  { key: "table", label: "表" },
  { key: "view", label: "视图" },
  { key: "trigger", label: "触发器" },
  { key: "procedure", label: "存储过程" },
  { key: "function", label: "函数" },
  { key: "event", label: "事件" },
];

async function loadDbs() {
  if (!currentInstance.value) return;
  try {
    dbOptions.value = await fetchQueryResources({
      instance_id: currentInstance.value.id,
      resource_type: "database",
    });
  } catch {
    // 拦截器已提示
  }
}

async function loadObjects() {
  if (!instanceName.value || !dbName.value) {
    objects.value = [];
    return;
  }
  listLoading.value = true;
  objectName.value = "";
  info.value = "";
  try {
    objects.value = await fetchDictionaryObjects({
      instance_name: instanceName.value,
      db_name: dbName.value,
      db_type: currentInstance.value?.db_type,
      object_type: activeType.value,
    });
  } catch {
    // 拦截器已提示
  } finally {
    listLoading.value = false;
  }
}

async function onSelectObject(name: string) {
  if (!name) return;
  infoLoading.value = true;
  try {
    info.value = await fetchDictionaryInfo({
      instance_name: instanceName.value,
      db_name: dbName.value,
      db_type: currentInstance.value?.db_type,
      object_type: activeType.value,
      object_name: name,
    });
  } catch {
    // 拦截器已提示
  } finally {
    infoLoading.value = false;
  }
}

async function onExport() {
  if (!instanceName.value || !dbName.value)
    return ElMessage.warning("请先选择实例和库");
  exporting.value = true;
  try {
    const { data } = await exportDictionary({
      instance_name: instanceName.value,
      db_name: dbName.value,
      db_type: currentInstance.value?.db_type,
    });
    const blob = new Blob([data as unknown as BlobPart], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `data_dictionary_${dbName.value}.html`;
    a.click();
    URL.revokeObjectURL(url);
  } catch {
    // 拦截器已提示
  } finally {
    exporting.value = false;
  }
}

watch(instanceName, () => {
  dbName.value = "";
  objects.value = [];
  info.value = "";
  if (currentInstance.value) loadDbs();
});
watch(dbName, () => loadObjects());
watch(activeType, () => loadObjects());

onMounted(loadInstances);
</script>

<template>
  <div class="dd-page">
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="实例">
          <el-select v-model="instanceName" filterable placeholder="选择实例" style="width: 220px">
            <el-option-group v-for="g in instanceGroups" :key="g.label" :label="g.label">
              <el-option v-for="i in g.items" :key="i.id" :label="i.instance_name" :value="i.instance_name" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="库">
          <el-select v-model="dbName" filterable placeholder="选择库" style="width: 200px">
            <el-option v-for="d in dbOptions" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button :disabled="!dbName" :loading="exporting" @click="onExport">导出字典</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" v-if="dbName">
      <el-tabs v-model="activeType">
        <el-tab-pane v-for="t in objectTypes" :key="t.key" :label="t.label" :name="t.key" />
      </el-tabs>
      <el-row :gutter="12">
        <el-col :span="8">
          <el-table
            v-loading="listLoading"
            :data="objects"
            stripe
            border
            highlight-current-row
            max-height="540"
            @current-change="(r: { name: string } | null) => r && onSelectObject(r.name)"
          >
            <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
          </el-table>
        </el-col>
        <el-col :span="16">
          <el-card v-loading="infoLoading" shadow="never" body-class="info-body">
            <template #header>{{ objectName || "定义" }}</template>
            <pre v-if="info" class="def-text">{{ info }}</pre>
            <el-empty v-else description="选择左侧对象查看定义" />
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.dd-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}

:deep(.info-body) {
  min-height: 400px;
}

.def-text {
  margin: 0;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  font-family: monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 500px;
  overflow: auto;
}
</style>
