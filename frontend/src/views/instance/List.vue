<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { Search, Refresh } from "@element-plus/icons-vue";
import { fetchInstances, type InstanceRow } from "@/api/instance";

const loading = ref(false);
const list = ref<InstanceRow[]>([]);
const total = ref(0);

const query = reactive({
  instance_name: "",
  db_type: "",
  page: 1,
  size: 15,
});

// 主要数据库类型（与 settings.ENABLED_ENGINES 对齐）
const dbTypes = [
  "mysql",
  "mariadb",
  "mssql",
  "redis",
  "pgsql",
  "oracle",
  "mongo",
  "clickhouse",
  "phoenix",
  "odps",
  "cassandra",
  "doris",
  "elasticsearch",
  "opensearch",
  "memcached",
  "tdengine",
];

const typeMap: Record<string, string> = { master: "主库", slave: "从库" };

async function loadData() {
  loading.value = true;
  try {
    const { data } = await fetchInstances({
      page: query.page,
      size: query.size,
      instance_name__icontains: query.instance_name || undefined,
      db_type: query.db_type || undefined,
    });
    list.value = data.results || [];
    total.value = data.count || 0;
  } catch {
    // 错误提示已由 request 拦截器处理
  } finally {
    loading.value = false;
  }
}

function onSearch() {
  query.page = 1;
  loadData();
}

function onReset() {
  query.instance_name = "";
  query.db_type = "";
  query.page = 1;
  loadData();
}

function onPageChange(p: number) {
  query.page = p;
  loadData();
}

function onSizeChange(s: number) {
  query.size = s;
  query.page = 1;
  loadData();
}

onMounted(loadData);
</script>

<template>
  <div class="instance-page">
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="query" @submit.prevent>
        <el-form-item label="实例名称">
          <el-input
            v-model="query.instance_name"
            placeholder="支持模糊匹配"
            clearable
            @keyup.enter="onSearch"
          />
        </el-form-item>
        <el-form-item label="数据库类型">
          <el-select v-model="query.db_type" placeholder="全部" clearable style="width: 160px">
            <el-option v-for="t in dbTypes" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="onSearch">查询</el-button>
          <el-button :icon="Refresh" @click="onReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="list" stripe border style="width: 100%">
        <el-table-column type="index" label="#" width="55" />
        <el-table-column prop="instance_name" label="实例名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="db_type" label="数据库类型" width="130" />
        <el-table-column label="角色" width="80">
          <template #default="{ row }">
            {{ typeMap[row.type as string] || row.type }}
          </template>
        </el-table-column>
        <el-table-column prop="host" label="主机" min-width="160" show-overflow-tooltip />
        <el-table-column prop="port" label="端口" width="90" />
        <el-table-column prop="user" label="用户" width="120" show-overflow-tooltip />
        <el-table-column prop="db_name" label="数据库" min-width="120" show-overflow-tooltip />
      </el-table>

      <div class="pager">
        <el-pagination
          :current-page="query.page"
          :page-size="query.size"
          :page-sizes="[15, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.instance-page {
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
</style>
