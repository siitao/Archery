<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { useInstanceSelect } from "@/composables/useInstanceSelect";
import {
  fetchDatabases,
  createDatabase,
  editDatabase,
  type DatabaseRow,
} from "@/api/instance_admin";
import { fetchCurrentUser, type CurrentUser } from "@/api/user";

const { instanceName, instanceGroups, currentInstance, loadInstances } =
  useInstanceSelect();

const list = ref<DatabaseRow[]>([]);
const loading = ref(false);
const savedOnly = ref(0);

// 创建/编辑 dialog
const dialogVisible = ref(false);
const dialogMode = ref<"create" | "edit">("create");
const form = ref({ db_name: "", owner: "", remark: "" });

const canManage = ref(false);

async function loadCanManage() {
  try {
    const { data } = await fetchCurrentUser();
    // 有菜单权限即视为可管理（旧版 create/edit 都只校验 sql.menu_database）
    canManage.value = true;
    return data as CurrentUser;
  } catch {
    canManage.value = false;
    return null;
  }
}

async function loadData() {
  if (!currentInstance.value) {
    list.value = [];
    return;
  }
  loading.value = true;
  try {
    list.value = await fetchDatabases(currentInstance.value.id, savedOnly.value);
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

watch(instanceName, () => loadData());
watch(savedOnly, () => loadData());

function openCreate() {
  dialogMode.value = "create";
  form.value = { db_name: "", owner: "", remark: "" };
  dialogVisible.value = true;
}

function openEdit(row: DatabaseRow) {
  dialogMode.value = "edit";
  form.value = {
    db_name: String(row.db_name || ""),
    owner: String(row.owner || ""),
    remark: String(row.remark || ""),
  };
  dialogVisible.value = true;
}

async function onSubmit() {
  if (!currentInstance.value) return;
  if (!form.value.db_name.trim()) return ElMessage.warning("请输入数据库名");
  try {
    if (dialogMode.value === "create") {
      await createDatabase({
        instance_id: currentInstance.value.id,
        db_name: form.value.db_name,
        owner: form.value.owner,
        remark: form.value.remark,
      });
      ElMessage.success("创建成功");
    } else {
      await editDatabase({
        instance_id: currentInstance.value.id,
        db_name: form.value.db_name,
        owner: form.value.owner,
        remark: form.value.remark,
      });
      ElMessage.success("保存成功");
    }
    dialogVisible.value = false;
    loadData();
  } catch {
    // 业务错误已提示
  }
}

onMounted(() => {
  loadInstances();
  loadCanManage();
});
</script>

<template>
  <div class="database-page">
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="实例">
          <el-select
            v-model="instanceName"
            filterable
            placeholder="选择实例"
            style="width: 240px"
          >
            <el-option-group
              v-for="grp in instanceGroups"
              :key="grp.label"
              :label="grp.label"
            >
              <el-option
                v-for="i in grp.items"
                :key="i.id"
                :label="i.instance_name"
                :value="i.instance_name"
              />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="过滤">
          <el-select v-model="savedOnly" style="width: 140px">
            <el-option :value="0" label="全部" />
            <el-option :value="1" label="仅已录入" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button
            v-if="canManage"
            type="primary"
            :disabled="!currentInstance"
            @click="openCreate"
          >
            创建数据库
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="list" stripe border style="width: 100%">
        <el-table-column type="index" label="#" width="55" />
        <el-table-column prop="db_name" label="数据库名" min-width="180" show-overflow-tooltip />
        <el-table-column prop="owner" label="负责人" width="140" show-overflow-tooltip />
        <el-table-column prop="remark" label="备注" min-width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="canManage"
              link
              type="primary"
              size="small"
              @click="openEdit(row as DatabaseRow)"
            >
              编辑
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!list.length && !loading" description="选择实例后展示数据库列表" />
    </el-card>

    <!-- 创建/编辑 dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '创建数据库' : '编辑数据库'"
      width="460px"
    >
      <el-form label-width="90px">
        <el-form-item label="数据库名" required>
          <el-input
            v-model="form.db_name"
            :disabled="dialogMode === 'edit'"
            placeholder="数据库名"
          />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="form.owner" placeholder="负责人用户名" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="onSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.database-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}
</style>
