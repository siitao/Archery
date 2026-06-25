import { ref, computed } from "vue";
import { fetchInstances, type InstanceRow } from "@/api/instance";

/**
 * 实例下拉公共逻辑：5 个实例管理子页共用。
 * 返回实例列表、按 db_type 分组、当前选中实例及其 db_type。
 */
export function useInstanceSelect() {
  const instanceName = ref("");
  const instanceOptions = ref<InstanceRow[]>([]);
  const loading = ref(false);

  async function loadInstances() {
    loading.value = true;
    try {
      const { data } = await fetchInstances({ size: 1000 });
      instanceOptions.value = data.results || [];
    } catch {
      // 错误提示已由 request 拦截器处理
    } finally {
      loading.value = false;
    }
  }

  /** 按 db_type 分组（el-option-group） */
  const instanceGroups = computed(() => {
    const map = new Map<string, InstanceRow[]>();
    for (const i of instanceOptions.value) {
      const k = i.db_type || "other";
      if (!map.has(k)) map.set(k, []);
      map.get(k)!.push(i);
    }
    return [...map.entries()].map(([label, items]) => ({ label, items }));
  });

  const currentInstance = computed(() =>
    instanceOptions.value.find((i) => i.instance_name === instanceName.value)
  );
  const currentDbType = computed(() => currentInstance.value?.db_type || "");

  return {
    instanceName,
    instanceOptions,
    instanceGroups,
    currentInstance,
    currentDbType,
    loading,
    loadInstances,
  };
}
