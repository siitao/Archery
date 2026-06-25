<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { legacyBase } from "@/utils/request";

const auth = useAuthStore();
const router = useRouter();

const hour = new Date().getHours();
const greeting = computed(() => {
  if (hour < 6) return "凌晨好";
  if (hour < 12) return "上午好";
  if (hour < 14) return "中午好";
  if (hour < 18) return "下午好";
  return "晚上好";
});

interface QuickEntry {
  title: string;
  desc: string;
  icon: string;
  color: string;
  perm?: string;
  routeName?: string;
  legacyPath?: string;
}

const entries: QuickEntry[] = [
  { title: "在线查询", desc: "对授权实例执行只读 SQL", icon: "Search", color: "#2563eb", perm: "sql.menu_sqlquery", legacyPath: "/sqlquery/" },
  { title: "SQL 上线", desc: "提交并审核 DDL/DML 工单", icon: "CircleCheck", color: "#16a34a", perm: "sql.menu_sqlworkflow", legacyPath: "/sqlworkflow/" },
  { title: "实例列表", desc: "查看与检索已纳管实例", icon: "Coin", color: "#db2777", perm: "sql.menu_instance_list", routeName: "instance-list" },
  { title: "慢查日志", desc: "Review 慢查询并优化", icon: "Timer", color: "#ea580c", perm: "sql.menu_slowquery", legacyPath: "/slowquery/" },
  { title: "数据字典", desc: "浏览表结构与对象", icon: "Reading", color: "#0891b2", perm: "sql.menu_data_dictionary", legacyPath: "/data_dictionary/" },
  { title: "OpenAPI", desc: "REST 接口文档", icon: "Promotion", color: "#7c3aed", perm: "sql.menu_openapi", legacyPath: "/api/swagger/" },
];

function visibleEntries() {
  return entries.filter((e) => !e.perm || auth.hasPerm(e.perm));
}

function go(e: QuickEntry) {
  if (e.routeName) router.push({ name: e.routeName });
  else if (e.legacyPath) window.open(legacyBase + e.legacyPath, "_blank");
}

function openLegacyCharts() {
  window.open(`${legacyBase}/dashboard/`, "_blank");
}
</script>

<template>
  <div class="dashboard">
    <el-card shadow="never" class="welcome">
      <div class="welcome-text">
        <h2>{{ greeting }}，{{ auth.displayName || "Archery" }}</h2>
        <p>欢迎使用 Archery SQL 审核查询平台（新前端预览）</p>
      </div>
    </el-card>

    <div class="entries">
      <el-card
        v-for="e in visibleEntries()"
        :key="e.title"
        shadow="hover"
        class="entry"
        @click="go(e)"
      >
        <div class="entry-icon" :style="{ background: e.color }">
          <el-icon :size="24"><component :is="e.icon" /></el-icon>
        </div>
        <div class="entry-body">
          <div class="entry-title">{{ e.title }}</div>
          <div class="entry-desc">{{ e.desc }}</div>
        </div>
      </el-card>
    </div>

    <el-card shadow="never" class="charts-card">
      <div class="charts-head">
        <div>
          <h3>数据图表</h3>
          <p class="charts-sub">基于 pyecharts 的完整图表（按日期统计上线 / 查询 / 慢查等）</p>
        </div>
        <el-button type="primary" plain @click="openLegacyCharts">
          查看完整图表（旧版）
        </el-button>
      </div>
      <el-empty description="图表组件正在迁移中，当前可在旧版页面查看" :image-size="80" />
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.welcome {
  margin-bottom: 20px;
  background: linear-gradient(120deg, #1e3a8a, #2563eb);
  border: none;
  color: #fff;
  :deep(.el-card__body) {
    padding: 24px 28px;
  }
  h2 {
    margin: 0;
    font-size: 22px;
  }
  p {
    margin: 8px 0 0;
    opacity: 0.9;
  }
}

.entries {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.entry {
  cursor: pointer;
  transition: transform 0.15s ease;
  &:hover {
    transform: translateY(-2px);
  }
  :deep(.el-card__body) {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px;
  }
}

.entry-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.entry-title {
  font-size: 16px;
  font-weight: 600;
}
.entry-desc {
  margin-top: 4px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.charts-card {
  h3 {
    margin: 0;
    font-size: 16px;
  }
  .charts-sub {
    margin: 4px 0 0;
    font-size: 13px;
    color: var(--el-text-color-secondary);
  }
}

.charts-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
</style>
