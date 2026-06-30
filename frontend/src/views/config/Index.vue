<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { fetchConfig, saveConfig } from "@/api/config";
import {
  CONFIG_SECTIONS,
  CONFIG_SUBSECTIONS,
  CONFIG_FIELDS,
  type ConfigField,
} from "@/config/configSchema";
import { fetchInstanceTags, type InstanceTagRow } from "@/api/instance";
import { fetchGroups, type AuthGroupRow } from "@/api/user";
import { fetchResourceGroups, type ResourceGroupRow } from "@/api/group";

const loading = ref(false);
const saving = ref(false);
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- 动态表单渲染器混合类型
const configValues = ref<Record<string, any>>({});

// 动态选项数据
const dynamicOptions = ref<Record<string, { value: string; label: string }[]>>({});

function getOptions(field: ConfigField): { value: string; label: string }[] {
  if (field.options) return field.options;
  if (field.dynamic) return dynamicOptions.value[field.dynamic] || [];
  return [];
}

// 条件显隐判断
function isVisible(field: ConfigField): boolean {
  if (!field.showWhen) return true;
  const val = configValues.value[field.showWhen.key];
  if (field.showWhen.value === true) return val === true || val === "true";
  if (field.showWhen.value === false) return val === false || val === "false";
  return String(val ?? "") === String(field.showWhen.value);
}

// 按分区/子分区组织字段
interface FieldGroup {
  key: string;
  fields: ConfigField[];
}

const sections = computed(() => {
  const result: { name: string; groups: FieldGroup[] }[] = [];
  for (const sectionName of CONFIG_SECTIONS) {
    const sectionFields = CONFIG_FIELDS.filter((f) => f.section === sectionName);
    if (!sectionFields.length) continue;
    const subs = CONFIG_SUBSECTIONS[sectionName];
    const groups: FieldGroup[] = [];
    if (subs && subs.length) {
      for (const sub of subs) {
        const subFields = sectionFields.filter((f) => f.subsection === sub);
        if (subFields.length) groups.push({ key: sub, fields: subFields });
      }
      // 不属于任何子分区的字段
      const leftover = sectionFields.filter((f) => !f.subsection && !subs.includes(f.subsection || ""));
      if (leftover.length) groups.push({ key: "_", fields: leftover });
    } else {
      groups.push({ key: sectionName, fields: sectionFields });
    }
    result.push({ name: sectionName, groups });
  }
  return result;
});

// 多选字段：存储值是逗号字符串，表单需要数组
function isMultiselectArray(field: ConfigField): boolean {
  return field.type === "multiselect";
}

async function loadConfig() {
  loading.value = true;
  try {
    const data = await fetchConfig();
    // 多选字段：逗号字符串 → 数组
    const values: Record<string, any> = {};
    for (const f of CONFIG_FIELDS) {
      const raw = data[f.key];
      if (isMultiselectArray(f)) {
        values[f.key] = typeof raw === "string" && raw ? raw.split(",") : Array.isArray(raw) ? raw : [];
      } else {
        values[f.key] = raw ?? (f.type === "boolean" ? false : f.type === "number" ? "" : "");
      }
    }
    configValues.value = values;
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

async function loadDynamicOptions() {
  try {
    const [tags, groups, resGroups] = await Promise.all([
      fetchInstanceTags().catch(() => []),
      fetchGroups().catch(() => []),
      fetchResourceGroups({ size: 1000 }).then((r) => r.data.results || []).catch(() => []),
    ]);
    dynamicOptions.value = {
      tags: (tags as InstanceTagRow[]).map((t) => ({ value: t.tag_code, label: `${t.tag_name}(${t.tag_code})` })),
      groups: (groups as AuthGroupRow[]).map((g) => ({ value: String(g.id), label: g.name })),
      resourceGroups: (resGroups as ResourceGroupRow[]).map((g) => ({
        value: String(g.group_id),
        label: g.group_name,
      })),
    };
  } catch {
    // 拦截器已提示
  }
}

async function onSave() {
  saving.value = true;
  try {
    await saveConfig(configValues.value);
    ElMessage.success("配置已保存");
  } catch (e) {
    ElMessage.error(`保存失败：${(e as Error).message}`);
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  loadConfig();
  loadDynamicOptions();
});
</script>

<template>
  <div v-loading="loading" class="config-page">
    <el-card shadow="never">
      <template #header>
        <div style="display:flex;align-items:center;justify-content:space-between">
          <span>系统配置项管理（{{ CONFIG_FIELDS.length }} 项）</span>
          <el-button type="primary" :loading="saving" @click="onSave">保存全部配置</el-button>
        </div>
      </template>

      <el-collapse>
        <el-collapse-item
          v-for="section in sections"
          :key="section.name"
          :title="section.name"
          :name="section.name"
        >
          <template v-for="group in section.groups" :key="group.key">
            <div v-if="group.key !== section.name && group.key !== '_'" class="subsection-title">
              {{ group.key }}
            </div>
            <div v-for="field in group.fields" :key="field.key">
              <el-form-item
                v-if="isVisible(field)"
                :label="field.label"
                class="config-field"
              >
                <!-- boolean -->
                <el-switch
                  v-if="field.type === 'boolean'"
                  v-model="configValues[field.key]"
                />
                <!-- number -->
                <el-input-number
                  v-else-if="field.type === 'number'"
                  v-model="configValues[field.key]"
                  controls-position="right"
                  style="width: 200px"
                />
                <!-- password -->
                <el-input
                  v-else-if="field.type === 'password'"
                  v-model="configValues[field.key]"
                  type="password"
                  show-password
                  :placeholder="field.desc || ''"
                  style="max-width: 400px"
                />
                <!-- select -->
                <el-select
                  v-else-if="field.type === 'select' && !field.dynamic"
                  v-model="configValues[field.key]"
                  filterable
                  style="width: 280px"
                >
                  <el-option
                    v-for="o in getOptions(field)"
                    :key="o.value"
                    :label="o.label"
                    :value="o.value"
                  />
                </el-select>
                <!-- dynamic select -->
                <el-select
                  v-else-if="field.type === 'select' && field.dynamic"
                  v-model="configValues[field.key]"
                  filterable
                  clearable
                  style="width: 280px"
                >
                  <el-option
                    v-for="o in getOptions(field)"
                    :key="o.value"
                    :label="o.label"
                    :value="o.value"
                  />
                </el-select>
                <!-- multiselect -->
                <el-select
                  v-else-if="field.type === 'multiselect'"
                  v-model="configValues[field.key]"
                  multiple
                  filterable
                  style="width: 400px"
                >
                  <el-option
                    v-for="o in getOptions(field)"
                    :key="o.value"
                    :label="o.label"
                    :value="o.value"
                  />
                </el-select>
                <!-- text (default) -->
                <el-input
                  v-else
                  v-model="configValues[field.key]"
                  :placeholder="field.desc || ''"
                  style="max-width: 400px"
                />
                <span v-if="field.desc && field.type !== 'text' && field.type !== 'password'" class="field-hint">
                  {{ field.desc }}
                </span>
              </el-form-item>
            </div>
          </template>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.config-page {
  .subsection-title {
    margin: 16px 0 8px;
    padding-bottom: 4px;
    font-weight: 600;
    font-size: 14px;
    color: var(--el-text-color-primary);
    border-bottom: 1px solid var(--el-border-color-lighter);
  }

  .config-field {
    margin-bottom: 12px;
  }

  .field-hint {
    margin-left: 12px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}
</style>
