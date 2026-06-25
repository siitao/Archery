<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { legacyBase } from "@/utils/request";
import {
  fetchDashboardCharts,
  type DashboardCharts,
  type BarLineChart,
  type PieDatum,
} from "@/api/dashboard";
import EChart from "@/components/EChart.vue";
import type { EChartsOption } from "echarts";

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
  { title: "在线查询", desc: "对授权实例执行只读 SQL", icon: "Search", color: "#2563eb", perm: "sql.menu_sqlquery", routeName: "sqlquery-index" },
  { title: "SQL 上线", desc: "提交并审核 DDL/DML 工单", icon: "CircleCheck", color: "#16a34a", perm: "sql.menu_sqlworkflow", routeName: "sqlworkflow-list" },
  { title: "实例列表", desc: "查看与检索已纳管实例", icon: "Coin", color: "#db2777", perm: "sql.menu_instance_list", routeName: "instance-list" },
  { title: "慢查日志", desc: "Review 慢查询并优化", icon: "Timer", color: "#ea580c", perm: "sql.menu_slowquery", routeName: "slowquery" },
  { title: "数据字典", desc: "浏览表结构与对象", icon: "Reading", color: "#0891b2", perm: "sql.menu_data_dictionary", routeName: "datadictionary" },
  { title: "OpenAPI", desc: "REST 接口文档", icon: "Promotion", color: "#7c3aed", perm: "sql.menu_openapi", legacyPath: "/api/swagger/" },
];

function visibleEntries() {
  return entries.filter((e) => !e.perm || auth.hasPerm(e.perm));
}

function go(e: QuickEntry) {
  if (e.routeName) router.push({ name: e.routeName });
  else if (e.legacyPath) window.open(legacyBase + e.legacyPath, "_blank");
}

// ===================== 图表 =====================
const loading = ref(false);
const charts = ref<DashboardCharts | null>(null);

const dateRange = ref<[string, string]>(defaultRange());

function defaultRange(): [string, string] {
  const fmt = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 29);
  return [fmt(start), fmt(end)];
}

function barOption(title: string, c: BarLineChart): EChartsOption {
  return {
    title: { text: title, left: "center", textStyle: { fontSize: 14 } },
    tooltip: { trigger: "axis" },
    grid: { left: 48, right: 24, top: 48, bottom: 48, containLabel: true },
    xAxis: {
      type: "category",
      data: c.x,
      axisLabel: { interval: 0, rotate: c.x.length > 10 ? 45 : 0 },
    },
    yAxis: { type: "value" },
    series: c.series.map((s) => ({
      name: s.name,
      type: "bar",
      data: s.data,
    })),
  };
}

function lineOption(title: string, c: BarLineChart): EChartsOption {
  return {
    title: { text: title, left: "center", textStyle: { fontSize: 14 } },
    tooltip: { trigger: "axis" },
    legend: { top: 24 },
    grid: { left: 48, right: 24, top: 56, bottom: 48, containLabel: true },
    xAxis: {
      type: "category",
      data: c.x,
      axisLabel: { interval: 0, rotate: c.x.length > 10 ? 45 : 0 },
    },
    yAxis: { type: "value" },
    series: c.series.map((s) => ({
      name: s.name,
      type: "line",
      smooth: true,
      data: s.data,
    })),
  };
}

function pieOption(title: string, data: PieDatum[]): EChartsOption {
  return {
    title: { text: title, left: "center", textStyle: { fontSize: 14 } },
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { type: "scroll", orient: "vertical", left: "left", top: "middle" },
    series: [
      {
        type: "pie",
        radius: ["30%", "60%"],
        center: ["60%", "55%"],
        data: data.map((d) => ({ name: d.name, value: Number(d.value) })),
        emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: "rgba(0,0,0,0.3)" } },
      },
    ],
  };
}

// 各图 option（数据为空时占位）
const optBar1 = computed(() => (charts.value ? barOption("SQL 上线数量（按日）", charts.value.bar1) : {}));
const optBar2 = computed(() => (charts.value ? barOption("SQL 上线用户", charts.value.bar2) : {}));
const optBar3 = computed(() => (charts.value ? barOption("慢查询 db 维度", charts.value.bar3) : {}));
const optBar5 = computed(() => (charts.value ? barOption("SQL 上线工单", charts.value.bar5) : {}));
const optLine1 = computed(() => (charts.value ? lineOption("SQL 查询统计（按日）", charts.value.line1) : {}));
const optPie1 = computed(() => (charts.value ? pieOption("SQL 上线统计（按组）", charts.value.pie1) : {}));
const optPie2 = computed(() => (charts.value ? pieOption("SQL 语法类型", charts.value.pie2) : {}));
const optPie3 = computed(() => (charts.value ? pieOption("慢查询 db/user 维度", charts.value.pie3) : {}));
const optPie4 = computed(() => (charts.value ? pieOption("SQL 查询用户（检索行数）", charts.value.pie4) : {}));
const optPie5 = computed(() => (charts.value ? pieOption("DB 检索行数", charts.value.pie5) : {}));

async function loadCharts() {
  if (!dateRange.value || dateRange.value.length < 2) return;
  loading.value = true;
  try {
    charts.value = await fetchDashboardCharts(dateRange.value[0], dateRange.value[1]);
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

function onDateChange() {
  loadCharts();
}

onMounted(loadCharts);
</script>

<template>
  <div class="dashboard">
    <el-card shadow="never" class="welcome">
      <div class="welcome-text">
        <h2>{{ greeting }}，{{ auth.displayName || "Archery" }}</h2>
        <p>欢迎使用 Archery SQL 审核查询平台</p>
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

    <el-card shadow="never" class="charts-card" v-loading="loading">
      <div class="charts-head">
        <div>
          <h3>数据图表</h3>
          <p class="charts-sub">SQL 上线 / 查询 / 慢查等多维度统计</p>
        </div>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="-"
          start-placeholder="开始"
          end-placeholder="结束"
          @change="onDateChange"
        />
      </div>
      <div class="charts-grid">
        <EChart :option="optBar1" />
        <EChart :option="optLine1" />
        <EChart :option="optPie1" />
        <EChart :option="optPie2" />
        <EChart :option="optBar2" />
        <EChart :option="optBar5" />
        <EChart :option="optPie4" />
        <EChart :option="optPie5" />
        <EChart :option="optBar3" />
        <EChart :option="optPie3" />
      </div>
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
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: 16px;
}
</style>
