<template>
  <div class="dashboard-wrap">
    <div class="fav-panel">
      <div class="fav-head">
        <div class="fav-title"><el-icon><Star /></el-icon> {{ t('home.favorites') }}</div>
        <el-tooltip :content="t('home.favoriteConfig')" placement="bottom">
          <el-button link class="fav-cfg" @click="configVisible = true"><el-icon><Setting /></el-icon></el-button>
        </el-tooltip>
      </div>
      <div v-loading="loading" class="fav-body">
        <div v-if="items.length" class="fav-grid">
          <div v-for="m in items" :key="m.code" class="fav-item" @click="openMenu(m)">
            <div class="fav-icon"><el-icon><component :is="menuIcon(m.icon)" /></el-icon></div>
            <div class="fav-name">{{ locale === 'zhCN' ? m.name : (m.name_en || m.name) }}</div>
          </div>
        </div>
        <div v-else class="fav-empty">
          {{ t('home.noFavorites') }}
          <el-button link type="primary" @click="configVisible = true">{{ t('home.goConfig') }}</el-button>
        </div>
      </div>
    </div>

    <FavoriteConfig v-model="configVisible" @saved="loadFavorites" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { Star, Setting } from '@element-plus/icons-vue'
import api from '../api'
import FavoriteConfig from '../components/FavoriteConfig.vue'
import { menuIcon } from '../utils/menuIcons'

const { t, locale } = useI18n()
const router = useRouter()
const loading = ref(false)
const items = ref([])
const configVisible = ref(false)

async function loadFavorites() {
  loading.value = true
  try {
    const res = await api.get('/menu/my-favorites')
    items.value = res.items || []
  } catch (e) {
    items.value = []
  } finally {
    loading.value = false
  }
}

function openMenu(m) {
  if (m.path) router.push(m.path)
}

onMounted(() => {
  loadFavorites()
  window.addEventListener('favorites-changed', loadFavorites)
})
onUnmounted(() => window.removeEventListener('favorites-changed', loadFavorites))
</script>

<style scoped>
.dashboard-wrap { min-height: 100%; }
.fav-panel { background: #fff; border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }
.fav-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid #ebeef5; }
.fav-title { display: flex; align-items: center; gap: 6px; font-size: 15px; font-weight: 600; color: #303133; }
.fav-title .el-icon { color: #409eff; }
.fav-cfg { font-size: 18px; color: #909399; }
.fav-body { min-height: 160px; padding: 18px; }
.fav-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(92px, 1fr)); gap: 18px 10px; }
.fav-item { display: flex; flex-direction: column; align-items: center; gap: 8px; cursor: pointer; padding: 8px 4px; border-radius: 6px; transition: background .15s; }
.fav-item:hover { background: #f5faff; }
.fav-icon { width: 46px; height: 46px; border-radius: 50%; background: #dbeafe; color: #409eff; display: flex; align-items: center; justify-content: center; font-size: 20px; }
.fav-name { font-size: 12px; color: #606266; text-align: center; line-height: 1.4; max-width: 92px; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.fav-empty { color: #909399; font-size: 13px; text-align: center; padding: 48px 0; }
</style>
