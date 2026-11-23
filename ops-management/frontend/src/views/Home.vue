<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="sidebar-logo"><el-icon><Box /></el-icon> {{ t('app.name') }}</div>
      <div class="sidebar-menu">
        <el-menu
          :default-active="activeMenu"
          :default-openeds="['container-group']"
          router
          background-color="transparent"
          text-color="#c8d6e5"
          active-text-color="#fff"
        >
          <el-sub-menu index="container-group">
            <template #title>
              <el-icon><Box /></el-icon><span>{{ t('home.containerGroup') }}</span>
            </template>
            <el-menu-item index="/container/list">
              <el-icon><DataBoard /></el-icon><span>{{ t('home.containerTracking') }}</span>
            </el-menu-item>
            <el-menu-item index="/container/dashboard">
              <el-icon><DataBoard /></el-icon><span>{{ t('home.dashboard') }}</span>
            </el-menu-item>
          </el-sub-menu>
        </el-menu>
      </div>
      <div class="sidebar-user">
        <el-icon><User /></el-icon> {{ user.display_name || t('home.user') }}
        <el-button link type="danger" size="small" style="float:right;color:#f56c6c" @click="logout">{{ t('home.logout') }}</el-button>
      </div>
    </aside>
    <div class="main-area">
      <div class="header">
        <div class="header-title">{{ pageTitle }}</div>
        <div class="header-actions">
          <el-dropdown @command="switchLang" trigger="click">
            <el-button plain size="small"><el-icon><Goods /></el-icon> {{ locale === 'enUS' ? 'English' : '简体中文' }} <el-icon><ArrowDown /></el-icon></el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="zhCN" :disabled="locale === 'zhCN'">简体中文</el-dropdown-item>
                <el-dropdown-item command="enUS" :disabled="locale === 'enUS'">English</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button type="primary" plain size="small" :loading="syncing" @click="runSync">
            <el-icon><Refresh /></el-icon> {{ t('home.syncNow') }}
          </el-button>
          <el-button plain size="small" @click="openLog">
            <el-icon><Document /></el-icon> {{ t('home.viewLog') }}
          </el-button>
        </div>
      </div>
      <div class="content"><router-view /></div>
    </div>

    <!-- 飞驼请求日志 -->
    <el-dialog v-model="logVisible" :title="t('home.logTitle')" width="900px" top="5vh">
      <div v-loading="logLoading">
        <pre class="log-content">{{ logContent || t('home.logEmpty') }}</pre>
      </div>
      <template #footer>
        <el-button @click="logVisible=false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="loadLog">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Goods, ArrowDown, Refresh, Document } from '@element-plus/icons-vue'
import api from '../api'
import { setLocale } from '../i18n'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const activeMenu = computed(() => route.path)
const pageTitle = computed(() => route.path.includes('dashboard') ? t('home.dashboard') : t('home.containerTracking'))
const user = ref(JSON.parse(localStorage.getItem('user') || '{}'))
const syncing = ref(false)

function switchLang(lang) { setLocale(lang) }

function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/login')
}

async function runSync() {
  syncing.value = true
  try {
    const res = await api.post('/sync/run')
    ElMessage.success(t('home.syncResult', { scanned: res.scanned, synced: res.synced, failed: res.failed }))
  } finally {
    syncing.value = false
  }
}

// 飞驼请求日志
const logVisible = ref(false)
const logLoading = ref(false)
const logContent = ref('')
async function openLog() {
  logVisible.value = true
  await loadLog()
}
async function loadLog() {
  logLoading.value = true
  try {
    const res = await api.get('/sync/log', { params: { lines: 300 } })
    logContent.value = res.content || ''
  } finally {
    logLoading.value = false
  }
}
</script>

<style scoped>
.header-actions { display: flex; align-items: center; gap: 10px; }
.log-content { background: #1e1e1e; color: #d4d4d4; padding: 16px; border-radius: 6px; font-family: Consolas, Monaco, monospace; font-size: 12px; line-height: 1.6; max-height: 65vh; overflow: auto; white-space: pre-wrap; word-break: break-all; margin: 0; }
</style>
