<template>
  <div class="login-page">
    <div class="login-panel">
      <div class="login-heading">
        <span class="welcome">{{ t('login.welcome') }}</span>
        <span class="slash">/</span>
        <span class="login-word">{{ t('login.loginWord') }}</span>
      </div>

      <div class="login-form" @keyup.enter="handleLogin">
        <!-- 账号 -->
        <div class="field">
          <el-icon class="field-icon"><User /></el-icon>
          <input
            v-model="form.usercode"
            class="field-input"
            type="text"
            autocomplete="username"
            :placeholder="t('login.username')"
          />
        </div>

        <!-- 密码（聚焦时红色边框，与参考图一致） -->
        <div class="field password-field">
          <el-icon class="field-icon"><Lock /></el-icon>
          <input
            ref="pwdRef"
            v-model="form.password"
            class="field-input"
            type="password"
            autocomplete="current-password"
            :placeholder="t('login.passwordPlaceholder')"
          />
        </div>

        <!-- 语言 -->
        <div class="field lang-field">
          <select v-model="langValue" class="field-select" @change="switchLang(langValue)">
            <option value="enUS">English</option>
            <option value="zhCN">简体中文</option>
          </select>
          <el-icon class="select-arrow"><ArrowDown /></el-icon>
        </div>

        <button class="login-button" :disabled="loading" @click="handleLogin">
          {{ loading ? t('login.logging') : t('login.loginBtn') }}
        </button>
      </div>

      <div class="login-footer">©</div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { User, Lock, ArrowDown } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'
import { setLocale } from '../i18n'

const { t, locale } = useI18n()
const router = useRouter()
const form = ref({ usercode: '', password: '' })
const loading = ref(false)
const langValue = ref(locale.value)
const pwdRef = ref(null)

watch(locale, (val) => { langValue.value = val })

onMounted(() => {
  nextTick(() => pwdRef.value?.focus())
})

function switchLang(lang) {
  setLocale(lang)
}

async function handleLogin() {
  if (!form.value.usercode || !form.value.password) {
    ElMessage.warning(t('login.required'))
    return
  }
  loading.value = true
  try {
    const res = await api.post('/auth/login', form.value)
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('user', JSON.stringify({
      display_name: res.display_name,
      usercode: res.usercode,
      accountname: res.accountname,
    }))
    ElMessage.success(t('login.success'))
    router.push('/')
  } catch (e) {
    // 拦截器已提示错误
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  padding: 40px 20px;
}
.login-panel { width: 100%; max-width: 544px; }

.login-heading { display: flex; align-items: baseline; gap: 12px; margin-bottom: 44px; white-space: nowrap; }
.login-heading .welcome { font-size: 44px; line-height: 1.1; font-weight: 700; color: #202124; letter-spacing: -1px; }
.login-heading .slash { font-size: 34px; font-weight: 400; color: #a8adb4; }
.login-heading .login-word { font-size: 34px; line-height: 1.1; font-weight: 700; color: #a8adb4; letter-spacing: 1px; }

.field {
  display: flex;
  align-items: center;
  height: 56px;
  margin-bottom: 20px;
  padding: 0 18px;
  border: 1px solid #dfe3e8;
  border-radius: 8px;
  background: #fff;
  transition: border-color .18s ease, box-shadow .18s ease;
}
.field:focus-within { border-color: #ff5b5b; box-shadow: 0 0 0 3px rgba(255, 91, 91, .12); }
.field-icon { font-size: 18px; color: #8c94a0; margin-right: 12px; flex-shrink: 0; }
.field-input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  font-size: 16px;
  color: #202124;
}
.field-input::placeholder { color: #aab0b8; }

.lang-field { position: relative; }
.field-select {
  appearance: none;
  -webkit-appearance: none;
  width: 100%;
  height: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  font-size: 16px;
  font-weight: 500;
  color: #202124;
  cursor: pointer;
}
.select-arrow { position: absolute; right: 18px; top: 50%; transform: translateY(-50%); color: #5f6773; font-size: 14px; pointer-events: none; }

.login-button {
  width: 100%;
  height: 52px;
  margin-top: 4px;
  border: 0;
  border-radius: 8px;
  background: #2f7cf6;
  color: #fff;
  font-size: 18px;
  font-weight: 500;
  cursor: pointer;
  transition: background .18s ease;
}
.login-button:hover:not(:disabled) { background: #1f6fe5; }
.login-button:disabled { opacity: .7; cursor: not-allowed; }

.login-footer { margin-top: 26px; text-align: center; color: #b8bec7; font-size: 14px; }

@media (max-width: 600px) {
  .login-heading .welcome { font-size: 34px; }
  .login-heading .login-word { font-size: 26px; }
  .login-heading .slash { font-size: 26px; }
}
</style>
