<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from "vue";
import * as echarts from "echarts";
import type { EChartsOption } from "echarts";

const props = withDefaults(
  // 允许传 EChartsOption 或松散对象（规避 echarts v6 在某些上下文的 graphic 联合类型深检）
  defineProps<{ option: EChartsOption | Record<string, unknown>; height?: string }>(),
  { height: "360px" }
);

const el = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
let ro: ResizeObserver | null = null;

function render() {
  if (!chart) return;
  chart.setOption(props.option as EChartsOption, true);
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
