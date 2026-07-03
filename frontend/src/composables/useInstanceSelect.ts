import { ref, computed } from "vue";
import { fetchUserInstances, type GroupInstanceRow } from "@/api/group";

/**
 * 实例下拉公共逻辑：多个查询/管理子页共用。
 * 返回实例列表、按 db_type 分组、当前选中实例及其 db_type。
 *
 * 走用户级接口（/api/v1/group/user_instances/），按资源组授权过滤，
 * 普通用户只能看到自己组内可访问的实例，避免触发 /api/v1/instance/ 的 403。
 *
 * @param supportedDbTypes - 可选，限定支持的 db_type 列表。
 *   传入后由后端过滤（单值）或前端过滤（多值）。
 */
export function useInstanceSelect(supportedDbTypes?: string[]) {
  const instanceName = ref("");
  const instanceOptions = ref<GroupInstanceRow[]>([]);
  const loading = ref(false);

  async function loadInstances() {
    loading.value = true;
    try {
      // 后端 db_type[] 支持多值过滤；单值时也走数组传参
      const params: { db_type?: string[] } = {};
      if (supportedDbTypes && supportedDbTypes.length === 1) {
        params.db_type = supportedDbTypes;
      }
      let results: GroupInstanceRow[] = await fetchUserInstances(params);
      if (supportedDbTypes && supportedDbTypes.length > 1) {
        results = results.filter((i) => supportedDbTypes.includes(i.db_type));
      }
      instanceOptions.value = results;
    } catch {
      // 错误提示已由 request 拦截器处理
    } finally {
      loading.value = false;
    }
  }

  /** 按 db_type 分组（el-option-group） */
  const instanceGroups = computed(() => {
    const map = new Map<string, GroupInstanceRow[]>();
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
