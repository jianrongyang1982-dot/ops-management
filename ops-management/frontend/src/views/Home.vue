<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="sidebar-logo"><el-icon><Box /></el-icon> {{ t('app.name') }}</div>
      <div v-loading="menuLoading" class="sidebar-menu">
        <el-menu
          :default-active="activeMenu"
          :default-openeds="openGroups"
          router
          background-color="transparent"
          text-color="#c8d6e5"
          active-text-color="#fff"
        >
          <el-sub-menu v-for="g in menuGroups" :key="g.code" :index="g.code + '-group'">
            <template #title>
              <el-icon><component :is="menuIcon(g.menus[0]?.icon)" /></el-icon><span>{{ groupName(g) }}</span>
            </template>
            <el-menu-item v-for="m in g.menus" :key="m.code" :index="m.path">
              <el-icon><component :is="menuIcon(m.icon)" /></el-icon><span>{{ menuName(m) }}</span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-for="m in flatMenus" :key="m.code" :index="m.path">
            <el-icon><component :is="menuIcon(m.icon)" /></el-icon><span>{{ menuName(m) }}</span>
          </el-menu-item>
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
          <el-popover placement="bottom-end" :width="360" trigger="click" @show="loadMessages">
            <template #reference>
              <el-button plain size="small" class="msg-btn">
                <el-icon><Bell /></el-icon>
                <span v-if="unread > 0" class="badge">{{ unread > 99 ? '99+' : unread }}</span>
              </el-button>
            </template>
            <div class="msg-panel">
              <div class="msg-head">
                <span>{{ t('issue.messages') }}</span>
                <el-button link type="primary" size="small" @click="readAll">{{ t('issue.readAll') }}</el-button>
              </div>
              <div v-if="messages.length === 0" class="msg-empty">{{ t('issue.noMessages') }}</div>
              <div v-for="m in messages" :key="m.id" class="msg-item" :class="{ unread: !m.is_read }" @click="openMessage(m)">
                <div class="msg-title">{{ m.title }}</div>
                <div class="msg-content">{{ m.content }}</div>
                <div class="msg-time">{{ m.created_time }}</div>
              </div>
            </div>
          </el-popover>
          <el-dropdown @command="switchLang" trigger="click">
            <el-button plain size="small"><el-icon><Goods /></el-icon> {{ langLabel }} <el-icon><ArrowDown /></el-icon></el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="zhCN" :disabled="locale === 'zhCN'">简体中文</el-dropdown-item>
                <el-dropdown-item command="enUS" :disabled="locale === 'enUS'">English</el-dropdown-item>
                <el-dropdown-item command="ar" :disabled="locale === 'ar'">العربية</el-dropdown-item>
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
      <TagsView
        :items="tagItems"
        :active="route.path"
        @change="openTag"
        @close="closeTag"
        @close-all="closeAllTags"
        @close-other="closeOtherTags"
        @favorite="openFavoriteConfig"
        :is-favorited="isCurrentFavorited"
        @toggle-favorite="toggleFavorite"
      />
      <div class="content">
        <router-view v-slot="{ Component, route: r }">
          <keep-alive>
            <component :is="Component" :key="r.path" />
          </keep-alive>
        </router-view>
      </div>
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

    <FavoriteConfig v-model="favVisible" @saved="onFavSaved" />
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Goods, ArrowDown, Refresh, Document, Box, User, Bell } from '@element-plus/icons-vue'
import TagsView from '../components/TagsView.vue'
import FavoriteConfig from '../components/FavoriteConfig.vue'
import { menuIcon } from '../utils/menuIcons'
import api from '../api'
import { setLocale } from '../i18n'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const activeMenu = computed(() => route.path)

// ---- 动态菜单（按权限） ----
const menuLoading = ref(false)
const menuGroups = ref([])     // 有子菜单的分组
const flatMenus = ref([])      // 无分组的平铺菜单
const openGroups = ref([])

const langLabel = computed(() => {
  if (locale.value === 'zhCN') return '简体中文'
  if (locale.value === 'ar') return 'العربية'
  return 'English'
})
function menuName(m) { return locale.value === 'zhCN' ? m.name : (m.name_en || m.name) }
function groupName(g) { return locale.value === 'zhCN' ? g.name : (g.name_en || g.name) }

async function loadMenus() {
  menuLoading.value = true
  try {
    const res = await api.get('/menu/my-menus')
    // 首页分组不显示在左侧（首页是固定标签/空白页）
    const groups = (res.groups || []).filter((g) => g.code !== 'home')
    menuGroups.value = groups.filter((g) => (g.menus || []).length > 1)
    flatMenus.value = groups.filter((g) => (g.menus || []).length === 1).map((g) => g.menus[0])
    openGroups.value = menuGroups.value.map((g) => g.code + '-group')
  } catch (e) {
    menuGroups.value = []
    flatMenus.value = []
  } finally {
    menuLoading.value = false
  }
}

// 路径 -> 标题（标签与页头共用）
function titleOf(path) {
  if (path === HOME_PATH) return t('home.homeTab')
  if (path.includes('performance/coefficients')) return t('performance.coefficient')
  if (path.includes('performance/employee')) return t('performance.employee')
  if (path.includes('otb/dashboard')) return t('otb.dashboard')
  if (path.includes('otb/category')) return t('otb.category')
  if (path.includes('otb/brand-category')) return t('otb.brandCategory')
  if (path.includes('otb/brand')) return t('otb.brand')
  if (path.includes('otb/sales-curve')) return t('otb.salesCurve')
  if (path.includes('otb/replenishment')) return t('otb.replenishment')
  if (path.includes('bu/definition')) return t('bu.definition')
  if (path.includes('bu/brand')) return t('bu.brand')
  if (path.includes('/issue/my')) return t('issue.myIssues')
  if (path.includes('/issue/monitor')) return t('issue.monitor')
  if (path.includes('/issue/assigned')) return t('issue.assignedToMe')
  if (path.includes('/issue/roles')) return t('issue.roleConfig')
  if (path.includes('/issue/create')) return t('issue.createTitle')
  if (path.includes('/issue/detail')) return t('issue.detailTitle')
  if (path.includes('system/login-log')) return t('sys.loginLog')
  if (path.includes('system/online-users')) return t('sys.onlineUsers')
  if (path.includes('system/change-password')) return t('sys.changePwd')
  if (path.includes('system/permission')) return t('perm.title')
  if (path.includes('dashboard')) return t('home.dashboard')
  // 动态菜单里找名称
  for (const m of flatMenus.value) if (m.path === path) return menuName(m)
  for (const g of menuGroups.value) for (const m of g.menus) if (m.path === path) return menuName(m)
  return t('home.containerTracking')
}
const pageTitle = computed(() => titleOf(route.path))

// ---- 顶部多标签页 ----
const HOME_PATH = '/home'
const tags = ref([{ path: HOME_PATH, fixed: true }])
const tagItems = computed(() => tags.value.map((tag) => ({
  path: tag.path,
  fixed: tag.fixed,
  title: titleOf(tag.path),
})))

watch(() => route.path, (path) => {
  if (!path || path === '/login') return
  if (!tags.value.some((tag) => tag.path === path)) tags.value.push({ path, fixed: false })
}, { immediate: true })

function openTag(path) {
  if (path !== route.path) router.push(path)
}

function closeTag(path) {
  const idx = tags.value.findIndex((tag) => tag.path === path)
  if (idx < 0 || tags.value[idx].fixed) return
  tags.value.splice(idx, 1)
  if (route.path === path) {
    const next = tags.value[idx - 1] || tags.value[idx]
    if (next) router.push(next.path)
  }
}

function closeAllTags() {
  tags.value = tags.value.filter((tag) => tag.fixed)
  if (route.path !== HOME_PATH) router.push(HOME_PATH)
}

function closeOtherTags() {
  const current = tags.value.find((tag) => tag.path === route.path)
  tags.value = tags.value.filter((tag) => tag.fixed || tag.path === route.path)
  if (!tags.value.find((tag) => tag.path === route.path) && current) {
    tags.value.unshift(current)
  }
}

// ---- 收藏夹配置 / 星标切换 ----
const favVisible = ref(false)
const favoriteCodes = ref([])
const isCurrentFavorited = computed(() => favoriteCodes.value.includes(route.path))

async function loadFavorites() {
  try {
    const res = await api.get('/menu/my-favorites')
    favoriteCodes.value = (res.items || []).map((x) => x.code)
  } catch (e) {
    favoriteCodes.value = []
  }
}

async function toggleFavorite() {
  const code = route.path
  if (code === HOME_PATH) return  // 首页不参与收藏
  const set = new Set(favoriteCodes.value)
  if (set.has(code)) set.delete(code)
  else set.add(code)
  try {
    const res = await api.post('/menu/my-favorites', { menu_codes: [...set] })
    favoriteCodes.value = (res.items || []).map((x) => x.code)
    window.dispatchEvent(new CustomEvent('favorites-changed'))
  } catch (e) { /* api 拦截器已提示 */ }
}

function openFavoriteConfig() { favVisible.value = true }
async function onFavSaved() {
  await loadFavorites()
  window.dispatchEvent(new CustomEvent('favorites-changed'))
}

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

// 站内消息
const messages = ref([])
const unread = ref(0)
async function loadMessages() {
  try {
    const res = await api.get('/issue/messages', { params: { page: 1, page_size: 20 } })
    messages.value = res.items || []
    unread.value = res.unread || 0
  } catch (e) { messages.value = [] }
}
async function readAll() {
  await api.post('/issue/messages/read-all')
  await loadMessages()
}
async function openMessage(m) {
  if (!m.is_read) {
    await api.post(`/issue/messages/${m.id}/read`)
    await loadMessages()
  }
  if (m.issue_id) router.push(`/issue/detail/${m.issue_id}`)
  else router.push('/issue/my')
}
function pollMessages() {
  api.get('/issue/messages', { params: { page: 1, page_size: 1 } })
    .then((res) => { unread.value = res.unread || 0 })
    .catch(() => {})
}
let msgTimer = null
onMounted(() => { loadMenus(); loadFavorites(); pollMessages(); msgTimer = setInterval(pollMessages, 60000) })
onUnmounted(() => { if (msgTimer) clearInterval(msgTimer) })

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
.msg-btn { position: relative; }
.badge { position: absolute; top: -6px; right: -6px; background: #f56c6c; color: #fff; font-size: 10px; line-height: 14px; min-width: 14px; height: 14px; border-radius: 7px; padding: 0 3px; text-align: center; }
.msg-panel { max-height: 420px; overflow-y: auto; }
.msg-head { display: flex; justify-content: space-between; align-items: center; padding-bottom: 8px; border-bottom: 1px solid #ebeef5; font-weight: 500; }
.msg-item { padding: 10px 4px; border-bottom: 1px solid #f0f2f5; cursor: pointer; }
.msg-item:hover { background: #f5f7fa; }
.msg-item.unread .msg-title { color: #409eff; }
.msg-title { font-size: 13px; font-weight: 500; color: #303133; }
.msg-content { font-size: 12px; color: #606266; margin-top: 3px; line-height: 1.5; }
.msg-time { font-size: 11px; color: #909399; margin-top: 4px; }
.msg-empty { text-align: center; color: #909399; padding: 24px 0; font-size: 12px; }
</style>
