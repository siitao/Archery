<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { useAuthStore } from "@/stores/auth";
import {
  fetchResourceGroup,
  fetchRelations,
  fetchUnassociated,
  addRelation,
  removeRelation,
  type ResourceGroupRow,
  type RelationRow,
} from "@/api/resourcegroup";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const isSuperuser = auth.isSuperuser;

const groupId = Number(route.params.id);
const group = ref<ResourceGroupRow | null>(null);

const activeTab = ref<"1" | "0">("1"); // 1=实例 0=用户
const objectType = computed<0 | 1>(() => (activeTab.value === "1" ? 1 : 0));
const list = ref<RelationRow[]>([]);
const loading = ref(false);

// 新增关联 dialog
const addDialog = ref(false);
const addOptions = ref<{ object_id: number; object_name: string }[]>([]);
const addSelected = ref<string[]>([]); // "id,name"
const addLoading = ref(false);

const typeLabel = computed(() => (activeTab.value === "1" ? "实例" : "用户"));

async function loadGroup() {
  try {
    const { data } = await fetchResourceGroup(groupId);
    group.value = data;
  } catch {
    // 拦截器已提示
  }
}

async function loadRelations() {
  loading.value = true;
  try {
    const r = await fetchRelations({
      group_id: groupId,
      type: objectType.value,
      limit: 1000,
    });
    list.value = r.rows;
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

function onTabChange() {
  loadRelations();
}

async function openAdd() {
  addSelected.value = [];
  addDialog.value = true;
  await loadUnassociated();
}

async function loadUnassociated() {
  addLoading.value = true;
  try {
    addOptions.value = await fetchUnassociated({
      group_id: groupId,
      object_type: objectType.value,
    });
  } catch {
    // 拦截器已提示
  } finally {
    addLoading.value = false;
  }
}

async function onAddSubmit() {
  if (!addSelected.value.length) return ElMessage.warning("请选择对象");
  try {
    await addRelation({
      group_id: groupId,
      object_type: objectType.value,
      object_info: addSelected.value,
    });
    ElMessage.success("已添加");
    addDialog.value = false;
    loadRelations();
  } catch {
    // 业务错误已提示
  }
}

async function onRemove(row: RelationRow) {
  try {
    await ElMessageBox.confirm(
      `确认移除${typeLabel.value}「${row.object_name}」？`,
      "提示",
      { type: "warning" }
    );
    await removeRelation({
      group_id: groupId,
      object_type: objectType.value,
      object_info: [`${row.object_id},${row.object_name}`],
    });
    ElMessage.success("已移除");
    loadRelations();
  } catch (e) {
    if (e !== "cancel") {
      // 业务错误已提示
    }
  }
}

onMounted(() => {
  loadGroup();
  loadRelations();
});
</script>

<template>
  <div class="relations-page">
    <el-card shadow="never" class="header-card">
      <div class="header">
        <el-button link @click="router.push({ name: 'resourcegroup' })">← 返回</el-button>
        <span class="title">资源组：{{ group?.group_name || `#${groupId}` }}</span>
        <div class="spacer" />
        <el-button v-if="isSuperuser" type="primary" @click="openAdd">新增关联</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <el-tab-pane label="关联实例" name="1" />
        <el-tab-pane label="关联用户" name="0" />
      </el-tabs>
      <el-table v-loading="loading" :data="list" stripe border style="width: 100%">
        <el-table-column type="index" label="#" width="55" />
        <el-table-column prop="object_name" :label="typeLabel + ' 名称'" min-width="200" show-overflow-tooltip />
        <el-table-column prop="object_id" :label="typeLabel + ' ID'" width="100" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="isSuperuser"
              link
              type="danger"
              size="small"
              @click="onRemove(row as RelationRow)"
            >
              移除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!list.length && !loading" description="暂无关联" />
    </el-card>

    <!-- 新增关联 -->
    <el-dialog v-model="addDialog" :title="`新增关联${typeLabel}`" width="480px">
      <el-select
        v-model="addSelected"
        v-loading="addLoading"
        multiple
        filterable
        placeholder="选择要关联的对象"
        style="width: 100%"
      >
        <el-option
          v-for="o in addOptions"
          :key="o.object_id"
          :label="o.object_name"
          :value="`${o.object_id},${o.object_name}`"
        />
      </el-select>
      <template #footer>
        <el-button @click="addDialog = false">取消</el-button>
        <el-button type="primary" @click="onAddSubmit">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.relations-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header {
  display: flex;
  align-items: center;
  gap: 12px;

  .title {
    font-size: 16px;
    font-weight: 600;
  }

  .spacer {
    flex: 1;
  }
}
</style>
