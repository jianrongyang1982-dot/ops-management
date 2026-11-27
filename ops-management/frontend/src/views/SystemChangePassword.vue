<template>
  <div class="pwd-page">
    <el-card class="pwd-card">
      <template #header>
        <div class="card-header">
          <el-icon><Lock /></el-icon>
          <span>{{ t('pwd.title') }}</span>
        </div>
      </template>

      <div class="pwd-user">
        <el-icon><User /></el-icon>
        <span>{{ user.display_name || user.usercode }}</span>
        <el-tag size="small" type="info">{{ user.usercode }}</el-tag>
      </div>

      <el-alert :title="t('pwd.hint')" type="info" :closable="false" show-icon class="pwd-alert" />

      <el-form ref="formRef" :model="form" :rules="rules" label-width="140px" class="pwd-form">
        <el-form-item :label="t('pwd.old')" prop="old">
          <el-input v-model="form.old" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-form-item :label="t('pwd.new')" prop="new">
          <el-input v-model="form.new" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item :label="t('pwd.confirm')" prop="confirm">
          <el-input v-model="form.confirm" type="password" show-password autocomplete="new-password" />
        </el-form-item>
      </el-form>

      <div class="pwd-actions">
        <el-button type="primary" :loading="saving" @click="submit">
          <el-icon><Check /></el-icon> {{ t('pwd.save') }}
        </el-button>
        <el-button @click="resetForm">{{ t('pwd.reset') }}</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Lock, User, Check } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { stage1Hash } from '../utils/sha256'

const { t } = useI18n()
const router = useRouter()
const user = computed(() => JSON.parse(localStorage.getItem('user') || '{}'))
const formRef = ref(null)
const saving = ref(false)
const form = ref({ old: '', new: '', confirm: '' })

const rules = computed(() => ({
  old: [{ required: true, message: t('pwd.oldRequired'), trigger: 'blur' }],
  new: [
    { required: true, message: t('pwd.newRequired'), trigger: 'blur' },
    { min: 6, message: t('pwd.minLen'), trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: t('pwd.confirmRequired'), trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== form.value.new) callback(new Error(t('pwd.notMatch')))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}))

function resetForm() {
  form.value = { old: '', new: '', confirm: '' }
  formRef.value?.clearValidate()
}

async function submit() {
  const ok = await formRef.value.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    const uc = user.value.usercode || ''
    // 前端第一层哈希：明文密码不出浏览器；后端只接受当前登录用户（从 JWT 取）
    const [oldHash, newHash] = await Promise.all([
      stage1Hash(uc, form.value.old),
      stage1Hash(uc, form.value.new),
    ])
    const res = await api.post('/system/change-password', {
      old_password: oldHash,
      new_password: newHash,
      confirm_password: newHash,
    })
    await ElMessageBox.alert(t('pwd.needRelogin'), t('pwd.title'), { type: 'success' })
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    router.push('/login')
  } finally { saving.value = false }
}
</script>

<style scoped>
.pwd-page { padding: 24px; height: 100%; overflow: auto; background: #f5f7fa; }
.pwd-card { max-width: 680px; margin: 0 auto; }
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.pwd-user { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; color: #303133; }
.pwd-alert { margin-bottom: 20px; }
.pwd-actions { display: flex; gap: 12px; padding-left: 140px; }
</style>
