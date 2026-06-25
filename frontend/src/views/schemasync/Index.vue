<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { useInstanceSelect } from "@/composables/useInstanceSelect";
import { fetchQueryResources } from "@/api/sqlquery";
import { schemaSync, type SchemaSyncResult } from "@/api/phase2";

const { instanceName, instanceGroups, currentInstance, loadInstances } =
  useInstanceSelect();

const dbName = ref("");
const dbOptions = ref<string[]>([]);
const targetInstanceName = ref("");
const targetDbName = ref("");
const syncAutoInc = ref(false);
const syncComments = ref(false);
const loading = ref(false);
const result = ref<SchemaSyncResult | null>(null);

function copyText(text: string) {
  if (!text) return;
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(() => ElMessage.success("已复制"));
  } else {
    ElMessage.warning("浏览器不支持复制");
  }
}

async function loadDbs(target = false) {
  const inst = target
    ? instanceGroups.value.flatMap((g) => g.items).find((i) => i.instance_name === (target ? targetInstanceName.value : instanceName.value))
    : currentInstance.value;
  if (!inst) return;
  try {
    dbOptions.value = await fetchQueryResources({
      instance_id: inst.id,
      resource_type: "database",
    });
  } catch {
    // 拦截器已提示
  }
}

watch(instanceName, () => {
  dbName.value = "";
  dbOptions.value = [];
  if (currentInstance.value) loadDbs();
});

watch(targetInstanceName, () => {
  targetDbName.value = "";
});

async function onCompare() {
  if (!instanceName.value || !dbName.value)
    return ElMessage.warning("请选择源实例和库");
  if (!targetInstanceName.value || !targetDbName.value)
    return ElMessage.warning("请选择目标实例和库");
  loading.value = true;
  result.value = null;
  try {
    result.value = await schemaSync({
      instance_name: instanceName.value,
      db_name: dbName.value,
      target_instance_name: targetInstanceName.value,
      target_db_name: targetDbName.value,
      sync_auto_inc: syncAutoInc.value,
      sync_comments: syncComments.value,
    });
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

onMounted(loadInstances);
</script>

<template>
  <div v-loading="loading" class="schemasync-page">
    <el-card shadow="never">
      <template #header>SchemaSync 结构对比</template>
      <el-form label-width="100px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="源实例">
              <el-select v-model="instanceName" filterable placeholder="源实例" style="width: 100%">
                <el-option-group v-for="g in instanceGroups" :key="g.label" :label="g.label">
                  <el-option v-for="i in g.items" :key="i.id" :label="i.instance_name" :value="i.instance_name" />
                </el-option-group>
              </el-select>
            </el-form-item>
            <el-form-item label="源库">
              <el-select v-model="dbName" filterable placeholder="源库" style="width: 100%">
                <el-option v-for="d in dbOptions" :key="d" :label="d" :value="d" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="目标实例">
              <el-select v-model="targetInstanceName" filterable placeholder="目标实例" style="width: 100%">
                <el-option-group v-for="g in instanceGroups" :key="g.label" :label="g.label">
                  <el-option v-for="i in g.items" :key="i.id" :label="i.instance_name" :value="i.instance_name" />
                </el-option-group>
              </el-select>
            </el-form-item>
            <el-form-item label="目标库">
              <el-input v-model="targetDbName" placeholder="目标库名" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="选项">
          <el-checkbox v-model="syncAutoInc">同步自增列</el-checkbox>
          <el-checkbox v-model="syncComments">同步注释</el-checkbox>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onCompare">开始对比</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <template v-if="result">
      <el-card shadow="never">
        <template #header>
          对比结果（diff）
          <el-button link type="primary" size="small" @click="copyText(result!.diff_stdout)">
            复制
          </el-button>
        </template>
        <pre class="sql-text">{{ result.diff_stdout || "（无差异）" }}</pre>
      </el-card>
      <el-card shadow="never">
        <template #header>
          Patch SQL（变更脚本）
          <el-button link type="primary" size="small" @click="copyText(result!.patch_stdout)">
            复制
          </el-button>
        </template>
        <pre class="sql-text">{{ result.patch_stdout || "（无）" }}</pre>
      </el-card>
      <el-card shadow="never">
        <template #header>Revert SQL（回滚脚本）</template>
        <pre class="sql-text">{{ result.revert_stdout || "（无）" }}</pre>
      </el-card>
    </template>
  </div>
</template>

<style scoped lang="scss">
.schemasync-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sql-text {
  margin: 0;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  font-family: monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 320px;
  overflow: auto;
}
</style>
