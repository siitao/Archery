<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  fetchUsers,
  createUser,
  updateUser,
  deleteUser,
  fetchGroups,
  createGroup,
  updateGroup,
  deleteGroup,
  fetchPermissions,
  type UserRow,
  type AuthGroupRow,
  type PermGroup,
} from "@/api/user";
import { fetchResourceGroups, type ResourceGroupRow } from "@/api/group";

const activeTab = ref("user");
const loading = ref(false);
const list = ref<UserRow[]>([]);
const total = ref(0);
const query = reactive({ username: "", page: 1, size: 15 });

const groups = ref<AuthGroupRow[]>([]);
const permGroups = ref<PermGroup[]>([]);
const resGroups = ref<ResourceGroupRow[]>([]);
const permFilter = ref("");

// 过滤后的权限组（根据搜索关键词）
const filteredPermGroups = computed(() => {
  if (!permFilter.value.trim()) return permGroups.value;
  const filter = permFilter.value.toLowerCase();
  return permGroups.value
    .map((pg) => ({
      ...pg,
      permissions: pg.permissions.filter(
        (p) =>
          p.codename.toLowerCase().includes(filter) ||
          p.name.toLowerCase().includes(filter)
      ),
    }))
    .filter((pg) => pg.permissions.length > 0);
});

// 全选所有权限
function selectAllPerms() {
  groupForm.permissions = permGroups.value.flatMap((pg) =>
    pg.permissions.map((p) => p.id)
  );
}

// 全不选
function deselectAllPerms() {
  groupForm.permissions = [];
}

// 全选某组权限
function selectGroupPerms(pg: PermGroup) {
  const ids = pg.permissions.map((p) => p.id);
  const existing = new Set(groupForm.permissions);
  ids.forEach((id) => existing.add(id));
  groupForm.permissions = Array.from(existing);
}

// 用户权限位（单独的搜索/过滤/全选）
const userPermFilter = ref("");

const filteredUserPermGroups = computed(() => {
  if (!userPermFilter.value.trim()) return permGroups.value;
  const filter = userPermFilter.value.toLowerCase();
  return permGroups.value
    .map((pg) => ({
      ...pg,
      permissions: pg.permissions.filter(
        (p) =>
          p.codename.toLowerCase().includes(filter) ||
          p.name.toLowerCase().includes(filter)
      ),
    }))
    .filter((pg) => pg.permissions.length > 0);
});

function selectAllUserPerms() {
  form.user_permissions = permGroups.value.flatMap((pg) =>
    pg.permissions.map((p) => p.id)
  );
}

function deselectAllUserPerms() {
  form.user_permissions = [];
}

function selectGroupUserPerms(pg: PermGroup) {
  const ids = pg.permissions.map((p) => p.id);
  const existing = new Set(form.user_permissions);
  ids.forEach((id) => existing.add(id));
  form.user_permissions = Array.from(existing);
}

async function loadData() {
  loading.value = true;
  try {
    const { data } = await fetchUsers({
      page: query.page,
      size: query.size,
      username: query.username || undefined,
    });
    list.value = data.results || [];
    total.value = data.count || 0;
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

function onSearch() {
  query.page = 1;
  loadData();
}

// ============ CRUD ============
const dialogVisible = ref(false);
const isEdit = ref(false);
const submitting = ref(false);

const form = reactive({
  id: undefined as number | undefined,
  username: "",
  display: "",
  email: "",
  password: "",
  is_active: true,
  is_staff: false,
  is_superuser: false,
  groups: [] as number[],
  resource_group: [] as number[],
  user_permissions: [] as number[],
});

function resetForm() {
  Object.assign(form, {
    id: undefined,
    username: "",
    display: "",
    email: "",
    password: "",
    is_active: true,
    is_staff: false,
    is_superuser: false,
    groups: [],
    resource_group: [],
    user_permissions: [],
  });
}

function openCreate() {
  isEdit.value = false;
  resetForm();
  dialogVisible.value = true;
}

function openEdit(row: UserRow) {
  isEdit.value = true;
  Object.assign(form, {
    id: row.id,
    username: row.username,
    display: row.display,
    email: row.email || "",
    password: "",
    is_active: row.is_active,
    is_staff: row.is_staff,
    is_superuser: row.is_superuser,
    groups: row.groups || [],
    resource_group: row.resource_group || [],
    user_permissions: row.user_permissions || [],
  });
  dialogVisible.value = true;
}

async function onSubmit() {
  if (!form.username.trim()) return ElMessage.warning("请填写用户名");
  if (!form.display.trim()) return ElMessage.warning("请填写中文名");
  if (!isEdit.value && !form.password) return ElMessage.warning("请设置密码");
  submitting.value = true;
  try {
    const payload: Record<string, unknown> = { ...form };
    // 编辑且密码留空 → 不传（保持原密码）
    if (isEdit.value && !payload.password) delete payload.password;
    if (isEdit.value && form.id) {
      await updateUser(form.id, payload);
      ElMessage.success("已更新");
    } else {
      await createUser(payload);
      ElMessage.success("已新增");
    }
    dialogVisible.value = false;
    loadData();
  } catch {
    // 拦截器已提示
  } finally {
    submitting.value = false;
  }
}

async function onDelete(row: UserRow) {
  try {
    await ElMessageBox.confirm(`确认删除用户「${row.display || row.username}」？`, "提示", {
      type: "warning",
    });
    await deleteUser(row.id);
    ElMessage.success("已删除");
    loadData();
  } catch (e) {
    if (e !== "cancel") {
      // 业务错误已由拦截器提示
    }
  }
}

async function onToggleActive(row: UserRow) {
  const next = !row.is_active;
  try {
    await updateUser(row.id, { is_active: next });
    row.is_active = next;
    ElMessage.success(next ? "已启用" : "已停用");
  } catch {
    // 拦截器已提示
  }
}

// ============ 权限组管理 ============
const groupDialogVisible = ref(false);
const groupIsEdit = ref(false);
const groupSubmitting = ref(false);
const groupForm = reactive({ id: undefined as number | undefined, name: "", permissions: [] as number[] });

function openGroupCreate() {
  groupIsEdit.value = false;
  Object.assign(groupForm, { id: undefined, name: "", permissions: [] });
  groupDialogVisible.value = true;
}

function openGroupEdit(g: AuthGroupRow) {
  groupIsEdit.value = true;
  Object.assign(groupForm, { id: g.id, name: g.name, permissions: g.permissions || [] });
  groupDialogVisible.value = true;
}

async function onGroupSubmit() {
  if (!groupForm.name.trim()) return ElMessage.warning("请填写组名");
  groupSubmitting.value = true;
  try {
    if (groupIsEdit.value && groupForm.id) {
      await updateGroup(groupForm.id, { name: groupForm.name, permissions: groupForm.permissions });
      ElMessage.success("已更新");
    } else {
      await createGroup({ name: groupForm.name, permissions: groupForm.permissions });
      ElMessage.success("已新增");
    }
    groupDialogVisible.value = false;
    groups.value = await fetchGroups();
  } catch {
    // 拦截器已提示
  } finally {
    groupSubmitting.value = false;
  }
}

async function onGroupDelete(g: AuthGroupRow) {
  try {
    await ElMessageBox.confirm(`确认删除权限组「${g.name}」？`, "提示", { type: "warning" });
    await deleteGroup(g.id);
    ElMessage.success("已删除");
    groups.value = await fetchGroups();
  } catch (e) {
    if (e !== "cancel") {
      // 业务错误已由拦截器提示
    }
  }
}

function onTabChange(name: string | number) {
  if (String(name) === "group" && groups.value.length === 0) {
    fetchGroups().then((g) => (groups.value = g)).catch(() => {});
  }
}

onMounted(async () => {
  loadData();
  try {
    const [g, p, r] = await Promise.all([
      fetchGroups(),
      fetchPermissions(),
      fetchResourceGroups({ size: 1000 }),
    ]);
    groups.value = g;
    permGroups.value = p;
    resGroups.value = r.data.results || [];
  } catch {
    // 拦截器已提示
  }
});
</script>

<template>
  <div class="user-page">
    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <el-tab-pane label="用户" name="user">
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="用户名">
          <el-input
            v-model="query.username"
            placeholder="精确匹配"
            clearable
            @keyup.enter="onSearch"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onSearch">查询</el-button>
          <el-button type="success" @click="openCreate">新增用户</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="list" stripe border>
        <el-table-column type="index" label="#" width="55" />
        <el-table-column prop="username" label="用户名" width="130" />
        <el-table-column prop="display" label="中文名" width="130" />
        <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip />
        <el-table-column label="超管" width="70">
          <template #default="{ row }">
            <el-tag v-if="(row as UserRow).is_superuser" type="danger" size="small">是</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-switch
              :model-value="(row as UserRow).is_active"
              @change="onToggleActive(row as UserRow)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="date_joined" label="加入时间" width="160" />
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row as UserRow)">编辑</el-button>
            <el-button link type="danger" @click="onDelete(row as UserRow)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          :current-page="query.page"
          :page-size="query.size"
          :page-sizes="[15, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="(p: number) => { query.page = p; loadData(); }"
          @size-change="(s: number) => { query.size = s; query.page = 1; loadData(); }"
        />
      </div>
    </el-card>

    <!-- 用户表单弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑用户' : '新增用户'"
      width="780px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="90px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="用户名" required>
              <el-input v-model="form.username" :disabled="isEdit" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="中文名" required>
              <el-input v-model="form.display" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱">
              <el-input v-model="form.email" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="密码" :required="!isEdit">
              <el-input
                v-model="form.password"
                type="password"
                show-password
                :placeholder="isEdit ? '留空表示不修改' : ''"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="角色标志">
              <el-checkbox v-model="form.is_active">启用</el-checkbox>
              <el-checkbox v-model="form.is_staff">可登录后台</el-checkbox>
              <el-checkbox v-model="form.is_superuser">超级管理员</el-checkbox>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="权限组">
              <el-select v-model="form.groups" multiple filterable placeholder="可多选" style="width: 100%">
                <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="资源组">
              <el-select v-model="form.resource_group" multiple filterable placeholder="可多选" style="width: 100%">
                <el-option
                  v-for="g in resGroups"
                  :key="g.group_id"
                  :label="g.group_name"
                  :value="g.group_id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="权限位">
              <div class="perm-selector">
                <el-input
                  v-model="userPermFilter"
                  placeholder="搜索权限名称..."
                  clearable
                  style="margin-bottom: 12px"
                />
                <div class="perm-actions">
                  <el-button size="small" @click="selectAllUserPerms">全选</el-button>
                  <el-button size="small" @click="deselectAllUserPerms">全不选</el-button>
                </div>
                <el-collapse>
                  <el-collapse-item
                    v-for="pg in filteredUserPermGroups"
                    :key="pg.model"
                    :name="pg.model"
                  >
                    <template #title>
                      <div class="perm-group-header">
                        <span>{{ pg.label }}（{{ pg.permissions.length }} 个权限）</span>
                        <el-button
                          size="small"
                          type="primary"
                          link
                          @click.stop="selectGroupUserPerms(pg)"
                        >
                          全选此组
                        </el-button>
                      </div>
                    </template>
                    <el-checkbox-group v-model="form.user_permissions" class="perm-grid">
                      <el-checkbox
                        v-for="p in pg.permissions"
                        :key="p.id"
                        :label="p.codename"
                        :value="p.id"
                      >
                        <el-tooltip :content="p.name" placement="top">
                          <span>{{ p.name }}</span>
                        </el-tooltip>
                      </el-checkbox>
                    </el-checkbox-group>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="onSubmit">
          {{ isEdit ? "保存" : "新增" }}
        </el-button>
      </template>
    </el-dialog>
      </el-tab-pane>

      <!-- 权限组 -->
      <el-tab-pane label="权限组" name="group">
        <el-card shadow="never" class="filter-card">
          <el-form :inline="true" @submit.prevent>
            <el-form-item>
              <el-button type="success" @click="openGroupCreate">新增权限组</el-button>
            </el-form-item>
          </el-form>
        </el-card>
        <el-card shadow="never">
          <el-table :data="groups" stripe border>
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="name" label="组名" min-width="160" />
            <el-table-column label="权限数" width="100">
              <template #default="{ row }">
                {{ (row as AuthGroupRow).permissions?.length || 0 }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="130" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openGroupEdit(row as AuthGroupRow)">编辑</el-button>
                <el-button link type="danger" @click="onGroupDelete(row as AuthGroupRow)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 权限组表单弹窗 -->
    <el-dialog
      v-model="groupDialogVisible"
      :title="groupIsEdit ? '编辑权限组' : '新增权限组'"
      width="720px"
      :close-on-click-modal="false"
    >
      <el-form :model="groupForm" label-width="70px">
        <el-form-item label="组名" required>
          <el-input v-model="groupForm.name" />
        </el-form-item>
        <el-form-item label="权限">
          <div class="perm-selector">
            <el-input
              v-model="permFilter"
              placeholder="搜索权限名称..."
              clearable
              style="margin-bottom: 12px"
            />
            <div class="perm-actions">
              <el-button size="small" @click="selectAllPerms">全选</el-button>
              <el-button size="small" @click="deselectAllPerms">全不选</el-button>
            </div>
            <el-collapse>
              <el-collapse-item
                v-for="pg in filteredPermGroups"
                :key="pg.model"
                :name="pg.model"
              >
                <template #title>
                  <div class="perm-group-header">
                    <span>{{ pg.label }}（{{ pg.permissions.length }} 个权限）</span>
                    <el-button
                      size="small"
                      type="primary"
                      link
                      @click.stop="selectGroupPerms(pg)"
                    >
                      全选此组
                    </el-button>
                  </div>
                </template>
                <el-checkbox-group v-model="groupForm.permissions" class="perm-grid">
                  <el-checkbox
                    v-for="p in pg.permissions"
                    :key="p.id"
                    :label="p.codename"
                    :value="p.id"
                  >
                    <el-tooltip :content="p.codename" placement="top">
                      <span>{{ p.name }}</span>
                    </el-tooltip>
                  </el-checkbox>
                </el-checkbox-group>
              </el-collapse-item>
            </el-collapse>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="groupDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="groupSubmitting" @click="onGroupSubmit">
          {{ groupIsEdit ? "保存" : "新增" }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.user-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.perm-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 4px 12px;
}

.perm-selector {
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  padding: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.perm-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.perm-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 12px;
}
</style>
