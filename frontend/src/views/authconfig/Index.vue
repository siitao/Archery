<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  fetchAuthConfig,
  saveAuthConfig,
  reloadAuthConfig,
  testAuthConnection,
  type AuthConfig,
  type AuthProvider,
} from "@/api/authConfig";

const loading = ref(false);
const saving = ref(false);
const reloading = ref(false);
const testing = ref(false);

/** 当前选定的外部认证方式（默认 local = 不启用外部认证） */
const provider = ref<AuthProvider>("local");

/** 各方式参数。所有方式的字段都放一个表单对象，按 provider 选择性展示。 */
const form = reactive<AuthConfig>({
  auth_provider: "local",
  // LDAP
  auth_ldap_server_uri: "",
  auth_ldap_bind_dn: "",
  auth_ldap_bind_password: "",
  auth_ldap_user_dn_template: "",
  auth_ldap_user_search_base: "",
  auth_ldap_user_search_filter: "(cn=%(user)s)",
  auth_ldap_user_attr_map: "display=displayName,email=mail",
  // OIDC
  oidc_rp_wellknown_url: "",
  oidc_rp_client_id: "",
  oidc_rp_client_secret: "",
  oidc_rp_scopes: "openid profile email",
  oidc_rp_sign_algo: "RS256",
  oidc_user_attr_map: "username=preferred_username,display=name,email=email",
  oidc_btn_name: "以OIDC登录",
  // 钉钉
  ding_app_key: "",
  ding_app_secret: "",
  ding_callback_url: "",
  // CAS
  cas_server_url: "",
  cas_version: "3",
  cas_verify_ssl_certificate: "false",
});

/** 方式选项 */
const PROVIDER_OPTIONS: { value: AuthProvider; label: string; desc: string }[] = [
  { value: "local", label: "关闭（仅本地登录）", desc: "不启用任何外部认证，仅使用本地账号密码登录" },
  { value: "ldap", label: "LDAP", desc: "企业目录服务，用户在表单输入 LDAP 账号密码登录" },
  { value: "oidc", label: "OIDC / SSO", desc: "OpenID Connect 单点登录（Keycloak、Authing 等）" },
  { value: "dingding", label: "钉钉", desc: "钉钉扫码登录" },
  { value: "cas", label: "CAS", desc: "CAS 单点登录" },
];

/** 密码/密钥类字段：后端对空值会保留旧值；前端用占位提示 */
const SECRET_PLACEHOLDER = "（已保存，留空表示不修改）";

async function loadConfig() {
  loading.value = true;
  try {
    const data = await fetchAuthConfig();
    Object.assign(form, data);
    provider.value = (data.auth_provider as AuthProvider) || "local";
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

/** 收集当前 provider 对应的参数（仅该方式相关 key） */
function collectParams(): Record<string, string> {
  const params: Record<string, string> = {};
  const keyMap: Record<string, string[]> = {
    ldap: [
      "auth_ldap_server_uri", "auth_ldap_bind_dn", "auth_ldap_bind_password",
      "auth_ldap_user_dn_template", "auth_ldap_user_search_base",
      "auth_ldap_user_search_filter", "auth_ldap_user_attr_map",
    ],
    oidc: [
      "oidc_rp_wellknown_url", "oidc_rp_client_id", "oidc_rp_client_secret",
      "oidc_rp_scopes", "oidc_rp_sign_algo", "oidc_user_attr_map", "oidc_btn_name",
    ],
    dingding: ["ding_app_key", "ding_app_secret", "ding_callback_url"],
    cas: ["cas_server_url", "cas_version", "cas_verify_ssl_certificate"],
  };
  for (const key of keyMap[provider.value] || []) {
    params[key] = (form[key] as string) ?? "";
  }
  return params;
}

/** 切换方式提示：外部认证一次只能启用一种（对齐项目原设计），由 radio-group 单选保证 */

async function onSave() {
  saving.value = true;
  try {
    await saveAuthConfig(provider.value, collectParams(), false);
    ElMessage.success("认证配置已保存。点击「重载认证配置」后生效。");
  } catch (e) {
    ElMessage.error((e as Error).message || "保存失败");
  } finally {
    saving.value = false;
  }
}

async function onSaveAndReload() {
  try {
    await ElMessageBox.confirm(
      "保存并重载会写入 .env 并重新加载系统配置，期间登录页 SSO 按钮会短暂变化，已登录会话不受影响。是否继续？",
      "保存并重载",
      { type: "warning", confirmButtonText: "保存并重载", cancelButtonText: "取消" }
    );
  } catch {
    return; // 用户取消
  }
  saving.value = true;
  reloading.value = true;
  try {
    await saveAuthConfig(provider.value, collectParams(), true);
    ElMessage.success("认证配置已保存并重载，即时生效。");
    await loadConfig(); // 刷新前端状态（尤其是密码占位）
  } catch (e) {
    ElMessage.error((e as Error).message || "保存并重载失败");
  } finally {
    saving.value = false;
    reloading.value = false;
  }
}

async function onReload() {
  try {
    await ElMessageBox.confirm(
      "重载会把数据库中的认证配置写入 .env 并重新加载系统配置，即时生效。是否继续？",
      "重载认证配置",
      { type: "warning", confirmButtonText: "重载", cancelButtonText: "取消" }
    );
  } catch {
    return;
  }
  reloading.value = true;
  try {
    const res = await reloadAuthConfig();
    ElMessage.success(res.msg || "重载成功");
  } catch (e) {
    ElMessage.error((e as Error).message || "重载失败");
  } finally {
    reloading.value = false;
  }
}

async function onTest() {
  if (provider.value === "local") {
    ElMessage.info("当前为本地登录，无需测试");
    return;
  }
  testing.value = true;
  try {
    const res = await testAuthConnection(provider.value, collectParams());
    ElMessage.success(res.msg || "测试通过");
  } catch (e) {
    ElMessage.error((e as Error).message || "测试失败");
  } finally {
    testing.value = false;
  }
}

onMounted(loadConfig);
</script>

<template>
  <div v-loading="loading" class="authconfig-page">
    <!-- 顶部工具栏 -->
    <el-affix :offset="60">
      <div class="ac-toolbar">
        <div class="toolbar-left">
          <span class="toolbar-title">认证方式配置</span>
          <el-tag size="small" type="success" round>本地登录始终启用</el-tag>
        </div>
        <el-button :loading="testing" @click="onTest" round>测试连接</el-button>
        <el-button :loading="reloading" @click="onReload" round>重载认证配置</el-button>
        <el-button :loading="saving" type="primary" @click="onSaveAndReload" round>
          保存并重载
        </el-button>
        <el-button :loading="saving" @click="onSave" round>仅保存</el-button>
      </div>
    </el-affix>

    <el-alert
      class="ac-tip"
      type="info"
      :closable="false"
      show-icon
      title="说明"
      description="本地账号密码登录始终启用，无法关闭。外部认证（LDAP/OIDC/钉钉/CAS）一次只能启用一种。保存后需点击「重载认证配置」或「保存并重载」方可即时生效。"
    />

    <el-card shadow="never" class="ac-card">
      <el-form label-width="180px" label-position="right">
        <!-- 外部认证方式选择（单选） -->
        <el-form-item label="外部认证方式">
          <el-radio-group v-model="provider">
            <el-radio-button
              v-for="opt in PROVIDER_OPTIONS"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </el-radio-button>
          </el-radio-group>
          <div class="provider-desc">
            {{ PROVIDER_OPTIONS.find((o) => o.value === provider)?.desc }}
          </div>
        </el-form-item>

        <!-- ============ LDAP ============ -->
        <template v-if="provider === 'ldap'">
          <el-divider content-position="left">LDAP 参数</el-divider>
          <el-form-item label="LDAP 服务器地址">
            <el-input v-model="form.auth_ldap_server_uri" placeholder="ldap://127.0.0.1:389" />
          </el-form-item>
          <el-form-item label="Bind DN">
            <el-input v-model="form.auth_ldap_bind_dn" placeholder="cn=admin,dc=example,dc=com" />
          </el-form-item>
          <el-form-item label="Bind 密码">
            <el-input
              v-model="form.auth_ldap_bind_password"
              type="password"
              show-password
              :placeholder="SECRET_PLACEHOLDER"
            />
          </el-form-item>
          <el-form-item label="用户 DN 模板">
            <el-input
              v-model="form.auth_ldap_user_dn_template"
              placeholder="留空则使用 Bind DN + 搜索过滤；填则如 uid=%(user)s,ou=users,dc=example,dc=com"
            />
          </el-form-item>
          <el-form-item label="用户搜索 Base">
            <el-input v-model="form.auth_ldap_user_search_base" placeholder="ou=users,dc=example,dc=com" />
          </el-form-item>
          <el-form-item label="用户搜索过滤">
            <el-input v-model="form.auth_ldap_user_search_filter" placeholder="(cn=%(user)s)" />
          </el-form-item>
          <el-form-item label="属性映射">
            <el-input
              v-model="form.auth_ldap_user_attr_map"
              placeholder="display=displayName,email=mail"
            />
            <div class="field-hint">格式 key=attr，逗号分隔；支持 display、email</div>
          </el-form-item>
        </template>

        <!-- ============ OIDC ============ -->
        <template v-if="provider === 'oidc'">
          <el-divider content-position="left">OIDC 参数</el-divider>
          <el-form-item label="Well-known URL">
            <el-input
              v-model="form.oidc_rp_wellknown_url"
              placeholder="https://keycloak.example.com/realms/<realm>/.well-known/openid-configuration"
            />
          </el-form-item>
          <el-form-item label="Client ID">
            <el-input v-model="form.oidc_rp_client_id" />
          </el-form-item>
          <el-form-item label="Client Secret">
            <el-input
              v-model="form.oidc_rp_client_secret"
              type="password"
              show-password
              :placeholder="SECRET_PLACEHOLDER"
            />
          </el-form-item>
          <el-form-item label="Scopes">
            <el-input v-model="form.oidc_rp_scopes" placeholder="openid profile email" />
          </el-form-item>
          <el-form-item label="签名算法">
            <el-input v-model="form.oidc_rp_sign_algo" placeholder="RS256" />
          </el-form-item>
          <el-form-item label="属性映射">
            <el-input
              v-model="form.oidc_user_attr_map"
              placeholder="username=preferred_username,display=name,email=email"
            />
            <div class="field-hint">
              格式 username=claim,display=claim,email=claim，逗号分隔
            </div>
          </el-form-item>
          <el-form-item label="登录按钮名称">
            <el-input v-model="form.oidc_btn_name" placeholder="以OIDC登录" />
            <div class="field-hint">登录页 SSO 按钮显示的文字</div>
          </el-form-item>
        </template>

        <!-- ============ 钉钉 ============ -->
        <template v-if="provider === 'dingding'">
          <el-divider content-position="left">钉钉参数</el-divider>
          <el-form-item label="App Key">
            <el-input v-model="form.ding_app_key" />
          </el-form-item>
          <el-form-item label="App Secret">
            <el-input
              v-model="form.ding_app_secret"
              type="password"
              show-password
              :placeholder="SECRET_PLACEHOLDER"
            />
          </el-form-item>
          <el-form-item label="回调地址">
            <el-input v-model="form.ding_callback_url" placeholder="/dingding/authenticate/" />
            <div class="field-hint">钉钉扫码登录后的回调路径</div>
          </el-form-item>
          <el-alert
            type="warning"
            :closable="false"
            show-icon
            title="钉钉无独立测试端点，请保存并重载后用扫码登录验证。"
          />
        </template>

        <!-- ============ CAS ============ -->
        <template v-if="provider === 'cas'">
          <el-divider content-position="left">CAS 参数</el-divider>
          <el-form-item label="CAS 服务端地址">
            <el-input v-model="form.cas_server_url" placeholder="https://cas.example.com/cas" />
          </el-form-item>
          <el-form-item label="CAS 版本">
            <el-input v-model="form.cas_version" placeholder="3" />
          </el-form-item>
          <el-form-item label="校验 SSL 证书">
            <el-switch
              :model-value="form.cas_verify_ssl_certificate === 'true'"
              inline-prompt
              active-text="校验"
              inactive-text="不校验"
              @update:model-value="
                form.cas_verify_ssl_certificate = $event ? 'true' : 'false'
              "
            />
          </el-form-item>
        </template>

        <!-- 关闭外部认证时无需参数 -->
        <template v-if="provider === 'local'">
          <el-alert
            type="success"
            :closable="false"
            show-icon
            title="当前仅启用本地账号密码登录。选择上方任一外部认证方式并填写参数即可启用。"
          />
        </template>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.authconfig-page {
  padding: 16px;
}
.ac-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: var(--el-bg-color, #fff);
  border-bottom: 1px solid var(--el-border-color-light, #ebeef5);
  flex-wrap: wrap;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-right: auto;
}
.toolbar-title {
  font-size: 16px;
  font-weight: 600;
}
.ac-tip {
  margin: 12px 0;
}
.ac-card {
  margin-top: 8px;
}
.provider-desc {
  width: 100%;
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
}
.field-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  line-height: 1.4;
}
</style>
