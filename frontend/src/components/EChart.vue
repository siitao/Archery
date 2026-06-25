<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from "vue";
import * as echarts from "echarts";
import type { EChartsOption } from "echarts";

const props = withDefaults(
  defineProps<{ option: EChartsOption; height?: string }>(),
  { height: "360px" }
);

const el = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
let ro: ResizeObserver | null = null;

function render() {
  if (!chart) return;
  chart.setOption(props.option, true);
}

onMounted(async () => {
  await nextTick();
  if (!el.value) return;
  chart = echarts.init(el.value);
  render();
  // 容器尺寸变化时自适应
  ro = new ResizeObserver(() => chart?.resize());
  ro.observe(el.value);
});

watch(() => props.option, render, { deep: true });

onBeforeUnmount(() => {
  ro?.disconnect();
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div ref="el" :style="{ width: '100%', height }" />
</template>
