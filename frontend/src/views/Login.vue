<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { User, Lock } from "@element-plus/icons-vue";
import { useAuthStore } from "@/stores/auth";
import { setCookie } from "@/utils/auth";
import { legacyBase } from "@/utils/request";
import {
  fetch2faContext,
  fetch2faVerify,
  send2faSms,
  type TwoFaContext,
} from "@/api/user";

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

// 2FA 状态
const twoFaMode = ref(false);
const twoFaCtx = ref<TwoFaContext | null>(null);
const twoFaForm = reactive({
  auth_type: "totp",
  otp: "",
  phone: "",
});
let smsCountdown = 0;
const smsBtnText = ref("获取验证码");

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
          // 需要 2FA：临时会话 sessionKey 设为 sessionid cookie，
          // 后续 /api/v1/user/2fa/* 同源带 cookie 即可读到该会话。
          setCookie("sessionid", res.data);
          await enter2fa();
          return;
        }
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

async function enter2fa() {
  try {
    twoFaCtx.value = await fetch2faContext();
    const types = twoFaCtx.value.auth_types.map((t) => t.code);
    twoFaForm.auth_type = types.includes("totp") ? "totp" : types[0] || "totp";
    twoFaForm.phone = twoFaCtx.value.phone || "";
    twoFaMode.value = true;
  } catch {
    // 拦截器已提示
  }
}

function onAuthTypeChange() {
  twoFaForm.otp = "";
}

async function onSendSms() {
  if (!twoFaForm.phone) return ElMessage.warning("请输入手机号");
  try {
    const { data } = await send2faSms({
      engineer: form.username,
      phone: twoFaForm.phone,
    });
    if (data.status === 0) {
      ElMessage.success("验证码已发送，5 分钟内有效");
      smsCountdown = 60;
      const timer = setInterval(() => {
        smsCountdown -= 1;
        smsBtnText.value = smsCountdown > 0 ? `${smsCountdown}s 后重发` : "获取验证码";
        if (smsCountdown <= 0) clearInterval(timer);
      }, 1000);
    } else {
      ElMessage.error(data.msg);
    }
  } catch {
    // 拦截器已提示
  }
}

async function onVerify() {
  if (!twoFaForm.otp) return ElMessage.warning("请输入验证码");
  loading.value = true;
  try {
    const { data } = await fetch2faVerify({
      engineer: form.username,
      otp: twoFaForm.otp,
      auth_type: twoFaForm.auth_type,
      phone: twoFaForm.auth_type === "sms" ? twoFaForm.phone : undefined,
    });
    if (data.status === 0) {
      await auth.loadCurrentUser();
      router.replace((route.query.redirect as string) || "/dashboard");
    } else {
      ElMessage.error(data.msg || "验证失败");
    }
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false;
  }
}

function backToLogin() {
  twoFaMode.value = false;
  twoFaCtx.value = null;
  twoFaForm.otp = "";
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <h1>Archery</h1>
        <p>SQL 审核查询平台</p>
      </div>

      <!-- 2FA 输入 -->
      <template v-if="twoFaMode">
        <div class="twofa-title">两步验证</div>
        <el-form size="large" @keyup.enter="onVerify">
          <el-form-item v-if="twoFaCtx && twoFaCtx.auth_types.length > 1">
            <el-select v-model="twoFaForm.auth_type" style="width: 100%" @change="onAuthTypeChange">
              <el-option
                v-for="t in twoFaCtx?.auth_types"
                :key="t.code"
                :label="t.display"
                :value="t.code"
              />
            </el-select>
          </el-form-item>
          <template v-if="twoFaForm.auth_type === 'sms'">
            <el-form-item>
              <el-input v-model="twoFaForm.phone" placeholder="手机号" clearable>
                <template #append>
                  <el-button :disabled="smsCountdown > 0" @click="onSendSms">
                    {{ smsBtnText }}
                  </el-button>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item>
              <el-input v-model="twoFaForm.otp" placeholder="短信验证码" clearable />
            </el-form-item>
          </template>
          <el-form-item v-else>
            <el-input v-model="twoFaForm.otp" placeholder="动态验证码（TOTP）" clearable />
          </el-form-item>
          <el-button type="primary" class="login-btn" :loading="loading" @click="onVerify">
            验证并登录
          </el-button>
          <el-button link class="back-btn" @click="backToLogin">返回登录</el-button>
        </el-form>
      </template>

      <!-- 账号密码 -->
      <template v-else>
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
      </template>
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

.twofa-title {
  text-align: center;
  margin-bottom: 20px;
  font-size: 18px;
  font-weight: 600;
  color: #1e3a8a;
}

.login-btn {
  width: 100%;
  margin-top: 4px;
}

.back-btn {
  width: 100%;
  margin-top: 10px;
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
