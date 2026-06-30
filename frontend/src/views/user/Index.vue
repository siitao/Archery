<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  fetchUsers,
  createUser,
  updateUser,
  deleteUser,
  fetchGroups,
  fetchPermissions,
  type UserRow,
  type AuthGroupRow,
  type PermGroup,
} from "@/api/user";
import { fetchResourceGroups, type ResourceGroupRow } from "@/api/group";

const loading = ref(false);
const list = ref<UserRow[]>([]);
const total = ref(0);
const query = reactive({ username: "", page: 1, size: 15 });

const groups = ref<AuthGroupRow[]>([]);
const permGroups = ref<PermGroup[]>([]);
const resGroups = ref<ResourceGroupRow[]>([]);

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
              <el-collapse>
                <el-collapse-item
                  v-for="pg in permGroups"
                  :key="pg.model"
                  :title="`${pg.label}（${pg.permissions.length}）`"
                >
                  <el-checkbox-group v-model="form.user_permissions" class="perm-grid">
                    <el-checkbox
                      v-for="p in pg.permissions"
                      :key="p.id"
                      :label="p.codename"
                      :value="p.id"
                    >
                      {{ p.codename }}
                    </el-checkbox>
                  </el-checkbox-group>
                </el-collapse-item>
              </el-collapse>
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
</style>
