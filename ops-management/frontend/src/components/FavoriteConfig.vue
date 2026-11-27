<template>
  <el-dialog
    :model-value="modelValue"
    :title="t('home.favoriteConfigTitle')"
    width="980px"
    top="6vh"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div v-loading="loading" class="cfg-wrap">
      <div class="cfg-left">
        <div
          v-for="g in groups"
          :key="g.code"
          class="cfg-group"
          :class="{ active: g.code === activeGroup }"
          @click="activeGroup = g.code"
        >{{ locale === 'zhCN' ? g.name : (g.name_en || g.name) }}</div>
      </div>
      <div class="cfg-right">
        <div v-if="currentMenus.length === 0" class="cfg-empty">{{ t('home.noMenus') }}</div>
        <div class="cfg-grid">
          <label v-for="m in currentMenus" :key="m.code" class="cfg-item">
            <el-checkbox v-model="checked[m.code]" />
            <el-icon class="cfg-icon"><component :is="menuIcon(m.icon)" /></el-icon>
            <span>{{ locale === 'zhCN' ? m.name : (m.name_en || m.name) }}</span>
          </label>
        </div>
      </div>
    </div>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :loading="saving" @click="submit">{{ t('common.confirm') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import api from '../api'
import { menuIcon } from '../utils/menuIcons'

const props = defineProps({ modelValue: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue', 'saved'])
const { t, locale } = useI18n()

const loading = ref(false)
const saving = ref(false)
const groups = ref([])
const activeGroup = ref('')
const checked = ref({})

const currentMenus = computed(() => {
  const g = groups.value.find((x) => x.code === activeGroup.value)
  return g ? g.menus : []
})

async function load() {
  loading.value = true
  try {
    const [menuRes, favRes] = await Promise.all([
      api.get('/menu/my-menus'),
      api.get('/menu/my-favorites'),
    ])
    groups.value = menuRes.groups || []
    activeGroup.value = groups.value[0]?.code || ''
    checked.value = {}
    const favSet = new Set((favRes.items || []).map((x) => x.code))
    groups.value.forEach((g) => g.menus.forEach((m) => { checked.value[m.code] = favSet.has(m.code) }))
  } catch (e) {
    groups.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.modelValue, (v) => { if (v) load() })

async function submit() {
  const codes = Object.keys(checked.value).filter((c) => checked.value[c])
  saving.value = true
  try {
    await api.post('/menu/my-favorites', { menu_codes: codes })
    ElMessage.success(t('home.favoriteSaved'))
    emit('saved')
    emit('update:modelValue', false)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.cfg-wrap { display: flex; min-height: 420px; border: 1px solid #ebeef5; border-radius: 4px; overflow: hidden; }
.cfg-left { width: 150px; flex: none; border-right: 1px solid #ebeef5; background: #fafafa; padding: 6px 0; }
.cfg-group { padding: 10px 14px; font-size: 13px; color: #606266; cursor: pointer; border-left: 3px solid transparent; }
.cfg-group:hover { background: #f0f2f5; }
.cfg-group.active { background: #e8f3ff; color: #2563eb; border-left-color: #409eff; }
.cfg-right { flex: 1; padding: 14px; overflow: auto; max-height: 480px; }
.cfg-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; }
.cfg-item { display: flex; align-items: center; gap: 8px; padding: 9px 10px; border: 1px solid #ebeef5; border-radius: 4px; cursor: pointer; font-size: 13px; color: #303133; }
.cfg-item:hover { border-color: #409eff; background: #f5faff; }
.cfg-icon { color: #409eff; font-size: 16px; }
.cfg-empty { color: #909399; text-align: center; padding: 60px 0; font-size: 13px; }
</style>
