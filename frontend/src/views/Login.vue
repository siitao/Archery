<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { User, Lock } from "@element-plus/icons-vue";
import { useAuthStore } from "@/stores/auth";
import { setCookie } from "@/utils/auth";
import { legacyBase } from "@/utils/request";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const formRef = ref<FormInstance>();
const loading = ref(false);
const form = reactive({ username: "", password: "" });

const rules: FormRules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
};

// 进入登录页时探测一次登录态：已登录则直接跳转；未登录也会触发 /me/ 设置 csrftoken cookie，
// 以保证后续 /authenticate/ 的 POST 能通过 CSRF 校验。
onMounted(() => {
  auth.loadCurrentUser().then(
    () => router.replace((route.query.redirect as string) || "/dashboard"),
    () => {
      /* 未登录，停留 */
    }
  );
});

async function onSubmit() {
  if (!formRef.value) return;
  await formRef.value.validate(async (valid) => {
    if (!valid) return;
    loading.value = true;
    try {
      const res = await auth.authenticateUser(form.username, form.password);
      if (res.status === 0) {
        if (res.data) {
          // 需要 2FA：切换临时会话后交给旧版 2FA 页面完成。
          // 2FA 登录/配置为安全关键流程，留待后续阶段整体迁移到 SPA。
          setCookie("sessionid", res.data);
          window.location.href = `${legacyBase}/login/2fa/`;
          return;
        }
        // 无 2FA：加载用户信息并跳转
        await auth.loadCurrentUser();
        router.replace((route.query.redirect as string) || "/dashboard");
      } else {
        ElMessage.error(res.msg || "登录失败");
      }
    } catch {
      // 错误提示已由 request 拦截器处理
    } finally {
      loading.value = false;
    }
  });
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <h1>Archery</h1>
        <p>SQL 审核查询平台</p>
      </div>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        size="large"
        @keyup.enter="onSubmit"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名"
            :prefix-icon="User"
            clearable
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            :prefix-icon="Lock"
            show-password
            clearable
          />
        </el-form-item>
        <el-button
          type="primary"
          class="login-btn"
          :loading="loading"
          @click="onSubmit"
        >
          登录
        </el-button>
      </el-form>
      <div class="login-footer">
        <a :href="`${legacyBase}/login/`">SSO / 注册 / 传统登录</a>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%);
}

.login-card {
  width: 380px;
  padding: 40px 36px 28px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
}

.login-brand {
  text-align: center;
  margin-bottom: 28px;

  h1 {
    margin: 0;
    font-size: 30px;
    font-weight: 700;
    color: #1e3a8a;
  }
  p {
    margin: 8px 0 0;
    color: #6b7280;
    font-size: 14px;
  }
}

.login-btn {
  width: 100%;
  margin-top: 4px;
}

.login-footer {
  margin-top: 18px;
  text-align: center;
  font-size: 13px;

  a {
    color: #6b7280;
    text-decoration: none;
    &:hover {
      color: #1e3a8a;
    }
  }
}
</style>
